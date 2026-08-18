# name-me backend

FastAPI service that serves Hebrew name embeddings + similarity search for the name-me app.

## Local development

```bash
uv sync
cp .env.example .env   # adjust CORS_ORIGINS if needed
uv run uvicorn nameme.main:app --reload
```

Then open http://127.0.0.1:8000/docs for interactive API docs.

## Rebuilding the ML artifacts

Every model's corpus vectors, fitted embedder/exported model, and PCA projector are
committed under `src/nameme/artifacts/<model_id>/` so the service starts with no offline
dependencies at runtime. To rebuild them:

```bash
uv run python scripts/build_corpus.py      # only needed if the raw data source changed

# only needed if you're re-exporting the cultural_similarity base model (rare):
uv sync --group export
uv run --group export python scripts/export_semantic_model.py

uv run python scripts/build_artifacts.py   # refits/refreshes BOTH models + their PCA projectors
```

Open `scripts/pipeline_status.html` in a browser while any of these run for live progress
(self-contained, no server needed — see `scripts/pipeline_status.py`).

See `../DATA_SOURCE.md` for data provenance and how to refresh the source, and the root
[`README.md`](../README.md#offline-artifact-pipeline) for the pipeline diagram.

## Testing & linting

```bash
uv run pytest
uv run ruff check .
```

## API contract (what the frontend actually sends/receives)

See the root [`README.md`](../README.md#data-flow-one-search-request-end-to-end) for the
full sequence diagram of a search request end to end. The short version:

| Endpoint | Method | Request body / params | Response |
|---|---|---|---|
| `/api/search` | POST | `{liked_names: string[], top_k?: number (default 20), model?: "written_similarity"\|"cultural_similarity", sex?: "any"\|"M"\|"F", sector?: "any"\|"Jewish"\|"Muslim"\|"Christian-Arab"\|"Druze", popularity?: "all"\|"top_10_percent"\|"top_90_percent", sort?: "similar"\|"dissimilar"}` | `{liked: NamePoint[], suggestions: SuggestedName[]}` |
| `/api/autocomplete` | GET | `?q=<prefix>&limit=<n>` | `{matches: string[]}` |
| `/api/health` | GET | — | `{status, corpus_size, models: ModelInfo[]}` |

`top_k`'s default of 20 matches the "find the middle point, then the 20 closest names"
brief — the middle point is the liked names' centroid, computed in
`search_service.search()`. `popularity`'s percentile thresholds are precomputed once at
startup (`CorpusStore.__post_init__`, `total.rank(pct=True)`) so filtering is a cheap
threshold check per candidate, not a re-rank. `sex`+`sector` are checked together, not
independently — `CorpusStore.matches_sex_sector()` requires a real `(sex, sector)` row for
the name, so e.g. `sex=F, sector=Jewish` won't match a name whose only female usage is
Muslim. `sort: "dissimilar"` reverses which end of the same similarity ranking gets walked
(farthest first instead of closest first) — useful for finding names that deliberately
don't resemble your liked names.

`NamePoint = {name, x, y}`; `SuggestedName` adds `similarity` (cosine, in `[-1,1]` though
`written_similarity`'s non-negative TF-IDF vectors keep it in `[0,1]` in practice), `sex`
(dominant sex, `"M"`/`"F"` — a name can still match a `sex` filter for its *non-dominant*
sex if it has real rows there, see above), `sectors` (every sector this name has any row
in, not just the dominant one — this field is exhaustive, unlike `sex`), `popularity` (raw
CBS count, summed across all sex+sector rows). All schemas are Pydantic models in
`src/nameme/schemas/search.py` — the frontend's `src/types/api.ts` mirrors them by hand, so
if you change one, change the other. Full interactive docs (auto-generated from the same
Pydantic models) are always available at `/docs` when the server is running.

`liked_names` is validated server-side to Hebrew-script strings only (see
`HEBREW_NAME_RE` in `schemas/search.py`) — the frontend mirrors this check client-side in
`NameInput.tsx` so invalid input never round-trips to the server, but the server-side check
is the one that actually matters for correctness.

## Architecture notes

- `embedding/base.py` defines the `NameEmbedder` interface (`fit_corpus`, `encode`, `dim`).
  Two implementations exist today, both registered in `embedding/registry.py`'s
  `MODEL_REGISTRY` and served **simultaneously**:
  - `embedding/ngram_svd.py` (`written_similarity`) — character n-gram TF-IDF + TruncatedSVD.
    The vectorizer's vocabulary/IDF fit against a large background Hebrew word corpus (see
    `scripts/background_corpus.py`, `DATA_SOURCE.md`) rather than only the names, so
    substring rarity reflects real Hebrew usage; SVD still fits on the names' own vectors.
  - `embedding/onnx_sentence.py` (`cultural_similarity`) — a pretrained multilingual
    sentence-transformer served via `onnxruntime` (no torch/transformers at runtime — those
    are export-only, see the `export` dependency group in `pyproject.toml` and
    `scripts/export_semantic_model.py`).

  To add a third technique: implement the interface, add one `ModelSpec` entry to
  `MODEL_REGISTRY`, re-run `build_artifacts.py` — no API/schema changes needed beyond
  extending the `SearchRequest.model` `Literal` and the frontend's model toggle.
- `corpus/loader.py`'s `CorpusStore` holds shared corpus metadata (name/sex/popularity) plus
  one `ModelStore` per registered model (its own vectors + fitted PCA). Each model's 2D PCA
  is fit **once**, offline, on that model's full corpus vectors and only ever
  `.transform()`-ed at request time, so each model's scatter-plot coordinate space stays
  stable across repeated searches in a session — but the two models' coordinate spaces are
  unrelated to each other (switching models is expected to visually "jump").
- `services/search_service.py` checks each liked name against the model's precomputed
  `vector_for(name)` first and only calls the live embedder for names outside the corpus —
  see the root README's "Memory footprint" section for why this matters for
  `cultural_similarity` specifically.
- Search is stateless: `POST /api/search` takes the full `liked_names` list each call; the
  frontend owns the "refine" loop by adding/removing names (or switching models) and
  resubmitting.
