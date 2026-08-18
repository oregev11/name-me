"""Loads all precomputed artifacts (corpus metadata, fitted embedder, corpus
vectors, fitted PCA projector) once at startup into a single in-memory store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from nameme.embedding.base import NameEmbedder


@dataclass
class CorpusStore:
    """In-memory view of the name corpus and fitted ML artifacts."""

    names_df: pd.DataFrame  # columns: name, sex, total (may have 2 rows per name)
    unique_names: list[str]  # order matches `vectors` rows
    vectors: np.ndarray  # shape (len(unique_names), embedder.dim)
    embedder: NameEmbedder
    pca: PCA
    embedder_type: str
    _name_to_row: dict[str, int] = field(init=False, repr=False)
    _meta_by_name: dict[str, dict] = field(init=False, repr=False)
    names_by_popularity: list[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._name_to_row = {name: i for i, name in enumerate(self.unique_names)}
        # If a name appears for both sexes, prefer the higher-total row for
        # display metadata (e.g. autocomplete), while similarity search
        # still only ever sees one vector per unique spelling.
        meta = (
            self.names_df.sort_values("total", ascending=False)
            .drop_duplicates(subset="name", keep="first")
            .set_index("name")
        )
        self._meta_by_name = meta.to_dict(orient="index")
        # Precomputed once so autocomplete requests only filter, not sort.
        self.names_by_popularity = meta.index.tolist()

    def vector_for(self, name: str) -> np.ndarray | None:
        row = self._name_to_row.get(name)
        return None if row is None else self.vectors[row]

    def meta_for(self, name: str) -> dict:
        return self._meta_by_name.get(name, {"sex": "U", "total": 0})

    @property
    def size(self) -> int:
        return len(self.unique_names)


def load_corpus_store(artifacts_dir: Path, embedder_type: str) -> CorpusStore:
    names_df = pd.read_csv(artifacts_dir / "name_corpus.csv")

    npz = np.load(artifacts_dir / "corpus_vectors.npz", allow_pickle=True)
    unique_names = list(npz["names"])
    vectors = npz["vectors"]

    embedder: NameEmbedder = joblib.load(artifacts_dir / "embedder.joblib")
    pca: PCA = joblib.load(artifacts_dir / "pca_projector.joblib")

    return CorpusStore(
        names_df=names_df,
        unique_names=unique_names,
        vectors=vectors,
        embedder=embedder,
        pca=pca,
        embedder_type=embedder_type,
    )
