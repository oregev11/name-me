"""Core search logic: encode liked names -> centroid ("middle point") ->
cosine similarity against the corpus -> top-K suggestions (closest by
default, or farthest in "dissimilar" mode), all projected into the shared
2D PCA space. Suggestions can be filtered by sex, sector, popularity
percentile, and a year range before the top-K cut is taken.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nameme.corpus.loader import CorpusStore, ModelStore
from nameme.schemas.search import (
    NamePoint,
    PopularityFilter,
    SearchResponse,
    SectorFilter,
    SexFilter,
    SortMode,
    SuggestedName,
)
from nameme.services.projection_service import project_to_2d

# Minimum popularity percentile (0..1, from CorpusStore.meta_for) a name must
# have to pass each filter. "top_10_percent" keeps only the most popular
# tenth of the corpus; "top_90_percent" excludes only the least popular
# tenth (a much more permissive cut).
_POPULARITY_THRESHOLDS: dict[PopularityFilter, float] = {
    "all": 0.0,
    "top_10_percent": 0.90,
    "top_90_percent": 0.10,
}


class UnsupportedOovNameError(Exception):
    """Raised when a liked name is outside the model's precomputed corpus
    and that model's `ModelSpec.allows_oov_encode` is False -- currently
    just `cultural_similarity`, whose live encode() path lazily loads an
    ONNX session + tokenizer (~450MB extra RSS, see the root README's
    "Memory footprint" section) that OOM-killed a real Render free-tier
    deploy the one time this was tested against a genuinely novel name.
    Routes should catch this and return a 422 with a clear, actionable
    message instead of letting the request trigger that load.
    """

    def __init__(self, names: list[str], model_id: str) -> None:
        self.names = names
        self.model_id = model_id
        super().__init__(f"{model_id!r} does not support out-of-corpus names: {names!r}")


def _encode_liked_names(
    model: ModelStore, model_id: str, liked_names: list[str]
) -> np.ndarray:
    """Look up precomputed corpus vectors first; only call the (possibly
    expensive/lazily-loaded) embedder for names outside the corpus -- and
    only for models that actually allow that (see `UnsupportedOovNameError`).

    Autocomplete steers most user input to names already in the corpus, so
    in the common case this never touches the live embedder at all -- which
    matters most for `cultural_similarity`, whose ONNX session + tokenizer
    cost real memory to load on first use (see OnnxSentenceEmbedder).
    """
    vectors = [model.vector_for(name) for name in liked_names]
    missing = [name for name, v in zip(liked_names, vectors, strict=True) if v is None]
    if missing:
        if not model.allows_oov_encode:
            raise UnsupportedOovNameError(missing, model_id)
        encoded = iter(model.embedder.encode(missing))
        vectors = [v if v is not None else next(encoded) for v in vectors]
    return np.stack(vectors, axis=0)


def _resolve_meta_source(
    store: CorpusStore,
    sex: SexFilter,
    sector: SectorFilter,
    year_min: int | None,
    year_max: int | None,
) -> dict[str, dict]:
    """Picks which per-name metadata to filter/rank/display against: the
    full (all-years, unfiltered) corpus metadata when no filter narrows
    anything, or an on-the-fly metadata dict aggregated from only the
    matching rows otherwise (year range and/or sex/sector -- see
    `CorpusStore.year_filtered_meta`/`sex_sector_filtered_meta`).

    Narrowing the source rows -- rather than aggregating over everything
    and only checking row *existence* against the filter -- is what makes
    a suggestion's displayed sex/popularity reflect the active filter
    (e.g. a sex=F search shows a mostly-boys name's female-only count and
    `sex="F"`, not its overall dominant values).

    Computed ONCE per request (a single pandas groupby, over at most the
    ~160K-row year breakdown), not per-candidate -- the ranking loop below
    does O(1) dict lookups against whichever dict this returns.
    """
    eff_min = year_min if year_min is not None else store.year_min
    eff_max = year_max if year_max is not None else store.year_max
    full_range = store.is_full_year_range(eff_min, eff_max)
    no_sex_sector_filter = sex == "any" and sector == "any"

    if full_range and no_sex_sector_filter:
        return store.full_meta()
    if full_range:
        return store.sex_sector_filtered_meta(sex, sector)
    return store.year_filtered_meta(eff_min, eff_max, sex, sector)


def search(
    store: CorpusStore,
    liked_names: list[str],
    top_k: int,
    model_id: str,
    sex: SexFilter = "any",
    sector: SectorFilter = "any",
    popularity: PopularityFilter = "all",
    sort: SortMode = "similar",
    year_min: int | None = None,
    year_max: int | None = None,
) -> SearchResponse:
    model = store.model(model_id)

    liked_vectors = _encode_liked_names(model, model_id, liked_names)
    centroid = liked_vectors.mean(axis=0, keepdims=True)  # the "middle point"

    similarities = cosine_similarity(centroid, model.vectors)[0]

    liked_set = set(liked_names)
    # "similar": closest to the middle point first. "dissimilar": farthest
    # first -- same ranking, just walked from the other end.
    ranked_idx = np.argsort(-similarities) if sort == "similar" else np.argsort(similarities)

    min_percentile = _POPULARITY_THRESHOLDS[popularity]
    meta_source = _resolve_meta_source(store, sex, sector, year_min, year_max)

    suggestion_idx = []
    for idx in ranked_idx:
        name = model.unique_names[idx]
        if name in liked_set:
            continue
        meta = meta_source.get(name)
        # Absent from meta_source means "no rows matching the active
        # sex/sector/year filters" -- excluded, not a fallback to broader
        # (e.g. full-corpus) metadata. meta_source is already narrowed to
        # matching rows (see _resolve_meta_source), so no extra sex/sector
        # check is needed here.
        if meta is None:
            continue
        if meta["percentile"] < min_percentile:
            continue
        suggestion_idx.append(idx)
        if len(suggestion_idx) == top_k:
            break

    liked_coords = project_to_2d(model.pca, liked_vectors)
    liked_points = [
        NamePoint(name=name, x=x, y=y)
        for name, (x, y) in zip(liked_names, liked_coords, strict=True)
    ]

    suggestion_vectors = model.vectors[suggestion_idx]
    suggestion_coords = project_to_2d(model.pca, suggestion_vectors)
    suggestions = []
    for idx, (x, y) in zip(suggestion_idx, suggestion_coords, strict=True):
        name = model.unique_names[idx]
        meta = meta_source[name]
        suggestions.append(
            SuggestedName(
                name=name,
                x=x,
                y=y,
                similarity=float(similarities[idx]),
                sex=meta["sex"],
                popularity=int(meta["total"]),
                sectors=sorted({sec for _s, sec in meta["combos"]}),
            )
        )

    return SearchResponse(liked=liked_points, suggestions=suggestions)
