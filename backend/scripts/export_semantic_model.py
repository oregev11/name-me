"""One-time offline export of the pretrained multilingual sentence-transformer
used by the `cultural_similarity` embedder, to ONNX + int8 dynamic
quantization.

EXPERIMENTAL: this embeds the bare Hebrew name string through a
general-purpose multilingual sentence encoder (no meaning/etymology text
dataset exists at adequate scale+license for this corpus -- see PLAN.md).
There is no confirmed prior art that this technique captures biblical/
cultural association for short given names -- see build_artifacts.py's
sanity check and treat its output as a soft, subjective signal, not a
guarantee.

Dependencies (torch, transformers, optimum) are EXPORT-ONLY: declared in the
`export` uv dependency group, never installed in the deployed image. Run
this locally whenever the base model changes; commit the resulting .onnx +
tokenizer files under artifacts/cultural_similarity/ the same way the other
embedder's artifacts are committed.

Usage:
    uv sync --group export
    uv run --group export python scripts/export_semantic_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline_status import PipelineStatus  # noqa: E402

from nameme.config import ARTIFACTS_DIR  # noqa: E402

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
OUTPUT_DIR = ARTIFACTS_DIR / "cultural_similarity"


def main() -> None:
    status = PipelineStatus("export_semantic_model")

    # Imported lazily: these are export-only deps (the `export` uv group),
    # not installed by a plain `uv sync` / the deployed image.
    status.step(f"downloading + exporting {MODEL_ID} to ONNX")
    from optimum.onnxruntime import ORTModelForFeatureExtraction, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from transformers import AutoTokenizer

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    model = ORTModelForFeatureExtraction.from_pretrained(MODEL_ID, export=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    fp32_path = OUTPUT_DIR / "model.onnx"
    fp32_size = fp32_path.stat().st_size if fp32_path.exists() else None
    if fp32_size:
        print(f"fp32 ONNX model size: {fp32_size / 1e6:.1f} MB")

    status.step("quantizing to int8")
    quantizer = ORTQuantizer.from_pretrained(OUTPUT_DIR)
    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=OUTPUT_DIR, quantization_config=qconfig)

    quantized_path = OUTPUT_DIR / "model_quantized.onnx"
    if quantized_path.exists():
        quantized_size = quantized_path.stat().st_size
        print(f"int8 quantized ONNX model size: {quantized_size / 1e6:.1f} MB")
        if fp32_size:
            reduction = 100 * (1 - quantized_size / fp32_size)
            print(f"Size reduction from quantization: {reduction:.0f}%")
            print(
                "NOTE: don't assume ~75% is typical for this model -- its "
                "parameters are dominated by a large multilingual embedding "
                "table that MatMul-targeted quantization may not shrink as "
                "effectively as it shrinks dense layers. This is the real "
                "measured number above."
            )
    else:
        print("WARNING: quantized model file not found where expected")

    # Remove the fp32 model so we don't commit both to git -- only the
    # quantized graph ships.
    if fp32_path.exists():
        fp32_path.unlink()
        print(f"Removed {fp32_path} (keeping only the quantized model)")

    status.step("sanity check")
    _sanity_check(OUTPUT_DIR)

    status.done()
    print(f"\nDone. Artifacts written to {OUTPUT_DIR}")
    print("Next: uv run python scripts/build_artifacts.py")


def _sanity_check(model_dir: Path) -> None:
    from sklearn.metrics.pairwise import cosine_similarity

    from nameme.embedding.onnx_sentence import OnnxSentenceEmbedder

    embedder = OnnxSentenceEmbedder(model_dir)
    embedder.fit_corpus([])  # warmup

    pairs = [
        ("שרה", "רבקה", "biblical matriarchs"),
        ("רות", "נעמי", "Megillat Rut"),
        ("דוד", "שלמה", "father/son biblical kings"),
        ("אברהם", "יצחק", "father/son patriarchs"),
    ]
    control = "אלמוג"

    print(
        "\nSanity check -- cosine similarity of culturally-linked (but "
        f"differently-spelled) pairs vs. an unrelated control ({control!r}):"
    )
    print(
        "NOTE: no ground-truth dataset exists for this. See PLAN.md's "
        "'Sanity check' section for how to interpret this."
    )
    for a, b, why in pairs:
        va, vb, vc = embedder.encode([a]), embedder.encode([b]), embedder.encode([control])
        linked = float(cosine_similarity(va, vb)[0, 0])
        ca = float(cosine_similarity(va, vc)[0, 0])
        cb = float(cosine_similarity(vb, vc)[0, 0])
        print(f"  [{why}] sim({a!r},{b!r})={linked:.3f}  vs control: {ca:.3f}, {cb:.3f}")


if __name__ == "__main__":
    main()
