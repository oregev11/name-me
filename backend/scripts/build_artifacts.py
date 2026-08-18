"""Fit the configured name embedder + a global 2D PCA projector on the name
corpus, and persist all artifacts the backend loads at startup.

Re-run this whenever name_corpus.csv changes, or whenever EMBEDDER_TYPE /
EMBEDDER_DIM changes (e.g. after adding a new NameEmbedder implementation).

Usage:
    uv run python scripts/build_artifacts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nameme.config import ARTIFACTS_DIR, get_settings  # noqa: E402
from nameme.embedding.factory import get_embedder  # noqa: E402

RANDOM_STATE = 42

CORPUS_PATH = ARTIFACTS_DIR / "name_corpus.csv"
EMBEDDER_PATH = ARTIFACTS_DIR / "embedder.joblib"
VECTORS_PATH = ARTIFACTS_DIR / "corpus_vectors.npz"
PCA_PATH = ARTIFACTS_DIR / "pca_projector.joblib"


def main() -> None:
    settings = get_settings()
    print(f"Using embedder_type={settings.embedder_type!r} embedder_dim={settings.embedder_dim}")

    corpus = pd.read_csv(CORPUS_PATH)
    # A name can appear twice (once per sex) -- embeddings operate on unique
    # spellings, so dedupe for fitting/encoding purposes.
    unique_names = corpus["name"].drop_duplicates().tolist()
    print(f"Fitting embedder on {len(unique_names)} unique name spellings")

    embedder = get_embedder(settings.embedder_type, settings.embedder_dim)
    embedder.fit_corpus(unique_names)
    joblib.dump(embedder, EMBEDDER_PATH, compress=3)
    print(f"Wrote {EMBEDDER_PATH}")

    vectors = embedder.encode(unique_names).astype(np.float32)
    np.savez_compressed(
        VECTORS_PATH, names=np.array(unique_names, dtype=object), vectors=vectors
    )
    print(f"Wrote {VECTORS_PATH} (shape={vectors.shape}, dtype={vectors.dtype})")

    # Fit the global 2D PCA once here; the backend only ever calls
    # `.transform()` on it at request time so the coordinate space stays
    # stable across repeated searches.
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coords = pca.fit_transform(vectors)
    joblib.dump(pca, PCA_PATH, compress=3)
    print(f"Wrote {PCA_PATH} (explained_variance_ratio={pca.explained_variance_ratio_})")

    # Sanity check: a few known-similar name pairs should land closer in
    # cosine similarity than a clearly unrelated pair.
    from sklearn.metrics.pairwise import cosine_similarity

    def sim(a: str, b: str) -> float:
        va = embedder.encode([a])
        vb = embedder.encode([b])
        return float(cosine_similarity(va, vb)[0, 0])

    print("\nSanity check -- cosine similarity of a few name pairs:")
    for a, b in [("דוד", "דודי"), ("שרה", "שרון"), ("משה", "מיכאל")]:
        print(f"  sim({a!r}, {b!r}) = {sim(a, b):.3f}")

    print(f"\n2D PCA coordinate range: x=[{coords[:, 0].min():.2f}, {coords[:, 0].max():.2f}] "
          f"y=[{coords[:, 1].min():.2f}, {coords[:, 1].max():.2f}]")


if __name__ == "__main__":
    main()
