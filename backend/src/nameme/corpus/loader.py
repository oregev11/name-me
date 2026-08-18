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


@dataclass
class CorpusStore:
    """Shared corpus metadata + every loaded model's ModelStore."""

    # columns: name, sex, sector, total -- one row per (name, sex, sector)
    # combination CBS published a count for; a name can have several rows
    # (e.g. used by both sexes, or by more than one sector).
    names_df: pd.DataFrame
    models: dict[str, ModelStore]
    _meta_by_name: dict[str, dict] = field(init=False, repr=False)
    names_by_popularity: list[str] = field(init=False, repr=False)
    corpus_size: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        df = self.names_df

        # Overall popularity: summed across every sex+sector row for a name
        # (a name's "total" is no longer a single source row now that
        # sector isn't aggregated away at build time).
        overall_total = df.groupby("name")["total"].sum()
        percentile = overall_total.rank(pct=True)

        # Dominant sex: the single (sex, sector) row with the largest count
        # for that name -- kept as a simple display field (SuggestedName.sex),
        # same simplification as before sector was tracked.
        dominant = (
            df.sort_values("total", ascending=False)
            .drop_duplicates(subset="name", keep="first")
            .set_index("name")["sex"]
        )

        # Every (sex, sector) combination a name has at least one row for --
        # this is what the sex/sector filters actually check membership
        # against, so a name filtered to e.g. sex=M, sector=Jewish must have
        # a real Jewish-boys row, not just *some* Jewish row and *some* boys
        # row from unrelated sectors/sexes.
        combos = df.groupby("name").apply(
            lambda g: set(zip(g["sex"], g["sector"], strict=True)),
            include_groups=False,
        )

        self._meta_by_name = {
            name: {
                "sex": dominant[name],
                "total": int(overall_total[name]),
                "percentile": float(percentile[name]),
                "combos": combos[name],
            }
            for name in overall_total.index
        }
        # Precomputed once so autocomplete requests only filter, not sort.
        self.names_by_popularity = overall_total.sort_values(ascending=False).index.tolist()
        self.corpus_size = len(overall_total)

    def meta_for(self, name: str) -> dict:
        return self._meta_by_name.get(
            name, {"sex": "U", "total": 0, "percentile": 0.0, "combos": set()}
        )

    def matches_sex_sector(self, name: str, sex: str, sector: str) -> bool:
        """True if `name` has at least one real (sex, sector) row matching
        both filters (either side of "any" matches anything). This is a
        combined check rather than two independent membership checks, so
        filtering to e.g. sex=M + sector=Jewish only keeps names actually
        used as Jewish boys' names -- not any name with some Jewish
        presence AND some boys' presence, possibly from unrelated rows.
        """
        if sex == "any" and sector == "any":
            return True
        combos = self.meta_for(name)["combos"]
        return any(
            (sex == "any" or s == sex) and (sector == "any" or sec == sector)
            for s, sec in combos
        )

    def model(self, model_id: str) -> ModelStore:
        try:
            return self.models[model_id]
        except KeyError:
            raise ValueError(f"Unknown model id: {model_id!r}") from None


def load_corpus_store(artifacts_dir: Path) -> CorpusStore:
    names_df = pd.read_csv(artifacts_dir / "name_corpus.csv")

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

    return CorpusStore(names_df=names_df, models=models)
