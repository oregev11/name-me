"""Loads all precomputed artifacts (corpus metadata + every registered
model's fitted embedder, corpus vectors, and fitted PCA projector) once at
startup into a single in-memory store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from nameme.embedding.base import NameEmbedder
from nameme.embedding.registry import MODEL_REGISTRY


@dataclass
class ModelStore:
    """In-memory view of one model's fitted artifacts."""

    unique_names: list[str]  # order matches `vectors` rows
    vectors: np.ndarray  # shape (len(unique_names), embedder.dim)
    embedder: NameEmbedder
    pca: PCA
    _name_to_row: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._name_to_row = {name: i for i, name in enumerate(self.unique_names)}

    def vector_for(self, name: str) -> np.ndarray | None:
        row = self._name_to_row.get(name)
        return None if row is None else self.vectors[row]


def _compute_meta(df: pd.DataFrame) -> dict[str, dict]:
    """Builds the per-name metadata dict (sex, total, percentile, combos)
    from a (name, sex, sector, total) dataframe. Shared by the full-corpus
    (all years) case and the on-demand year-filtered case -- same shape,
    different input rows.
    """
    if df.empty:
        return {}

    overall_total = df.groupby("name")["total"].sum()
    percentile = overall_total.rank(pct=True)

    # Dominant sex: the single (sex, sector) row with the largest count for
    # that name -- kept as a simple display field (SuggestedName.sex).
    dominant = (
        df.sort_values("total", ascending=False)
        .drop_duplicates(subset="name", keep="first")
        .set_index("name")["sex"]
    )

    # Every (sex, sector) combination a name has at least one row for --
    # this is what the sex/sector filters check membership against, so
    # e.g. sex=M + sector=Jewish only keeps names with a real Jewish-boys
    # row, not just *some* Jewish row and *some* boys row from unrelated
    # rows.
    combos = df.groupby("name").apply(
        lambda g: set(zip(g["sex"], g["sector"], strict=True)),
        include_groups=False,
    )

    return {
        name: {
            "sex": dominant[name],
            "total": int(overall_total[name]),
            "percentile": float(percentile[name]),
            "combos": combos[name],
        }
        for name in overall_total.index
    }


def combos_match(combos: set[tuple[str, str]], sex: str, sector: str) -> bool:
    if sex == "any" and sector == "any":
        return True
    return any(
        (sex == "any" or s == sex) and (sector == "any" or sec == sector) for s, sec in combos
    )


def _filter_rows(df: pd.DataFrame, sex: str, sector: str) -> pd.DataFrame:
    """Rows matching the sex/sector filter ("any" side matches everything).

    Narrowing the *source rows* before aggregating (rather than aggregating
    over everything and only checking row existence afterwards) is what
    makes a suggestion's displayed metadata reflect the active filter: e.g.
    a sex=F search on a name that's mostly given to boys but also to many
    girls (a real case -- see test_corpus_store.py) shows that name's
    female-only count and `sex="F"`, not its overall (sex-mixed) dominant
    values -- which previously made girls-filtered searches visibly surface
    "boys" on the chart.
    """
    if sex == "any" and sector == "any":
        return df
    mask = pd.Series(True, index=df.index)
    if sex != "any":
        mask &= df["sex"] == sex
    if sector != "any":
        mask &= df["sector"] == sector
    return df.loc[mask]


