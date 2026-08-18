"""Core search logic: encode liked names -> centroid -> cosine similarity
against the corpus -> top-K suggestions, all projected into the shared 2D
PCA space.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nameme.corpus.loader import CorpusStore
from nameme.schemas.search import NamePoint, SearchResponse, SuggestedName
from nameme.services.projection_service import project_to_2d


def search(store: CorpusStore, liked_names: list[str], top_k: int) -> SearchResponse:
    liked_vectors = store.embedder.encode(liked_names)
    centroid = liked_vectors.mean(axis=0, keepdims=True)

    similarities = cosine_similarity(centroid, store.vectors)[0]

    liked_set = set(liked_names)
    ranked_idx = np.argsort(-similarities)

    suggestion_idx = []
    for idx in ranked_idx:
        name = store.unique_names[idx]
        if name in liked_set:
            continue
        suggestion_idx.append(idx)
        if len(suggestion_idx) == top_k:
            break

    liked_coords = project_to_2d(store.pca, liked_vectors)
    liked_points = [
        NamePoint(name=name, x=x, y=y)
        for name, (x, y) in zip(liked_names, liked_coords, strict=True)
    ]

    suggestion_vectors = store.vectors[suggestion_idx]
    suggestion_coords = project_to_2d(store.pca, suggestion_vectors)
    suggestions = []
    for idx, (x, y) in zip(suggestion_idx, suggestion_coords, strict=True):
        name = store.unique_names[idx]
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
