"""EXPERIMENTAL: a "cultural similarity" name embedder.

Embeds the bare Hebrew name string through a pretrained multilingual
sentence-transformer (exported to ONNX + int8-quantized offline, see
scripts/export_semantic_model.py), aiming to surface names that are
culturally/biblically/etymologically related even when spelled completely
differently -- the opposite blind spot of the character n-gram
(`written_similarity`) model.

There is no confirmed prior art for this specific technique (embedding a
bare given name, rather than a sentence, through a general-purpose
multilingual sentence encoder) and no ground-truth dataset to validate
against. Treat its output as a soft, human-judged signal -- see the sanity
check in build_artifacts.py and PLAN.md's "Sanity check" section. It is
entirely possible this ends up mostly re-deriving orthographic/phonetic
similarity (duplicating written_similarity) rather than capturing genuine
cultural association; that would be a real negative result on the modeling
approach, not a bug.

Runtime dependencies are deliberately limited to `onnxruntime` + the
standalone `tokenizers` package -- NOT `torch`/`transformers`, which are
export-time-only tooling (see the `export` dependency group in
pyproject.toml) so the deployed backend stays free of a multi-GB ML
framework.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class OnnxSentenceEmbedder:
    """Mean-pooled, L2-normalized sentence-transformer embedding, served via
    a quantized ONNX graph. Implements the NameEmbedder protocol."""

    def __init__(self, model_dir: Path, max_length: int = 32, dim: int = 384) -> None:
        self._model_dir = Path(model_dir)
        self._max_length = max_length
        self._dim = dim
        self._session: ort.InferenceSession | None = None
        self._tokenizer: Tokenizer | None = None
        self._expects_token_type_ids = False

    def fit_corpus(self, names: list[str]) -> None:
        # True no-op: nothing to fit for a pretrained model. Deliberately
        # does NOT eagerly load the ONNX session/tokenizer here -- loading
        # them costs ~600MB RSS (the tokenizer's 250K-vocab table alone is
        # ~210MB, more than the 118MB quantized model). Since
        # search_service looks up precomputed corpus vectors before ever
        # calling encode() (see vector_for() usage there), a typical
        # session backed by autocomplete-selected names never triggers a
        # live load at all. Loading happens lazily, once, on the first
        # actual encode() call -- see _ensure_loaded().
        pass

    def encode(self, names: list[str], batch_size: int = 64) -> np.ndarray:
        self._ensure_loaded()
        assert self._tokenizer is not None and self._session is not None

        chunks: list[np.ndarray] = []
        for i in range(0, len(names), batch_size):
            batch = names[i : i + batch_size]
            encodings = self._tokenizer.encode_batch(batch)
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            feed = {"input_ids": input_ids, "attention_mask": attention_mask}
            if self._expects_token_type_ids:
                feed["token_type_ids"] = np.zeros_like(input_ids)

            last_hidden_state = self._session.run(None, feed)[0]  # (batch, seq_len, dim)

            mask = attention_mask[:, :, None].astype(np.float32)
            summed = (last_hidden_state * mask).sum(axis=1)
            counts = np.clip(mask.sum(axis=1), 1e-9, None)
            pooled = summed / counts  # mean pooling over real (non-pad) tokens

            norm = np.linalg.norm(pooled, axis=1, keepdims=True)
            normalized = pooled / np.clip(norm, 1e-9, None)  # L2 normalize
            chunks.append(normalized.astype(np.float32))

        return np.concatenate(chunks, axis=0)

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return

        self._tokenizer = Tokenizer.from_file(str(self._model_dir / "tokenizer.json"))
        self._tokenizer.enable_padding()
        self._tokenizer.enable_truncation(max_length=self._max_length)

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1  # keep CPU/memory footprint predictable on a small host
        self._session = ort.InferenceSession(
            str(self._model_dir / "model_quantized.onnx"),
            sess_options=so,
            providers=["CPUExecutionProvider"],
        )
        input_names = {i.name for i in self._session.get_inputs()}
        self._expects_token_type_ids = "token_type_ids" in input_names
