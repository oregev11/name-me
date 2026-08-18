from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics.pairwise import cosine_similarity

from nameme.config import ARTIFACTS_DIR
from nameme.embedding.onnx_sentence import OnnxSentenceEmbedder

MODEL_DIR = ARTIFACTS_DIR / "cultural_similarity"


@pytest.fixture(scope="module")
def embedder() -> OnnxSentenceEmbedder:
    e = OnnxSentenceEmbedder(MODEL_DIR)
    e.fit_corpus([])  # no-op warmup, real committed ONNX artifacts
    return e


def test_encode_shape(embedder: OnnxSentenceEmbedder) -> None:
    vectors = embedder.encode(["דוד", "שרה", "רבקה"])
    assert vectors.shape == (3, embedder.dim) == (3, 384)


def test_encode_is_l2_normalized(embedder: OnnxSentenceEmbedder) -> None:
    vectors = embedder.encode(["דוד", "אביגיל"])
    norms = np.linalg.norm(vectors, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-4)


def test_encode_is_deterministic(embedder: OnnxSentenceEmbedder) -> None:
    a = embedder.encode(["שרה"])
    b = embedder.encode(["שרה"])
    np.testing.assert_array_equal(a, b)


def test_encode_handles_out_of_vocabulary_name(embedder: OnnxSentenceEmbedder) -> None:
    # A name unlikely to be a discrete token in the base model's vocabulary --
    # should still produce a finite, well-formed vector via subword composition.
    vector = embedder.encode(["קסניה"])
    assert vector.shape == (1, embedder.dim)
    assert np.all(np.isfinite(vector))


@pytest.mark.xfail(
    reason=(
        "Unproven hypothesis: a general multilingual sentence encoder applied to a "
        "bare Hebrew name string may not actually capture biblical/cultural "
        "association (it may just capture orthographic/phonetic similarity instead, "
        "duplicating written_similarity). If this starts passing, tighten the margin; "
        "if it keeps failing, that's a real negative result on the modeling approach, "
        "not a bug to chase. See PLAN.md's 'Sanity check' section."
    ),
    strict=False,
)
def test_culturally_linked_pairs_more_similar_than_unrelated_control(
    embedder: OnnxSentenceEmbedder,
) -> None:
    pairs = [("שרה", "רבקה"), ("רות", "נעמי"), ("דוד", "שלמה"), ("אברהם", "יצחק")]
    control = "אלמוג"

    passes = 0
    for a, b in pairs:
        va, vb, vc = embedder.encode([a]), embedder.encode([b]), embedder.encode([control])
        linked = cosine_similarity(va, vb)[0, 0]
        control_sim = max(cosine_similarity(va, vc)[0, 0], cosine_similarity(vb, vc)[0, 0])
        if linked > control_sim:
            passes += 1

    assert passes >= 3, f"only {passes}/{len(pairs)} culturally-linked pairs beat their control"
