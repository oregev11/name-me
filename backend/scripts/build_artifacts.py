"""Build/refresh artifacts for every model in MODEL_REGISTRY: fit (or load,
for pretrained models) the embedder, encode the full corpus, and fit a
global 2D PCA projector -- persisting everything each model needs to serve
requests without any offline dependency at runtime.

Re-run this whenever name_corpus.csv changes, or whenever a model's
implementation changes. For `cultural_similarity`, this requires
`scripts/export_semantic_model.py` to have already produced the ONNX model
+ tokenizer files under artifacts/cultural_similarity/ -- this script only
*consumes* that export, it does not produce it.

Usage:
    uv run python scripts/build_artifacts.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from background_corpus import fetch_background_corpus  # noqa: E402
from pipeline_status import PipelineStatus  # noqa: E402

from nameme.config import ARTIFACTS_DIR  # noqa: E402
from nameme.embedding.registry import MODEL_REGISTRY, ModelSpec  # noqa: E402

RANDOM_STATE = 42
CORPUS_PATH = ARTIFACTS_DIR / "name_corpus.csv"

# (name_a, name_b, "why they're linked") -- used only for cultural_similarity's
# sanity check. Deliberately differently-spelled pairs.
CULTURALLY_LINKED_PAIRS = [
    ("שרה", "רבקה", "biblical matriarchs"),
    ("רות", "נעמי", "Megillat Rut"),
    ("דוד", "שלמה", "father/son biblical kings"),
    ("אברהם", "יצחק", "father/son patriarchs"),
]
UNRELATED_CONTROL = "אלמוג"  # modern secular name, no biblical association

# (name_a, name_b) -- used only for written_similarity's sanity check.
SPELLING_SIMILAR_PAIRS = [("דוד", "דודי"), ("שרה", "שרון"), ("משה", "מיכאל")]


def _sim(embedder, a: str, b: str) -> float:
    va = embedder.encode([a])
    vb = embedder.encode([b])
    return float(cosine_similarity(va, vb)[0, 0])


def _sanity_check_written_similarity(embedder) -> None:
    print("\nSanity check -- cosine similarity of spelling-similar name pairs:")
    for a, b in SPELLING_SIMILAR_PAIRS:
        print(f"  sim({a!r}, {b!r}) = {_sim(embedder, a, b):.3f}")


def _sanity_check_cultural_similarity(embedder) -> None:
    print(
        "\nSanity check -- cosine similarity of culturally-linked (but "
        "differently-spelled) pairs vs. an unrelated control "
        f"({UNRELATED_CONTROL!r}):"
    )
    print(
        "NOTE: no ground-truth dataset exists for this. Success is a human "
        "judgment call -- see PLAN.md's 'Sanity check' section. If linked "
        "pairs aren't meaningfully more similar than their control "
        "comparisons, that's a genuine negative result on this modeling "
        "approach, not something to 'fix'."
    )
    for a, b, why in CULTURALLY_LINKED_PAIRS:
        linked = _sim(embedder, a, b)
        control_a = _sim(embedder, a, UNRELATED_CONTROL)
        control_b = _sim(embedder, b, UNRELATED_CONTROL)
        print(f"  [{why}]")
        print(f"    linked   sim({a!r}, {b!r}) = {linked:.3f}")
        print(f"    control  sim({a!r}, {UNRELATED_CONTROL!r}) = {control_a:.3f}")
        print(f"    control  sim({b!r}, {UNRELATED_CONTROL!r}) = {control_b:.3f}")


def _build_one(
    spec: ModelSpec,
    unique_names: list[str],
    status: PipelineStatus,
    background_corpus: list[str] | None = None,
) -> None:
    print(f"\n=== {spec.id} ({spec.display_name_he}) ===")
    status.step(f"building {spec.id}")
    model_dir = ARTIFACTS_DIR / spec.artifacts_subdir
    model_dir.mkdir(parents=True, exist_ok=True)

    embedder = spec.new_embedder(model_dir)
    if spec.id == "written_similarity" and background_corpus:
        # Fit the TF-IDF vectorizer's vocabulary/IDF weights against a much
        # larger, representative sample of Hebrew words instead of only the
        # ~20K names -- see NgramSvdEmbedder.fit_corpus and DATA_SOURCE.md.
        embedder.fit_corpus(unique_names, background_corpus=background_corpus)
    else:
        embedder.fit_corpus(unique_names)
    if spec.persisted_embedder:
        joblib.dump(embedder, model_dir / "embedder.joblib", compress=3)
        print(f"Wrote {model_dir / 'embedder.joblib'}")

    t0 = time.monotonic()
    if spec.persisted_embedder:
        vectors = embedder.encode(unique_names).astype(np.float32)
    else:
        # Pretrained model: batched ONNX inference over ~20K names takes
        # real minutes, not milliseconds -- report progress.
        vectors = _encode_with_progress(embedder, unique_names, status, spec.id)
    print(f"Encoded {len(unique_names)} names in {time.monotonic() - t0:.1f}s")

    np.savez_compressed(
        model_dir / "corpus_vectors.npz",
        names=np.array(unique_names, dtype=object),
        vectors=vectors,
    )
    print(f"Wrote corpus_vectors.npz (shape={vectors.shape}, dtype={vectors.dtype})")

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coords = pca.fit_transform(vectors)
    joblib.dump(pca, model_dir / "pca_projector.joblib", compress=3)
    print(
        f"Wrote pca_projector.joblib "
        f"(explained_variance_ratio={pca.explained_variance_ratio_})"
    )
    print(
        f"2D PCA coordinate range: "
        f"x=[{coords[:, 0].min():.2f}, {coords[:, 0].max():.2f}] "
        f"y=[{coords[:, 1].min():.2f}, {coords[:, 1].max():.2f}]"
    )

    if spec.id == "written_similarity":
        _sanity_check_written_similarity(embedder)
    elif spec.id == "cultural_similarity":
        _sanity_check_cultural_similarity(embedder)


def _encode_with_progress(embedder, names: list[str], status: PipelineStatus, model_id: str):
    batch_size = 64
    chunks = []
    total = len(names)
    for i in range(0, total, batch_size):
        batch = names[i : i + batch_size]
        chunks.append(embedder.encode(batch))
        done = min(i + batch_size, total)
        if (i // batch_size) % 10 == 0 or done == total:
            print(f"  encoded {done}/{total} names...")
            status.progress(model_id, done, total)
    return np.concatenate(chunks, axis=0).astype(np.float32)


def main() -> None:
    status = PipelineStatus("build_artifacts")
    status.step("loading corpus")
    corpus = pd.read_csv(CORPUS_PATH)
    unique_names = corpus["name"].drop_duplicates().tolist()
    print(f"Building artifacts for {len(unique_names)} unique name spellings")

    status.step("fetching background Hebrew word corpus")
    background_corpus = fetch_background_corpus()
    print(f"Fetched background corpus: {len(background_corpus)} Hebrew words")

    for spec in MODEL_REGISTRY.values():
        _build_one(spec, unique_names, status, background_corpus=background_corpus)

    status.done()


if __name__ == "__main__":
    main()
