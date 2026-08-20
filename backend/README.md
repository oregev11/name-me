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

These two commands are exactly what CI runs (see below) — if they pass locally, CI passes
for the same reason, not a different one.

## CI/CD

See the root [`README.md`](../README.md#cicd) for the repo-wide picture (both services,
the CI/CD relationship, `DEPLOYMENT_PLAN.md`). This section is the backend-specific detail:
what `.github/workflows/backend-ci.yml` actually does, step by step, and how it relates to
this service's deploy target.

### What triggers it

```yaml
on:
  push:
    branches: [main]
    paths: ["backend/**", ".github/workflows/backend-ci.yml"]
  pull_request:
    paths: ["backend/**", ".github/workflows/backend-ci.yml"]
```

Path-filtered on purpose: editing only `frontend/` never spins up this Python job. GitHub
evaluates the `paths` filter against the changed files in the push/PR, not the whole repo —
so a commit touching only `README.md` at the repo root, for instance, triggers *neither*
CI workflow (that top-level file isn't under either service's `paths`, which is why root
README edits don't need a CI run to "pass" — there's genuinely nothing to check).

### The steps, and why each one is there

`defaults.run.working-directory: backend` means every step below runs with `backend/` as
its cwd, so commands read exactly like running them by hand from this directory:

1. **`astral-sh/setup-uv@v3`** — installs `uv` on the runner (GitHub's images don't ship it).
2. **`uv python install`** — installs whatever Python version `pyproject.toml`'s
   `requires-python` (`>=3.12`) resolves to; keeps the runner's interpreter in sync with
   what's declared, rather than trusting whatever GitHub's image happens to preinstall.
3. **`uv sync --all-extras`** — installs dependencies. Easy to misread: `--all-extras`
   controls `[project.optional-dependencies]` (a concept this project doesn't use at all —
   there are none declared), **not** `[dependency-groups]`. So this step installs the
   default runtime deps + the `dev` group (`pytest`, `httpx`, `ruff`) and nothing else — the
   `export` group (torch/transformers/optimum, ~2GB+) and `notebook` group are never pulled
   in here, keeping CI fast and matching what actually ships (see `pyproject.toml`'s
   `[dependency-groups]` comments for why those two are opt-in).
4. **`uv run ruff check .`** — lint. Note there's **no static type-check step** for the
   backend (Python has no `tsc` equivalent wired up here — no `mypy`/`pyright` in CI). This
   is an honest gap, not an oversight to hide: Pydantic models give runtime validation at the
   API boundary (`schemas/search.py`), which covers the highest-value case (malformed
   requests), but internal type mistakes elsewhere aren't statically caught the way the
   frontend's `tsc -b` step catches them.
5. **`uv run pytest`** — the real correctness gate: `tests/` (unit tests for
   `corpus/loader.py`, `services/search_service.py`, the embedders) plus `tests/test_*.py`
   FastAPI `TestClient` integration tests that exercise `/api/search`, `/api/autocomplete`,
   `/api/health` end to end against the real committed artifacts (no mocked corpus) — these
   are the same tests, same artifacts, the `docker_smoke_test.sh` container-level check and
   local `uv run pytest` both exercise, just at three different layers (unit → in-process
   HTTP → real container).

### Known gap: 5 tests currently fail in CI, not just locally

`cultural_similarity/model_quantized.onnx` (~112MB) is excluded from git — see the root
README's [Memory footprint](../README.md#memory-footprint-why-this-matters-for-free-tier-hosting)
section and `DEPLOYMENT_PLAN.md` — which means the GitHub Actions runner's checkout is
missing it too, identically to a fresh local `git clone`. `tests/embedding/test_onnx_sentence.py`
(4 tests) and one case in `tests/test_search_service.py`
(`test_out_of_corpus_names_fall_back_to_the_live_embedder`) call the live ONNX encode path
directly and fail with `onnxruntime.capi.onnxruntime_pybind11_state.NoSuchFile`. Every other
test passes regardless (the precomputed `corpus_vectors.npz` for `cultural_similarity` *is*
committed, so in-corpus lookups — the common case — never touch the missing file). Until the
ONNX-hosting decision in `DEPLOYMENT_PLAN.md` is made and a download step is added to this
workflow (mirroring whatever the Dockerfile ends up doing), treat `backend-ci` as "passes
except those 5, which fail for a known, unrelated-to-your-change reason" rather than a clean
gate.

