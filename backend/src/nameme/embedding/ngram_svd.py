"""MVP name embedder: character n-gram TF-IDF reduced via truncated SVD.

Requires no external model download, and generalizes to out-of-vocabulary
names because it operates on character substrings rather than whole-name
identity.

The TF-IDF vectorizer's vocabulary and document-frequency weighting can
optionally be fit on a separate, larger background corpus of general Hebrew
words (see `fit_corpus`'s `background_corpus` param) rather than on the name
list itself -- this judges how rare/common a given substring really is
against real Hebrew usage, instead of against the biased, comparatively
small sample of spellings that happen to be given names. The dimensionality
reduction (SVD) is still fit on the actual name vectors, since that's the
entity set the model needs to discriminate between.
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

    def fit_corpus(self, names: list[str], background_corpus: list[str] | None = None) -> None:
        vectorizer: TfidfVectorizer = self._pipeline.named_steps["tfidf"]
        svd: TruncatedSVD = self._pipeline.named_steps["svd"]

        # Vocabulary + IDF weights come from the background corpus when
        # given (a much larger, representative sample of Hebrew words) --
        # otherwise fall back to fitting on the names themselves, same as
        # before. Either way, SVD is fit on the *names'* vectors: it needs
        # to capture variance among the ~20K names we actually serve, not
        # among the whole background vocabulary.
        vectorizer.fit(background_corpus if background_corpus else names)
        name_vectors = vectorizer.transform(names)
        svd.fit(name_vectors)
        self._fitted = True

    def encode(self, names: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("NgramSvdEmbedder.fit_corpus() must be called before encode()")
        return self._pipeline.transform(names)

    @property
    def dim(self) -> int:
        return self._n_components
