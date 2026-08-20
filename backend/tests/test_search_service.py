"""Unit tests for the corpus-vector-lookup-first optimization in
_encode_liked_names: this is what keeps typical (autocomplete-guided)
searches from ever touching the lazily-loaded ONNX embedder, which is what
keeps idle/typical RAM low for the cultural_similarity model. See
PLAN.md's 'RAM verification' section for the measured numbers this
protects.
"""

from __future__ import annotations

import numpy as np
import pytest

from nameme.config import ARTIFACTS_DIR
from nameme.corpus.loader import load_corpus_store
from nameme.services.search_service import UnsupportedOovNameError, _encode_liked_names


def test_in_corpus_names_never_touch_the_live_embedder() -> None:
    store = load_corpus_store(ARTIFACTS_DIR)
    model = store.model("cultural_similarity")

    # Sabotage the live embedder so the test fails loudly if it's ever
    # actually called -- in-corpus names should be served entirely from
    # the precomputed corpus_vectors.npz lookup.
    def _boom(names: list[str]) -> np.ndarray:
        raise AssertionError(f"embedder.encode() should not be called for in-corpus names: {names}")

    model.embedder.encode = _boom  # type: ignore[method-assign]

    liked_names = ["דוד", "יוסף"]
    vectors = _encode_liked_names(model, "cultural_similarity", liked_names)

    assert vectors.shape == (2, model.vectors.shape[1])
    for i, name in enumerate(liked_names):
        np.testing.assert_array_equal(vectors[i], model.vector_for(name))


def test_out_of_corpus_names_fall_back_to_the_live_embedder_when_allowed() -> None:
    # written_similarity allows OOV encode (it's cheap -- no lazy heavyweight
    # session to load, see ModelSpec.allows_oov_encode).
    store = load_corpus_store(ARTIFACTS_DIR)
    model = store.model("written_similarity")

    made_up_name = "קסניופולוס"
    assert model.vector_for(made_up_name) is None  # precondition: genuinely OOV

    vectors = _encode_liked_names(model, "written_similarity", ["דוד", made_up_name])

    assert vectors.shape == (2, model.vectors.shape[1])
    np.testing.assert_array_equal(vectors[0], model.vector_for("דוד"))
    assert np.all(np.isfinite(vectors[1]))


def test_out_of_corpus_names_rejected_when_model_disallows_oov_encode() -> None:
    # cultural_similarity disallows it -- a real Render free-tier deploy
    # OOM-killed itself on exactly this path (lazy ONNX+tokenizer load),
    # see UnsupportedOovNameError's docstring and DEPLOYMENT_PLAN.md.
    store = load_corpus_store(ARTIFACTS_DIR)
    model = store.model("cultural_similarity")

    def _boom(names: list[str]) -> np.ndarray:
        raise AssertionError(f"embedder.encode() must not be called: {names}")

    model.embedder.encode = _boom  # type: ignore[method-assign]

    made_up_name = "קסניופולוס"
    assert model.vector_for(made_up_name) is None  # precondition: genuinely OOV

    with pytest.raises(UnsupportedOovNameError) as exc_info:
        _encode_liked_names(model, "cultural_similarity", ["דוד", made_up_name])

    assert exc_info.value.names == [made_up_name]
    assert exc_info.value.model_id == "cultural_similarity"
