"""The registry of all available name-embedding models.

Replaces the old single-model `factory.py` now that both models must be
live simultaneously (the user picks per-search which to use) rather than
swapped at deploy time via one EMBEDDER_TYPE setting.

To add a third model later: implement a class satisfying `NameEmbedder`,
add one `ModelSpec` entry below pointing at a new artifacts subdirectory,
and it's automatically picked up by `scripts/build_artifacts.py` and the
runtime loader (`corpus/loader.py`) -- both just iterate `MODEL_REGISTRY`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nameme.embedding.base import NameEmbedder
from nameme.embedding.ngram_svd import NgramSvdEmbedder
from nameme.embedding.onnx_sentence import OnnxSentenceEmbedder


@dataclass(frozen=True)
class ModelSpec:
    id: str
    display_name_he: str
    artifacts_subdir: str
    dim: int
    # True: the embedder's fitted state is joblib-dumped/loaded per corpus
    #   build (e.g. a fitted TF-IDF+SVD pipeline).
    # False: the embedder is a stateless wrapper around files already
    #   produced by an offline export step (e.g. an ONNX model) -- nothing
    #   of its own to persist per corpus build.
    persisted_embedder: bool
    new_embedder: Callable[[Path], NameEmbedder]


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "written_similarity": ModelSpec(
        id="written_similarity",
        display_name_he="דמיון כתיב",
        artifacts_subdir="written_similarity",
        dim=100,
        persisted_embedder=True,
        new_embedder=lambda _model_dir: NgramSvdEmbedder(n_components=100),
    ),
    "cultural_similarity": ModelSpec(
        id="cultural_similarity",
        display_name_he="דמיון תרבותי ומשמעות",
        artifacts_subdir="cultural_similarity",
        dim=384,
        persisted_embedder=False,
        new_embedder=lambda model_dir: OnnxSentenceEmbedder(model_dir),
    ),
}
