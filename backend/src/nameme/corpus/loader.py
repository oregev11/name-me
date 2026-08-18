"""Loads all precomputed artifacts (corpus metadata + every registered
model's fitted embedder, corpus vectors, and fitted PCA projector) once at
startup into a single in-memory store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from nameme.embedding.base import NameEmbedder
from nameme.embedding.registry import MODEL_REGISTRY


@dataclass
class ModelStore:
    """In-memory view of one model's fitted artifacts."""

    unique_names: list[str]  # order matches `vectors` rows
    vectors: np.ndarray  # shape (len(unique_names), embedder.dim)
    embedder: NameEmbedder
    pca: PCA
    _name_to_row: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._name_to_row = {name: i for i, name in enumerate(self.unique_names)}

    def vector_for(self, name: str) -> np.ndarray | None:
        row = self._name_to_row.get(name)
        return None if row is None else self.vectors[row]


@dataclass
class CorpusStore:
    """Shared corpus metadata + every loaded model's ModelStore."""

    names_df: pd.DataFrame  # columns: name, sex, total (may have 2 rows per name)
    models: dict[str, ModelStore]
    _meta_by_name: dict[str, dict] = field(init=False, repr=False)
    names_by_popularity: list[str] = field(init=False, repr=False)
    corpus_size: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # If a name appears for both sexes, prefer the higher-total row for
        # display metadata (e.g. autocomplete). Model-independent.
        meta = (
            self.names_df.sort_values("total", ascending=False)
            .drop_duplicates(subset="name", keep="first")
            .set_index("name")
        )
        # Percentile rank by popularity, 0..1, higher = more popular. Powers
        # the "top 10% / top 90% of names" filter -- computed once here so a
        # search request is just a threshold comparison, not a full re-rank.
        meta["percentile"] = meta["total"].rank(pct=True)
        self._meta_by_name = meta.to_dict(orient="index")
        # Precomputed once so autocomplete requests only filter, not sort.
        self.names_by_popularity = meta.index.tolist()
        self.corpus_size = len(meta)

    def meta_for(self, name: str) -> dict:
        return self._meta_by_name.get(name, {"sex": "U", "total": 0, "percentile": 0.0})

    def model(self, model_id: str) -> ModelStore:
        try:
            return self.models[model_id]
        except KeyError:
            raise ValueError(f"Unknown model id: {model_id!r}") from None


def load_corpus_store(artifacts_dir: Path) -> CorpusStore:
    names_df = pd.read_csv(artifacts_dir / "name_corpus.csv")

    models: dict[str, ModelStore] = {}
    for spec in MODEL_REGISTRY.values():
        model_dir = artifacts_dir / spec.artifacts_subdir

        npz = np.load(model_dir / "corpus_vectors.npz", allow_pickle=True)
        unique_names = list(npz["names"])
        vectors = npz["vectors"]

        if spec.persisted_embedder:
            embedder: NameEmbedder = joblib.load(model_dir / "embedder.joblib")
        else:
            embedder = spec.new_embedder(model_dir)
            # Deliberately NOT warmed up here -- see OnnxSentenceEmbedder.fit_corpus():
            # loading the ONNX session + tokenizer costs ~600MB RSS, and most
            # searches never need it since search_service checks precomputed
            # corpus vectors first. It loads lazily on first real encode() call.
            embedder.fit_corpus([])

        pca: PCA = joblib.load(model_dir / "pca_projector.joblib")

        models[spec.id] = ModelStore(
            unique_names=unique_names, vectors=vectors, embedder=embedder, pca=pca
        )

    return CorpusStore(names_df=names_df, models=models)