### CD: this workflow does not deploy anything

`backend-ci.yml` only tests — it has no `deploy` job. The actual deploy target (Render, via
`render.yaml` + `backend/Dockerfile`, `autoDeploy: true`) reacts to the same `git push`
independently, not *after* this workflow passes — see the root README's
[CI/CD](../README.md#cicd) section ("The gap") for why that's a known, currently-unclosed
loop, and `DEPLOYMENT_PLAN.md` for the actual deploy steps. `backend/scripts/docker_smoke_test.sh`
is the closest thing to a pre-deploy gate today — it's a manual step, not automated in CI.

## Manual ML sanity check

`notebooks/ml_sanity_check.ipynb` loads the real `nameme` package and real committed
artifacts (no reimplemented logic) for interactively comparing name pairs, running full
filtered searches, and visualizing results:

```bash
uv sync --group notebook
uv run jupyter lab notebooks/
```

See `notebooks/README.md`.

## API contract (what the frontend actually sends/receives)

See the root [`README.md`](../README.md#data-flow-one-search-request-end-to-end) for the
full sequence diagram of a search request end to end. The short version:

| Endpoint | Method | Request body / params | Response |
|---|---|---|---|
| `/api/search` | POST | `{liked_names: string[], top_k?: number (default 20), model?: "written_similarity"\|"cultural_similarity", sex?: "any"\|"M"\|"F", sector?: "any"\|"Jewish"\|"Muslim"\|"Christian-Arab"\|"Druze", popularity?: "all"\|"top_10_percent"\|"top_90_percent", sort?: "similar"\|"dissimilar", year_min?: number\|null, year_max?: number\|null}` | `{liked: NamePoint[], suggestions: SuggestedName[]}` |
| `/api/autocomplete` | GET | `?q=<prefix>&limit=<n>` | `{matches: string[]}` |
| `/api/health` | GET | — | `{status, corpus_size, models: ModelInfo[], year_min, year_max}` |

`top_k`'s default of 20 matches the "find the middle point, then the 20 closest names"
brief — the middle point is the liked names' centroid, computed in
`search_service.search()`. `popularity`'s percentile thresholds are precomputed once at
startup (`CorpusStore.__post_init__`, `total.rank(pct=True)`) so filtering is a cheap
threshold check per candidate, not a re-rank. `sex`+`sector` are checked together, not
independently — `CorpusStore.matches_sex_sector()` requires a real `(sex, sector)` row for
the name, so e.g. `sex=F, sector=Jewish` won't match a name whose only female usage is
Muslim. `sort: "dissimilar"` reverses which end of the same similarity ranking gets walked
(farthest first instead of closest first) — useful for finding names that deliberately
don't resemble your liked names. `year_min`/`year_max` (both `null` by default = no filter)
restrict candidates to names with evidence of use in that span, via a supplementary
per-year breakdown (`name_years.csv`) that only covers a subset of the corpus — see
`DATA_SOURCE.md` and `CorpusStore.year_filtered_meta()`. `/api/health`'s `year_min`/
`year_max` report the dataset's actual span (1949–2024) so the frontend can size its
year-range slider correctly.

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
- The year-range filter resolves its metadata source ONCE per request
  (`_resolve_meta_source`), not per candidate: the full (all-years) `CorpusStore` metadata
  when no year filter narrows the range, or a fresh `year_filtered_meta()` dict (one pandas
  groupby over `name_years.csv`) otherwise. The ranking loop then does plain `dict.get()`
  lookups against whichever was resolved — a name absent from a year-filtered dict means "no
  evidence in that range", not "fall back to the full corpus".
- Search is stateless: `POST /api/search` takes the full `liked_names` list each call; the
  frontend owns the "refine" loop by adding/removing names (or switching models) and
  resubmitting.
