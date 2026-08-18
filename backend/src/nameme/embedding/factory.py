"""Factory that resolves the configured embedder type to a concrete instance.

To add a new embedding technique later: implement a class satisfying
`NameEmbedder` in a new module here, add a branch below, and point
`EMBEDDER_TYPE` at it. No other code needs to change.
"""

from __future__ import annotations

from nameme.embedding.base import NameEmbedder
from nameme.embedding.ngram_svd import NgramSvdEmbedder


def get_embedder(embedder_type: str, embedder_dim: int = 100) -> NameEmbedder:
    if embedder_type == "ngram_svd":
        return NgramSvdEmbedder(n_components=embedder_dim)
    raise ValueError(f"Unknown embedder_type: {embedder_type!r}")
