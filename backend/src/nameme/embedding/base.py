"""The embedder abstraction that lets us swap embedding techniques later
without touching the API, schemas, or frontend.

Any future implementation (e.g. a Name2Vec-style trained Doc2Vec model) just
needs to satisfy this Protocol and be registered in `factory.py`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class NameEmbedder(Protocol):
    """Encodes Hebrew names into fixed-size vectors for similarity search."""

    def fit_corpus(self, names: list[str]) -> None:
        """Fit the embedder on the full name corpus. Must be called once
        before `encode`."""
        ...

    def encode(self, names: list[str]) -> np.ndarray:
        """Encode a list of names into an array of shape (len(names), dim).

        Must work for names outside the fitted corpus (out-of-vocabulary
        input from a user), even if the resulting vector is lower quality.
        """
        ...

    @property
    def dim(self) -> int:
        """Dimensionality of the vectors produced by `encode`."""
        ...