@dataclass
class CorpusStore:
    """Shared corpus metadata + every loaded model's ModelStore."""

    # columns: name, sex, sector, total -- one row per (name, sex, sector)
    # combination CBS published a lifetime count for; a name can have
    # several rows (e.g. used by both sexes, or by more than one sector).
    names_df: pd.DataFrame
    # columns: name, sex, sector, year, total -- supplementary per-year
    # breakdown, powers the year-range filter. A STRICT SUBSET of
    # names_df's names (see scripts/build_corpus.py): names without any
    # yearly breakdown remain fully searchable with no year filter applied,
    # but can't be matched against a narrower-than-full year range since we
    # have no evidence of which years they were actually given in.
    years_df: pd.DataFrame
    models: dict[str, ModelStore]
    _meta_by_name: dict[str, dict] = field(init=False, repr=False)
    names_by_popularity: list[str] = field(init=False, repr=False)
    corpus_size: int = field(init=False, repr=False)
    year_min: int = field(init=False, repr=False)
    year_max: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._meta_by_name = _compute_meta(self.names_df)
        # Precomputed once so autocomplete requests only filter, not sort.
        self.names_by_popularity = sorted(
            self._meta_by_name, key=lambda n: self._meta_by_name[n]["total"], reverse=True
        )
        self.corpus_size = len(self._meta_by_name)
        self.year_min = int(self.years_df["year"].min())
        self.year_max = int(self.years_df["year"].max())

    def meta_for(self, name: str) -> dict:
        return self._meta_by_name.get(
            name, {"sex": "U", "total": 0, "percentile": 0.0, "combos": set()}
        )

    def full_meta(self) -> dict[str, dict]:
        """The complete (all-years, no sex/sector narrowing) per-name
        metadata dict -- same shape as `year_filtered_meta()`'s and
        `sex_sector_filtered_meta()`'s return values, so callers can pick
        whichever source fits and treat it uniformly (see
        services/search_service.py).
        """
        return self._meta_by_name

    def sex_sector_filtered_meta(self, sex: str, sector: str) -> dict[str, dict]:
        """Per-name metadata from the full (all-years) corpus, narrowed to
        rows matching `sex`/`sector` (see `_filter_rows`) before
        aggregating -- so e.g. a sex=F search shows a unisex name's
        female-only count and `sex="F"`, not its overall dominant values.
        """
        return _compute_meta(_filter_rows(self.names_df, sex, sector))

    def matches_sex_sector(self, name: str, sex: str, sector: str) -> bool:
        """True if `name` has at least one real (sex, sector) row matching
        both filters (either side of "any" matches anything) -- see
        `combos_match`. Uses the full (all-years) metadata; for a live
        search, `sex_sector_filtered_meta()`/`year_filtered_meta()` are
        used instead, since they also narrow the *displayed* metadata to
        the matching rows (see services/search_service.py).
        """
        return combos_match(self.meta_for(name)["combos"], sex, sector)

    def is_full_year_range(self, min_year: int, max_year: int) -> bool:
        return min_year <= self.year_min and max_year >= self.year_max

    def year_filtered_meta(
        self, min_year: int, max_year: int, sex: str = "any", sector: str = "any"
    ) -> dict[str, dict]:
        """Per-name metadata computed from ONLY `years_df` rows within
        [min_year, max_year], further narrowed to rows matching `sex`/
        `sector` when given (default "any" = no narrowing -- see
        `_filter_rows`). Names with no yearly breakdown at all are simply
        absent from the result -- callers should treat this dict as the
        full candidate universe for a year-filtered search (a name missing
        from it means "no evidence found in this range", not "look it up
        elsewhere"), not fall back to `meta_for` for missing names.
        """
        mask = (self.years_df["year"] >= min_year) & (self.years_df["year"] <= max_year)
        return _compute_meta(_filter_rows(self.years_df.loc[mask], sex, sector))

    def model(self, model_id: str) -> ModelStore:
        try:
            return self.models[model_id]
        except KeyError:
            raise ValueError(f"Unknown model id: {model_id!r}") from None


def load_corpus_store(artifacts_dir: Path) -> CorpusStore:
    names_df = pd.read_csv(artifacts_dir / "name_corpus.csv")
    years_df = pd.read_csv(artifacts_dir / "name_years.csv")

    models: dict[str, ModelStore] = {}
    for spec in MODEL_REGISTRY.values():
        model_dir = artifacts_dir / spec.artifacts_subdir

        npz = np.load(model_dir / "corpus_vectors.npz", allow_pickle=True)
        unique_names = list(npz["names"])
        vectors = npz["vectors"]

        if spec.persisted_embedder:
            embedder: NameEmbedder = joblib.load(model_dir / "embedder.joblib")
        else:
            embedder = spec.new_embedder(model_dir)
            # Deliberately NOT warmed up here -- see OnnxSentenceEmbedder.fit_corpus():
            # loading the ONNX session + tokenizer costs ~600MB RSS, and most
            # searches never need it since search_service checks precomputed
            # corpus vectors first. It loads lazily on first real encode() call.
            embedder.fit_corpus([])

        pca: PCA = joblib.load(model_dir / "pca_projector.joblib")

        models[spec.id] = ModelStore(
            unique_names=unique_names, vectors=vectors, embedder=embedder, pca=pca
        )

    return CorpusStore(names_df=names_df, years_df=years_df, models=models)
