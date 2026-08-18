"""Core search logic: encode liked names -> centroid ("middle point") ->
cosine similarity against the corpus -> top-K suggestions (closest by
default, or farthest in "dissimilar" mode), all projected into the shared
2D PCA space. Suggestions can be filtered by sex and by popularity
percentile before the top-K cut is taken.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nameme.corpus.loader import CorpusStore, ModelStore
from nameme.schemas.search import (
    NamePoint,
    PopularityFilter,
    SearchResponse,
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


def _encode_liked_names(model: ModelStore, liked_names: list[str]) -> np.ndarray:
    """Look up precomputed corpus vectors first; only call the (possibly
    expensive/lazily-loaded) embedder for names outside the corpus.

    Autocomplete steers most user input to names already in the corpus, so
    in the common case this never touches the live embedder at all -- which
    matters most for `cultural_similarity`, whose ONNX session + tokenizer
    cost real memory to load on first use (see OnnxSentenceEmbedder).
    """
    vectors = [model.vector_for(name) for name in liked_names]
    missing = [name for name, v in zip(liked_names, vectors, strict=True) if v is None]
    if missing:
        encoded = iter(model.embedder.encode(missing))
        vectors = [v if v is not None else next(encoded) for v in vectors]
    return np.stack(vectors, axis=0)


def search(
    store: CorpusStore,
    liked_names: list[str],
    top_k: int,
    model_id: str,
    sex: SexFilter = "any",
    popularity: PopularityFilter = "all",
    sort: SortMode = "similar",
) -> SearchResponse:
    model = store.model(model_id)

    liked_vectors = _encode_liked_names(model, liked_names)
    centroid = liked_vectors.mean(axis=0, keepdims=True)  # the "middle point"

    similarities = cosine_similarity(centroid, model.vectors)[0]

    liked_set = set(liked_names)
    # "similar": closest to the middle point first. "dissimilar": farthest
    # first -- same ranking, just walked from the other end.
    ranked_idx = np.argsort(-similarities) if sort == "similar" else np.argsort(similarities)

    min_percentile = _POPULARITY_THRESHOLDS[popularity]

    suggestion_idx = []
    for idx in ranked_idx:
        name = model.unique_names[idx]
        if name in liked_set:
            continue
        meta = store.meta_for(name)
        if sex != "any" and meta["sex"] != sex:
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
        meta = store.meta_for(name)
        suggestions.append(
            SuggestedName(
                name=name,
                x=x,
                y=y,
                similarity=float(similarities[idx]),
                sex=meta["sex"],
                popularity=int(meta["total"]),
            )
        )

    return SearchResponse(liked=liked_points, suggestions=suggestions)
