"""MVP name embedder: character n-gram TF-IDF reduced via truncated SVD.

Requires no training corpus beyond the name list itself, no external model
download, and generalizes to out-of-vocabulary names because it operates on
character substrings rather than whole-name identity.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

RANDOM_STATE = 42


class NgramSvdEmbedder:
    """Char n-gram TF-IDF -> TruncatedSVD pipeline implementing NameEmbedder."""

    def __init__(self, n_components: int = 100, ngram_range: tuple[int, int] = (2, 3)) -> None:
        self._n_components = n_components
        self._pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=ngram_range)),
                ("svd", TruncatedSVD(n_components=n_components, random_state=RANDOM_STATE)),
            ]
        )
        self._fitted = False

    def fit_corpus(self, names: list[str]) -> None:
        self._pipeline.fit(names)
        self._fitted = True

    def encode(self, names: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("NgramSvdEmbedder.fit_corpus() must be called before encode()")
        return self._pipeline.transform(names)

    @property
    def dim(self) -> int:
        return self._n_components
