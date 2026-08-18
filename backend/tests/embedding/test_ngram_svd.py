from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics.pairwise import cosine_similarity

from nameme.embedding.ngram_svd import NgramSvdEmbedder

CORPUS = ["דוד", "דודי", "דניאל", "שרה", "שרון", "מיכאל", "יוסף", "יוסי", "רחל", "נועה"]


@pytest.fixture
def embedder() -> NgramSvdEmbedder:
    e = NgramSvdEmbedder(n_components=5)
    e.fit_corpus(CORPUS)
    return e


def test_encode_before_fit_raises() -> None:
    e = NgramSvdEmbedder(n_components=5)
    with pytest.raises(RuntimeError):
        e.encode(["דוד"])


def test_encode_shape(embedder: NgramSvdEmbedder) -> None:
    vectors = embedder.encode(["דוד", "שרה"])
    assert vectors.shape == (2, embedder.dim)


def test_similar_spellings_are_more_similar_than_unrelated(embedder: NgramSvdEmbedder) -> None:
    v_david = embedder.encode(["דוד"])
    v_davidi = embedder.encode(["דודי"])  # shares the "דוד" substring
    v_noa = embedder.encode(["נועה"])  # unrelated spelling

    sim_related = cosine_similarity(v_david, v_davidi)[0, 0]
    sim_unrelated = cosine_similarity(v_david, v_noa)[0, 0]

    assert sim_related > sim_unrelated


def test_encode_handles_out_of_vocabulary_name(embedder: NgramSvdEmbedder) -> None:
    # Not in the fitted corpus at all -- should still return a finite vector.
    vector = embedder.encode(["אביגיל"])
    assert vector.shape == (1, embedder.dim)
    assert np.all(np.isfinite(vector))


def test_fit_corpus_accepts_a_background_corpus() -> None:
    # The vectorizer's vocabulary/IDF can come from a separate, larger
    # corpus while SVD still fits on the names themselves.
    background = ["שלום", "בית", "ילד", "ילדה", "אהבה", "משפחה", "חיים", "אור", "שמש", "ים"]
    e = NgramSvdEmbedder(n_components=5)
    e.fit_corpus(CORPUS, background_corpus=background)

    vectorizer = e._pipeline.named_steps["tfidf"]  # noqa: SLF001
    # Vocabulary should include n-grams that only appear in the background
    # words, not in any name -- proof the vectorizer was fit on `background`.
    assert any("של" in term for term in vectorizer.vocabulary_)

    vector = e.encode(["דוד"])
    assert vector.shape == (1, 5)
    assert np.all(np.isfinite(vector))


def test_fit_corpus_without_background_corpus_still_works() -> None:
    # Backward-compatible default: fit on the names themselves.
    e = NgramSvdEmbedder(n_components=5)
    e.fit_corpus(CORPUS)
    vector = e.encode(["דוד"])
    assert vector.shape == (1, 5)
    assert np.all(np.isfinite(vector))
