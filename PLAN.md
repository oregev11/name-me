# Hebrew Baby Name Recommender — Implementation Plan

## Context

`idea.md` describes a portfolio project: a website that helps parents choose a Hebrew baby
name using ML with a human-in-the-loop workflow — enter a few liked names, get similar
names via embeddings + cosine similarity, see everything on a 2D (PCA) scatter plot, and
refine by adding/removing names. The project directory is currently empty (just `idea.md`,
no git repo). This plan lays out a from-scratch, industry-standard build.

Decisions locked in with the user during scoping:
- **Stack**: Python backend + React frontend (separate services).
- **Hosting**: free-tier cloud hosting, publicly accessible (portfolio requirement).
- **Human-in-the-loop scope (MVP)**: stateless re-search loop only — add/remove liked
  names client-side, re-run search. No feedback-weighted ranking, no cross-session learning.
- **Auth/persistence**: fully anonymous, no accounts, no database.
- **Data source (MVP)**: CBS/babynamesIL only — no scraping, no meaning/etymology data.
- **Embedding (MVP)**: simple character n-gram vectors, explicitly behind a swappable
  interface so a fancier model (e.g. Name2Vec-style Doc2Vec) can replace it later without
  touching the API or frontend contract.

Research grounding (done): the `aviezerl/babynamesIL` GitHub repo (CC0, wraps official
Israel CBS Release 391/2025 data) exposes a ready-to-use CSV directly —
`data-raw/babynamesIL_totals.csv` (`sector,sex,name,total`) — so no R/rpy2/Excel parsing
is needed. No existing open-source app does embedding+cosine+PCA for name recommendation,
so this is original UX; generic embedding-visualization practice (fit PCA once globally,
project new points into that fixed space) applies.

## Repo layout

```
name-me/
├── README.md, LICENSE (MIT for code), DATA_SOURCE.md (CC0 attribution + pinned source SHA)
├── .gitignore
├── .github/workflows/{backend-ci.yml, frontend-ci.yml}
├── backend/
│   ├── pyproject.toml (uv), Dockerfile, README.md
│   ├── src/nameme/
│   │   ├── main.py            # FastAPI app factory, lifespan loads artifacts once
│   │   ├── config.py          # pydantic-settings (EMBEDDER_TYPE, CORS_ORIGINS, etc.)
│   │   ├── api/routes_search.py, routes_autocomplete.py, routes_health.py
│   │   ├── schemas/search.py  # Pydantic request/response models
│   │   ├── embedding/base.py, ngram_svd.py, factory.py
│   │   ├── corpus/loader.py
│   │   ├── services/search_service.py, projection_service.py
│   │   └── artifacts/         # generated, committed: name_corpus.csv, embedder.joblib,
│   │                          # corpus_vectors.npz, pca_projector.joblib
│   ├── scripts/build_corpus.py, build_artifacts.py
│   └── tests/ (pytest + FastAPI TestClient)
└── frontend/
    ├── package.json (Vite + React + TypeScript), .env.example
    ├── src/
    │   ├── api/client.ts (reads VITE_API_BASE_URL)
    │   ├── types/api.ts
    │   ├── components/NameInput.tsx, LikedNameChips.tsx, ScatterChart.tsx,
    │   │   SuggestionsList.tsx, Layout.tsx
    │   └── hooks/useNameSearch.ts
    └── tests/ (Vitest + React Testing Library)
```

## Data pipeline

1. **`backend/scripts/build_corpus.py`** (one-time, offline, output committed to repo):
   - Fetch `babynamesIL_totals.csv` from a **pinned commit SHA** on `aviezerl/babynamesIL`
     (not `main`, to avoid drift) via `pandas.read_csv(url)`.
   - Aggregate to one row per `(name, sex)` (sum across `sector`); keep both sex rows if a
     name is used by both rather than collapsing.
   - Filter non-Hebrew-script anomalies via a Hebrew Unicode range check.
   - Output `backend/src/nameme/artifacts/name_corpus.csv` with columns `name, sex, total`.
   - Sanity check: spot-check top names by `total` (e.g. `שרה`, `דוד`, `יוסף` should appear).
   - Commit the derived CSV into the repo — small (low thousands of rows), makes the Docker
     build fully offline/reproducible, avoids depending on the third-party URL at deploy time.

2. **`backend/scripts/build_artifacts.py`** (re-run when embedder or corpus changes):
   - Fit the configured `NameEmbedder` on the corpus names, persist via `joblib`.
   - Encode the full corpus, save `corpus_vectors.npz` (names + vectors).
   - Fit a **global** 2D `sklearn.decomposition.PCA` on corpus vectors once, persist it —
     this is what keeps the scatter plot's coordinate space stable across refine calls
     (never re-fit PCA per request; only `.transform()` new points into it).
   - Fixed `random_state=42` throughout for reproducibility.

All four artifacts are committed under `backend/src/nameme/artifacts/` and shipped in the
Docker image — no external object storage needed at this scale.

## Embedding module (swappable by design)

`embedding/base.py` defines a `NameEmbedder` Protocol: `fit_corpus(names)`, `encode(names)
-> np.ndarray`, `dim` property. `embedding/ngram_svd.py` is the MVP implementation: a
`sklearn.Pipeline` of `TfidfVectorizer(analyzer="char_wb", ngram_range=(2,3))` →
`TruncatedSVD(n_components=100)`, which naturally handles out-of-vocabulary names since
n-grams generalize from substrings. `embedding/factory.py` reads `EMBEDDER_TYPE` from
config and returns the right implementation. **To upgrade later** (e.g. to a Name2Vec-style
model): add a new module conforming to the same Protocol, register it in the factory,
re-run `build_artifacts.py`, redeploy — no API/schema/frontend changes required.

## Backend API (FastAPI)

Confirmed choice: async, auto OpenAPI docs (nice portfolio touch — `/docs`), first-class
Pydantic integration, the current standard for Python ML-serving APIs.

- `POST /api/search` — `{liked_names: [str], top_k?: int}` → `{liked: NamePoint[],
  suggestions: SuggestedName[]}`. Logic: encode liked names → centroid vector → cosine
  similarity (`sklearn.metrics.pairwise.cosine_similarity`) against precomputed corpus
  vectors → top-K excluding already-liked → project all points into 2D via the **pre-fit**
  global PCA.
- `GET /api/autocomplete?q=<prefix>&limit=10` — plain in-memory substring/prefix match over
  the corpus (no ML), for the name-entry box.
- `GET /api/health` — status + corpus size + active embedder type, used by Render health
  checks.
- Artifacts loaded once at startup via FastAPI `lifespan`, not per-request.
- Deps via `uv` + `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `pydantic-settings`,
  `scikit-learn`, `numpy`, `pandas`, `joblib`; dev: `pytest`, `httpx`, `ruff`.
- Tests: `pytest` + FastAPI `TestClient`, loading real artifacts in a session-scoped
  fixture (fast at this corpus size) — health check, search returns descending similarity
  scores in `[0,1]`, autocomplete matches, validation error on empty `liked_names`.

## Frontend (React + Vite + TypeScript)

Vite is the current standard React scaffold; TypeScript for portfolio code-quality signal.

- **Charting**: Recharts (`ScatterChart`/`Scatter`) — SVG-based, handles a few dozen points
  easily, widely recognized library, supports two styled series (liked vs. suggested) with
  a custom tooltip showing name + similarity.
- `NameInput.tsx`: RTL (`dir="rtl"`) input with debounced autocomplete against
  `/api/autocomplete`; selecting/entering a name adds it as a chip.
- `LikedNameChips.tsx`: removable chips — the core refine interaction.
- `ScatterChart.tsx`: renders liked vs. suggested points distinctly, custom tooltip.
- `SuggestionsList.tsx`: ranked list beside/below the chart, each row has an "add to liked"
  button to pull a suggestion into the next search — closes the human-in-the-loop.
- `useNameSearch.ts`: owns `likedNames` state, calls `POST /api/search` (explicit "Search"
  button rather than search-on-every-keystroke, for predictability).
- No state library needed — local state is sufficient at this scope.
- `VITE_API_BASE_URL` env var (`.env.example` committed, `.env` gitignored) for the API base.
- Lint/format: ESLint (typescript-eslint + react-hooks) + Prettier.
- Tests: Vitest + React Testing Library — a couple of component tests (chip add on select,
  scatter renders expected point count from mock props).

## Deployment

- **Backend → Render**, Docker-based web service. Multi-stage `Dockerfile`
  (`python:3.12-slim`, `uv sync --frozen`, copy `src/` including committed `artifacts/`),
  `uvicorn nameme.main:app --host 0.0.0.0 --port $PORT`, health check on `/api/health`.
- **Frontend → Vercel**, static Vite build, zero-config detection, free tier, preview
  deploys per PR.
- **CORS**: `CORSMiddleware` with allowed origins from a `CORS_ORIGINS` env var (prod
  Vercel origin + `http://localhost:5173` for dev).
- **Known trade-off, called out explicitly**: Render's free tier spins down after ~15 min
  idle, ~30–60s cold start on the next request. Mitigate with a friendly "waking up the
  model server…" loading state in the frontend rather than a bare spinner; note in the
  README. An optional future enhancement (not MVP) is a scheduled GitHub Actions ping to
  `/api/health` to keep it warm.

## Repo hygiene / CI

- `git init`, initial commit once backend+frontend skeletons exist.
- Root `README.md`: description, local dev instructions for both services, deployed URL,
  and a plain-language "how the ML works" section (n-gram + SVD + cosine + PCA) — good
  portfolio content.
- `LICENSE` (MIT for code) + `DATA_SOURCE.md` (CC0 attribution to `aviezerl/babynamesIL` +
  CBS Release 391/2025, with the pinned source commit SHA used for `build_corpus.py`).
- `.gitignore`: standard Python/Node exclusions, but **do not** ignore
  `backend/src/nameme/artifacts/*` — those are deliberately committed.
- GitHub Actions: `backend-ci.yml` (`uv sync`, `ruff check`, `pytest` on `backend/**`
  changes), `frontend-ci.yml` (`npm ci`, `eslint`, `vitest run`, `npm run build` on
  `frontend/**` changes).

## Suggested build order

1. Data pipeline: run `build_corpus.py`, verify + commit `name_corpus.csv` + `DATA_SOURCE.md`.
2. Embedding module + `build_artifacts.py`; sanity-check similar names cluster sensibly and
   PCA output looks visually reasonable (manual check, no committed notebook needed).
3. Backend API + full pytest suite green + manual `/docs` check.
4. Frontend built against mocked `SearchResponse` JSON first (de-risks UI polish
   independent of backend correctness) — RTL input, chips, Recharts scatter.
5. Wire frontend to the real backend; handle loading/error states including the cold-start
   message; verify the full add/remove-refine loop end to end locally.
6. Deploy backend (Render) + frontend (Vercel); wire `CORS_ORIGINS` / `VITE_API_BASE_URL`;
   smoke-test the public URL.
7. Add CI workflows, finish README with real screenshots + deployed link, final lint pass.

## Open risks (flagged, not blockers)

- **Third-party data source stability**: the CBS CSV is fetched from a pinned commit on
  someone else's GitHub repo — a manual, occasional-refresh step, not an automated
  pipeline. Mitigated by committing our own derived corpus and pinning the SHA.
- **Name/sex ambiguity**: a few names appear under both sexes in CBS data; kept as separate
  `(name, sex)` rows — decide during implementation whether autocomplete should dedupe by
  name text alone.
- **Out-of-vocabulary/non-Hebrew input**: the n-gram embedder returns *a* vector for any
  input, but results are meaningless for garbage/non-Hebrew text — add a Hebrew Unicode
  range validator on `SearchRequest.liked_names` and mirror it in the frontend input.
- **Data recency**: CBS Release 391/2025 covers through 2024, no auto-refresh — fine for an
  MVP portfolio piece, worth a one-line README note.

## Verification

- Backend: `cd backend && uv sync && pytest` all green; `ruff check .` clean; run
  `uvicorn nameme.main:app --reload` locally and manually exercise `/docs`, POST a couple
  of real Hebrew names to `/api/search`, confirm descending similarity scores and sane 2D
  coordinates.
- Frontend: `cd frontend && npm ci && npm run test && npm run build`; run `npm run dev`
  against the local backend, walk through the full flow — enter names, see scatter +
  suggestions, add a suggestion to liked, remove a liked name, re-search.
- End-to-end: after deploying, load the public Vercel URL fresh (simulating cold start),
  confirm the loading message appears and the app becomes usable within ~60s, then run the
  same manual flow as above against production.

---

# Phase 2: Second model — "cultural_similarity"

**Status of Phase 1 above**: fully implemented, tested, committed (`db83632`), and verified
end-to-end with a headless-browser smoke test. This phase extends that working MVP — it does
not replace anything above.

**Status of Phase 2 (this section): DONE.** Both models implemented, tested (22 backend +
8 frontend tests, all passing; 1 backend test intentionally `xfail(strict=False)` and
currently xpassing), verified end-to-end in a real browser including the model toggle, and
the RAM risk flagged going in was measured, addressed (lazy-loading + corpus-lookup-first),
and re-measured. Not yet committed to git or deployed — see the end of this document for
what's left.

## Process requirements from CLAUDE.md (repo root, found this session — not previously known)

A project-level `CLAUDE.md` exists with standing instructions that apply from here on:

- **README updated at every step**, over-explaining especially the frontend-backend
  interface, with the full UI→backend→UI data flow explained and illustrated with **mermaid
  diagrams** (must render correctly in VS Code's markdown preview — standard ```mermaid
  fences), plus one-liner commands to run the whole process.
- **Plans are saved as a `*.md` file in the repo itself** — hence this file.
- **Pipelines get a dynamic HTML status-monitoring page** — applies here to the offline
  artifact-build pipeline (`build_corpus.py` → `export_semantic_model.py` →
  `build_artifacts.py`), since the ONNX corpus-encoding step takes multiple minutes.
- Python commands should default to `/home/ofir/.pyenv/versions/zoomcampEnv/` — judgment
  call: the project's `uv`-managed venv (already working, isolated, industry-standard) stays
  for the project itself; this env is used for genuinely ad-hoc one-off Python commands
  outside the project's own environment.
- Always test new features (already the working pattern).
- Keep code clean/neat/minimal (already the working pattern).

**Consequently, the build order below now starts with a documentation pass** (bringing the
existing Phase 1 README up to this standard, since it predates discovering CLAUDE.md) before
any new code, and README updates are folded into each subsequent step rather than done once
at the end.

## Revised build order

1. **Documentation pass first**: rewrite root `README.md` and `backend/README.md` /
   `frontend/README.md` to over-explain the frontend-backend interface — a mermaid sequence
   diagram of the UI→backend→UI data flow for a search request (name typed → autocomplete →
   liked chip → `POST /api/search` → centroid/cosine/PCA → response → chart+list render →
   refine loop), a mermaid diagram of the offline artifact pipeline, and one-liner commands
   for: local dev (both services), running tests, rebuilding artifacts.
2. Embedder + registry + loader changes (backend section below), with README's data-flow
   section updated to reflect the two-model reality as soon as the API contract changes.
3. Offline export/build pipeline, **including the pipeline status HTML page** (see below),
   run it, verify artifacts + sanity checks, update README with real output.
4. API + schema changes, backend tests.
5. Frontend `ModelToggle` + wiring, frontend tests, update README screenshots/description.
6. RAM verification, update README with the real measured number and any resulting decision.

## Pipeline status monitor (new requirement)

A small, dependency-free HTML page (e.g. `backend/scripts/pipeline_status.html`) that the
export/build scripts write a status JSON to (e.g. `backend/scripts/.pipeline_status.json`:
current step, progress within the long ONNX-encoding step, elapsed time, last sanity-check
output) and which polls that file locally (plain `fetch()` of the relative JSON file on an
interval, or a meta-refresh if opened via `file://`) to show live progress — opened directly
in a browser or VS Code's preview while `build_artifacts.py` runs. No server process needed;
this is a supervision aid for a multi-minute local script, not a deployed feature.

## Context

The current (only) model — now named **`written_similarity`** — is a char n-gram TF-IDF +
SVD pipeline. It captures pure spelling similarity ("דוד" ~ "דודי" because they share
substrings) but completely misses cultural/religious/etymological association: names that
are meaningfully related (e.g. biblical matriarchs) but spelled nothing alike currently
never surface as similar. The user wants a second model, **`cultural_similarity`**, that
finds relatedness "based on the Hebrew language as context" — and wants **both models live
simultaneously** in the running app, with the user picking per-search which one to use
(not a redeploy-time swap like today's single-`EMBEDDER_TYPE` config).

Research (see conversation) found no confirmed prior art for embedding bare Hebrew given
names for cultural similarity specifically. The chosen approach — embedding the bare name
string through a pretrained multilingual sentence-transformer — is therefore a genuine,
labeled experiment, not an established technique. No adequately-sized, permissively-licensed
Hebrew name-meaning/etymology dataset exists (Wiktionary only covers ~283 names, CC BY-SA),
so meaning-text embedding was ruled out for now; the bare-name-string approach is the honest
scope-appropriate choice, explicitly flagged as unproven in code, tests, and the sanity
check below.

Self-hosting a full torch+transformers model at runtime is high-risk on the target free-tier
host (~512MB RAM) — reported naive image sizes of 5.9–8GB. The chosen mitigation: export the
model to ONNX **offline** (torch/transformers/optimum as dev-only tooling, never shipped),
optionally int8-quantized, and serve it at runtime with only `onnxruntime` + the standalone
`tokenizers` package — no torch/transformers in the deployed image. RAM is still a real,
unverified risk once both models load simultaneously (rough estimate 300–650MB); the user
has chosen to build it and measure actual RAM locally before deciding on a deploy tier,
rather than pre-emptively downgrading model quality. The user has also accepted committing
the resulting ~100–150MB ONNX file directly to git (no git-lfs) as a known, permanent repo
size increase.

## Chosen model

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0, 118M params,
384-dim output). Chosen over AlephBERT/HeBERT/DictaBERT (Hebrew-specific MLM models with no
confirmed precedent for word/name-level embedding quality, and HeBERT's license is
unconfirmed) and multilingual-e5-small (awkward `"query: "/"passage: "` prefix convention,
unconfirmed/conflicting size reports) — MiniLM is the best-documented, most established
option for this use case.

## Artifacts layout (new)

```
backend/src/nameme/artifacts/
├── name_corpus.csv                       # unchanged, shared across models
├── written_similarity/                   # existing 3 files, MOVED here from artifacts/ root
│   ├── embedder.joblib
│   ├── corpus_vectors.npz
│   └── pca_projector.joblib
└── cultural_similarity/                  # new
    ├── model_quantized.onnx              # int8 dynamic-quantized ONNX graph
    ├── tokenizer.json / tokenizer_config.json / special_tokens_map.json
    ├── corpus_vectors.npz                # 19,882 x 384 float32, compressed
    └── pca_projector.joblib              # own PCA, fit independently — never shared
```

Migrate the existing top-level artifact files into `written_similarity/` as part of this
work; verify their content is byte-for-byte/numerically unchanged (same `RANDOM_STATE=42`)
before removing the old top-level copies.

## Backend changes

- **`pyproject.toml`**: add `onnxruntime`, `tokenizers` as core runtime deps. Add a new
  **non-default** `export` dependency group (`torch`, `transformers`, `optimum[onnxruntime]`)
  — `uv sync` / `uv sync --frozen --no-dev` (what `Dockerfile` runs) must NOT install it;
  only `uv sync --group export` does, for the one-time offline export. Regenerate and commit
  `uv.lock`.
- **`embedding/onnx_sentence.py`** (new): `OnnxSentenceEmbedder` implementing the existing
  `NameEmbedder` protocol via `onnxruntime.InferenceSession` + `tokenizers.Tokenizer` —
  tokenize → run ONNX graph → mean-pool over `last_hidden_state` using the attention mask →
  L2-normalize (replicating what `sentence-transformers` does internally, since raw ONNX
  export only gives the unpooled hidden states). `fit_corpus()` is a no-op warmup (nothing to
  fit for a pretrained model). Batches internally (`batch_size=64`) since `build_artifacts.py`
  will call `encode()` on the full ~20K-name corpus at once.
- **`embedding/registry.py`** (new, replaces `factory.py`): a `MODEL_REGISTRY: dict[str,
  ModelSpec]` describing both models — id, Hebrew display name, artifacts subdirectory,
  vector dim, whether the embedder is `joblib`-persisted (`written_similarity`) or a
  stateless wrapper around already-exported files (`cultural_similarity`), and a constructor
  closure. This lets `build_artifacts.py` and the runtime loader share one loop over
  `MODEL_REGISTRY.values()` instead of branching per model.
- **`config.py`**: drop `embedder_type`/`embedder_dim` (no longer describe a single global
  choice); `ARTIFACTS_DIR` stays as the root, `MODEL_REGISTRY` supplies subdirectories.
- **`corpus/loader.py`**: introduce `ModelStore` (per-model: `unique_names`, `vectors`,
  `embedder`, `pca`, name→row lookup). `CorpusStore` becomes `names_df` + `meta_for` +
  `names_by_popularity` (unchanged, shared/model-independent) + `models: dict[str,
  ModelStore]` + a `.model(model_id)` lookup. `load_corpus_store(artifacts_dir)` now loads
  every model in `MODEL_REGISTRY` at startup (no more `embedder_type` parameter).
- **`schemas/search.py`**: `SearchRequest` gains `model: Literal["written_similarity",
  "cultural_similarity"] = "written_similarity"` (default preserves current behavior).
  `HealthResponse` gains `models: list[ModelInfo]` (id, display name, dim, corpus vector
  count) replacing the old single `embedder_type: str` — lets `/api/health` confirm both
  models actually loaded post-deploy.
- **`services/search_service.py`**: `search()` gains a `model_id` parameter, resolves
  `store.model(model_id)` first, otherwise unchanged (centroid → cosine similarity → top-K →
  PCA projection, per-model vectors/PCA).
- **`routes_search.py`**: passes `body.model` through. **`routes_autocomplete.py`: no
  changes** — it's pure corpus-name string matching, not model-dependent, confirmed from the
  existing code. **`routes_health.py`**: reports all loaded models.
- **`scripts/export_semantic_model.py`** (new): one-time offline script — `uv sync --group
  export` then run it. Downloads the base model via `optimum`'s `ORTModelForFeatureExtraction`
  + `AutoTokenizer`, exports to ONNX, applies dynamic int8 quantization
  (`ORTQuantizer`/`AutoQuantizationConfig.avx2`), writes files into
  `artifacts/cultural_similarity/`. **Prints the actual file size before/after
  quantization — do not assume the commonly-cited ~75% reduction holds**, since this
  model's parameters are dominated by a large multilingual embedding table that
  `MatMul`-targeted quantization may not shrink as effectively. Runs the sanity check
  (below) at the end. Not run in CI (needs network + heavy deps).
- **`scripts/build_artifacts.py`**: rewritten as a loop over `MODEL_REGISTRY` — for
  `written_similarity`, unchanged logic (fit TF-IDF+SVD, encode, fit PCA); for
  `cultural_similarity`, loads the already-exported ONNX model via `OnnxSentenceEmbedder`,
  encodes the full corpus (one-time, offline; print progress — this takes real minutes,
  unlike the near-instant TF-IDF fit), fits its own independent 2D PCA. Requires
  `export_semantic_model.py` to have been run first.
- **Dockerfile / CI**: no structural changes needed — `export` is non-default so the existing
  `uv sync --frozen --no-dev` in `Dockerfile` and `uv sync --all-extras` in
  `backend-ci.yml` continue to exclude torch/transformers automatically. Artifacts under
  `src/nameme/artifacts/` are already copied into the image regardless of subdirectory
  structure.

## Frontend changes

- **`types/api.ts`**: add `ModelId` type, `ModelInfo`, update `HealthResponse`.
- **`api/client.ts`**: `searchNames(likedNames, model, topK)` — `model` now required.
- **`hooks/useNameSearch.ts`**: add `model` state (default `written_similarity`), thread
  through search calls, re-run current liked names against the new model when the user
  switches (`setModel`).
- **`components/ModelToggle.tsx`** (new): two-option Hebrew radio-style toggle ("דמיון
  כתיב" / "דמיון תרבותי ומשמעות"), styled consistently with existing chip/button patterns in
  `global.css`.
- **`App.tsx`**: renders `ModelToggle` above `NameInput`; **key the `ScatterChart` on
  `model`** (`<ScatterChart key={model} .../>`) to force a clean remount rather than an
  interpolated transition — switching models jumps to an unrelated PCA coordinate space,
  which is expected, not a bug, and should look like a deliberate map change, not a glitch.
  A short hint under the toggle communicates this ("מעבר בין שיטות בונה מפה חדשה מאפס").

## Testing

- **`tests/embedding/test_onnx_sentence.py`** (new): shape, determinism, L2-normalization,
  OOV-name handling — parity with `test_ngram_svd.py`'s coverage.
- A **soft, explicitly experimental** comparative test (biblical/culturally-linked pairs vs.
  an unrelated control name) marked `@pytest.mark.xfail(strict=False)` with a docstring
  explaining this tests an unproven hypothesis — so CI stays green regardless of outcome
  while still documenting and tracking whether the hypothesis currently holds.
- **`tests/test_search.py`**: `model="cultural_similarity"` returns valid results; omitting
  `model` defaults to `written_similarity` (backward compat); unknown `model` value → `422`.
- **`tests/test_health.py`**: both models reported with correct dims (100, 384).
- **`frontend/tests/ModelToggle.test.tsx`** (new): correct labels, `aria-checked` reflects
  value, click calls `onChange`, `disabled` disables both buttons.

## Sanity check — DONE, positive result

Both `export_semantic_model.py` and `build_artifacts.py` print cosine similarity for a few
culturally-linked-but-differently-spelled pairs against an unrelated control name (אלמוג).
There is no ground-truth dataset for this, so "success" is a human judgment call. **Actual
measured result: all 4/4 pairs passed clearly** (linked similarity vs. the higher of the two
control comparisons):

| Pair | Why linked | sim(linked) | sim(vs control) |
|---|---|---|---|
| שרה, רבקה | biblical matriarchs | 0.776 | 0.360 |
| רות, נעמי | Megillat Rut | 0.616 | 0.281 |
| דוד, שלמה | father/son biblical kings | 0.749 | 0.311 |
| אברהם, יצחק | father/son patriarchs | 0.780 | 0.274 |

Qualitatively, searching "דוד" under `cultural_similarity` surfaces "יוהונתן" (Jonathan —
David's biblical companion) and "גדעון" (Gideon, a biblical judge) rather than only
spelling-similar compound names — a genuinely different, plausible-looking result set from
`written_similarity`'s output for the same query. This is real, encouraging signal that the
technique captures something beyond orthographic similarity — still not a guarantee (no
ground truth exists, and this is 4 hand-picked pairs, not a systematic evaluation), but a
meaningfully positive outcome for what was flagged going in as a genuine experiment. The
corresponding CI test (`test_culturally_linked_pairs_more_similar_than_unrelated_control`,
marked `xfail(strict=False)` so it can't break the build either way) currently **xpasses**.

## RAM verification — DONE, real numbers below

Docker isn't available in this sandbox, so image size was not verified there — still an open
step for a real build environment before deploying. What WAS verified locally: built the
exact production venv (`uv sync --frozen --no-dev`), ran `uvicorn nameme.main:app`, hit
`/api/health` to confirm both models loaded, measured actual RSS via `ps -o rss=`.

**First measurement (eager-load, naive): ~680–700MB RSS at idle** — over budget for a
512MB host. Breakdown isolated by importing components one at a time:
`fastapi+pandas+sklearn+numpy` ≈ 150MB, `+onnxruntime` ≈ 167MB, `+ONNX session loaded` ≈
386MB, **`+tokenizer loaded` ≈ 596MB**. The tokenizer (XLM-R's 250K-token multilingual
vocab, serialized as a 17MB `tokenizer.json`) costs ~210MB once loaded into memory — more
than the 118MB quantized model itself. This was the dominant, non-obvious cost.

**Fix applied — two changes, both implemented and tested:**
1. `OnnxSentenceEmbedder.fit_corpus()` is now a true no-op (was eagerly calling
   `_ensure_loaded()` at startup) — the ONNX session + tokenizer now load lazily, on the
   first real `encode()` call, not at process startup.
2. `search_service._encode_liked_names()` checks `ModelStore.vector_for(name)` (the
   precomputed corpus lookup) for every liked name FIRST, and only calls the live embedder
   for names outside the ~20K corpus. Since autocomplete steers users toward known names,
   most searches never touch the live embedder at all for either model.

**Result, measured after the fix:**

| Scenario | RSS |
|---|---|
| Idle, right after startup | 256 MB |
| After a search with corpus-known names | 258 MB |
| After the first search with a genuinely OOV name under `cultural_similarity` | 721 MB |

The typical/idle case now comfortably fits a 512MB free tier (was the real go/no-go risk
flagged pre-implementation, now resolved for the common case). The worst case (a truly novel
name typed under `cultural_similarity`) still costs ~700MB, permanently, for that process's
remaining lifetime — this is a known, accepted, documented trade-off (see root README's
"Memory footprint" section), not silently swept under the rug. If it becomes a real problem
in practice, the fallback order from the original risk assessment still applies: (a) a paid
tier with more RAM, (b) pruning the tokenizer's vocabulary to Hebrew-relevant tokens only
(the biggest remaining lever, untried), (c) restricting `cultural_similarity` input to
autocomplete-only selection (no free-text OOV path for that model), (d) splitting it into a
separately-scaled service.

Locked in with a regression test: `tests/test_search_service.py` asserts in-corpus names
never call the live embedder (fails loudly via a sabotaged mock if that invariant breaks).

### Critical files

- `backend/src/nameme/embedding/onnx_sentence.py` (new)
- `backend/src/nameme/embedding/registry.py` (new, replaces `factory.py`)
- `backend/src/nameme/corpus/loader.py`
- `backend/scripts/export_semantic_model.py` (new)
- `backend/scripts/build_artifacts.py`
- `backend/src/nameme/schemas/search.py`
- `backend/src/nameme/services/search_service.py`
- `backend/pyproject.toml`
- `frontend/src/hooks/useNameSearch.ts`
- `frontend/src/components/ModelToggle.tsx` (new)

## Verification — all done

- ✅ `uv sync --group export && uv run --group export python scripts/export_semantic_model.py`
  — fp32 470.3MB → int8 118.1MB (75% reduction, matched the commonly-cited figure — the
  caution about the embedding table not shrinking as well turned out unnecessary here).
- ✅ `uv run python scripts/build_artifacts.py` — both models built; `written_similarity`'s
  sanity numbers (0.730/0.368/0.249) came out byte-for-byte identical to pre-refactor,
  confirming the migration preserved behavior exactly. `cultural_similarity`'s sanity check:
  see "Sanity check" section above (4/4 pairs passed).
- ✅ `uv sync --frozen --no-dev` (production deps only) — confirmed via package list that
  torch/transformers/optimum are absent; app boots and serves correctly on this venv.
- ✅ Measured real RSS — see "RAM verification" section above for the full before/after.
- ✅ `POST /api/search` with both `model` values via curl; `/api/health` lists both models
  with correct dims (100, 384).
- ✅ Backend: 22 pytest tests + 1 xpass, `ruff check .` clean.
- ✅ Frontend: 8 Vitest tests, `tsc -b` clean, oxlint clean, prod build succeeds (548KB JS,
  165KB gzipped — acceptable for a portfolio app, unoptimized).
- ✅ End-to-end in a real headless browser: searched "דוד" under `written_similarity` (got
  spelling-similar compound names), switched the toggle to `cultural_similarity` (got a
  visibly different result set including יוהונתן/גדעון), confirmed the scatter plot
  remounted with a new coordinate space, zero console errors.

## What's left (not done in this session)

- ~~Not yet committed to git~~ — committed as `4b3d0c2`.
- Not yet deployed to Render/Vercel (needs account access — same as Phase 1).
- Docker build itself still unverified (no Docker daemon in this sandbox).
- The biggest remaining RAM lever (tokenizer vocabulary pruning to Hebrew-relevant tokens
  only) was identified but not attempted — worth doing if the worst-case ~700MB path turns
  out to matter in practice after deploying.

---

# Phase 3: TASKS..md items (search filters, background corpus, polish)

**Status: DONE.** Implements every item in the user's `TASKS..md` (repo root) except item 7,
which was blank.

## Context

The user dropped a `TASKS..md` file at the repo root with a short numbered wishlist and
asked to implement it. Two items were ambiguous enough to be worth a clarifying question
rather than guessing (see conversation): item 1 ("embedding is based on larger corpus and
not names") was confirmed to mean `written_similarity`'s TF-IDF vectorizer should fit its
IDF weighting against a larger general-Hebrew corpus, not just the ~20K names; item 5's
GitHub link was confirmed to ship as an opt-in placeholder (`VITE_GITHUB_URL`) since no
GitHub remote exists yet for this repo.

## What was built, per task item

0. **Middle point + 20 closest**: this was already the algorithm (centroid → cosine
   similarity → top-K); bumped `SearchRequest.top_k`'s default from 10 to 20 to match the
   brief literally, and its max from 30 to 50 so a user could ask for more.
1. **Larger-corpus IDF for `written_similarity`**: `NgramSvdEmbedder.fit_corpus()` now
   accepts an optional `background_corpus` — when given, the TF-IDF vectorizer's
   vocabulary/IDF fits on it, while TruncatedSVD still fits on the *names'* resulting
   vectors (SVD needs to discriminate among the ~20K names actually served, not the whole
   background vocabulary). Background corpus: `hspell_simple.txt` from
   `eyaler/hebrew_wordlists` (~130K individual Hebrew word forms, AGPL v3 — fetched fresh at
   build time via `scripts/background_corpus.py`, never committed; see `DATA_SOURCE.md` for
   the license disclosure). Measured effect on the existing sanity pairs: sim(דוד,דודי)
   0.730→0.742 (roughly stable), sim(שרה,שרון) 0.368→0.301, sim(משה,מיכאל) 0.249→0.101 (both
   meaningfully lower — consistent with those shared substrings being much more common in
   general Hebrew than the names-only corpus implied, i.e. the fix is doing what it should).
2. **Sex filter**: `SearchRequest.sex: "any"|"M"|"F"`, applied in `search_service.search()`
   before the top-K cut. Frontend: `SearchFilters` component, a `<select>`.
3. **Popularity percentile filter**: `SearchRequest.popularity: "all"|"top_10_percent"|
   "top_90_percent"`. `CorpusStore.__post_init__` precomputes each name's popularity
   percentile once (`total.rank(pct=True)`) so filtering is a cheap threshold check per
   candidate, not a re-rank at request time.
4. **Nicer visualization**: `ScatterChart` now splits suggestions into two colored series by
   sex (blue/pink) instead of one flat color, adds a `ZAxis` bubble-size channel keyed on
   real-world popularity, a legend, and a richer tooltip (similarity + sex + popularity).
5. **GitHub + names-list links**: new `Footer` component. Names list: `name_corpus.csv` is
   copied to `frontend/public/names.csv` and linked directly (static file, no new backend
   endpoint) — needs a manual re-copy if the corpus is ever refreshed. GitHub: renders only
   when `VITE_GITHUB_URL` is set (`.env.example` documents it) — deliberately not a fake/dead
   link since no remote exists yet.
6. **"Most different" mode**: `SearchRequest.sort: "similar"|"dissimilar"` — same similarity
   ranking, walked from the other end (`np.argsort(similarities)` instead of
   `np.argsort(-similarities)`). Frontend: two-button toggle in `SearchFilters`, matching
   `ModelToggle`'s pattern.
7. (blank in the source file — nothing to do)

## Testing

Backend: `tests/test_search.py` gained tests for the default top_k=20, sex filtering,
popularity filtering, and dissimilar-sort reversal (asserting the two result sets are
disjoint and correctly ordered). `tests/embedding/test_ngram_svd.py` gained tests for
`fit_corpus` with and without a `background_corpus`. All via the existing pattern (real
committed artifacts, no mocks, session-scoped fixtures). Frontend:
`tests/SearchFilters.test.tsx` (5 tests, mirroring `ModelToggle.test.tsx`'s pattern).

## Verification — all done

- ✅ Backend: 28 pytest tests + 1 xpass, `ruff check .` clean.
- ✅ Frontend: 13 Vitest tests, `tsc -b` clean, oxlint clean, prod build succeeds.
- ✅ Re-ran `build_artifacts.py` end to end with the real background corpus fetch; both
  models' artifacts rebuilt and committed; `written_similarity`'s new sanity numbers
  recorded above; `cultural_similarity` unaffected (unchanged numbers, confirming the
  background-corpus change is properly scoped to only the one model).
- ✅ End-to-end in a real headless browser: default search returns exactly 20 suggestions;
  sex filter narrows results; popularity filter narrows results; dissimilar-mode results are
  completely disjoint from similar-mode results for the same query; legend + colored/sized
  points render; `/names.csv` link returns `200`; zero console errors throughout.

### Critical files

- `backend/src/nameme/embedding/ngram_svd.py`
- `backend/scripts/background_corpus.py` (new)
- `backend/src/nameme/corpus/loader.py`
- `backend/src/nameme/services/search_service.py`
- `backend/src/nameme/schemas/search.py`
- `frontend/src/components/SearchFilters.tsx` (new)
- `frontend/src/components/Footer.tsx` (new)
- `frontend/src/components/ScatterChart.tsx`
- `frontend/src/hooks/useNameSearch.ts`

---

# Phase 4: Sector filter + clearer liked-name visualization

**Status: DONE.**

## Context

Two follow-up requests: (1) filter results by the population-sector "tabs" the CBS source
data is organized by (Jewish/Muslim/Christian-Arab/Druze boys/girls), which the data
pipeline had been discarding since Phase 1 (`build_corpus.py` aggregated `sector` away when
building `name_corpus.csv`); (2) make liked/selected names visually unambiguous in the
scatter plot — they'd been sharing the same popularity-driven size scale as suggestions,
risking blending in among nearby bubbles.

## What was built

**Data pipeline**: `build_corpus.py` no longer aggregates away `sector` — `name_corpus.csv`
is now one row per `(name, sex, sector)` (28,623 rows across the same 19,882 unique names;
embeddings are unaffected, since they only depend on the name list, not this metadata, so
`build_artifacts.py` did not need to re-run). Confirmed the 4 sector values actually present
in the source (`Jewish`, `Muslim`, `Christian-Arab`, `Druze` — no `Other`, despite earlier
Phase 1 research assuming one existed).

**Correctness fix bundled in**: the old `meta_for(name)["sex"]` was the *dominant* sex only
(highest-total row), so filtering by a name's non-dominant sex silently excluded it even
when real data existed (e.g. "דניאל" — dominant M with ~62K, but ~13K girls too — would
vanish entirely under a sex=F filter). `CorpusStore` now tracks every `(sex, sector)`
combination each name has a real row in (`combos`), and `matches_sex_sector(name, sex,
sector)` checks combined membership (not two independent checks) — so `sex=F, sector=Jewish`
only matches names with an actual Jewish-girls row, not any name with *some* Jewish presence
and *some* girls' presence from unrelated rows. Locked in with `tests/test_corpus_store.py`
using "דניאל" as a real example, not a fabricated fixture.

**API**: `SearchRequest.sector: "any"|"Jewish"|"Muslim"|"Christian-Arab"|"Druze"`.
`SuggestedName.sectors: list[str]` — every sector a name has any row in (exhaustive, unlike
`sex` which stays dominant-only for backward compatibility and simplicity).

**Frontend**: `SearchFilters` gained a sector `<select>` (Hebrew labels: יהודי/ה, מוסלמי/ת,
נוצרי/ה-ערבי/ה, דרוזי/ת). `ScatterChart`'s liked-name points now use a custom `shape`
render function (`LikedPointShape`) instead of the built-in `shape="star"` string — a
hand-drawn SVG star polygon at a fixed size (deliberately not wired to the `ZAxis`
popularity scale suggestions use), a white stroke outline for contrast, and the name printed
directly above it. Renders last in the JSX (top of SVG z-order), so it's never covered by
suggestion bubbles.

## Testing

New `tests/test_corpus_store.py` (6 tests): unisex-name combo detection, the dominant-sex
bug-fix regression test, `any`/`any` always matching, combined sex+sector matching requiring
a real co-occurring row, percentile bounds, overall-total aggregation. `test_search.py`
gained a sector-filter test (asserts every result's `sectors` list actually contains the
filtered sector — a precise check, unlike the sex filter's HTTP-level test, which was
loosened to a wiring-level check now that the dominant-sex assumption it relied on is gone).
Frontend: `SearchFilters.test.tsx` gained a sector-select test.

## Verification — all done

- ✅ Backend: 36 pytest tests + 1 xpass, `ruff check .` clean.
- ✅ Frontend: 14 Vitest tests, `tsc -b` clean, oxlint clean, prod build succeeds.
- ✅ Re-ran `build_corpus.py`; confirmed unique-name count unchanged (19,882) so no
  artifact/embedding rebuild was needed.
- ✅ End-to-end in a real headless browser: sector=Muslim filter returns only names whose
  `sectors` list actually contains `"Muslim"` (verified via a direct API call, not just the
  UI); two liked names ("דוד", "שרה") render as clearly labeled, fixed-size stars distinct
  from the surrounding suggestion bubbles (screenshot reviewed); zero console errors.
- Hit one environment snag during verification (unrelated to the app): background dev-server
  processes ended up suspended (`T` state) rather than killed by a prior cleanup, which held
  the port open while not responding — resolved with `kill -9` and a clean restart. Not a
  code issue, noted here only because it cost some time to diagnose.

### Critical files

- `backend/scripts/build_corpus.py`
- `backend/src/nameme/corpus/loader.py`
- `backend/src/nameme/services/search_service.py`
- `backend/src/nameme/schemas/search.py`
- `frontend/src/components/SearchFilters.tsx`
- `frontend/src/components/ScatterChart.tsx`

---

# Phase 5: Year-range filter (a "ruler")

**Status: DONE.**

## Context

The user asked for a slider to restrict which names are considered by a birth-year range.
The obvious approach — switch `build_corpus.py` to babynamesIL's yearly file
(`babynamesIL.csv`) as the primary source — was tried first and rejected after measuring
its actual effect: that file uses a **stricter** inclusion threshold (≥5 children in a
single year, vs. the totals file's ≥5-summed-across-all-years), and covers only 5,708 of
the corpus's 19,884 names. Switching to it entirely would have silently dropped 71% of the
corpus just to add a filter — a real regression disguised as a feature. Caught by actually
measuring the row/name counts before committing to a design, not by assumption.

## What was built

**Data pipeline**: `build_corpus.py` now fetches both babynamesIL files and produces two
outputs — `name_corpus.csv` (unchanged: the full 19,882-name corpus, from the totals file)
and a new supplementary `name_years.csv` (159,678 rows, `(name, sex, sector, year)`, years
1949–2024, covering 5,706 of the corpus names). The year filter only ever narrows the
*candidate set* for a search; it never changes what embeddings exist or what autocomplete
finds.

**Backend**: `CorpusStore` gained `years_df`, `year_min`/`year_max` (dataset bounds),
`is_full_year_range()`, and `year_filtered_meta()` (an on-the-fly per-name aggregate over
just the requested year span — same shape as the existing full-corpus metadata, computed
via one pandas groupby, shared logic factored into `_compute_meta()`). `search_service`
resolves which metadata source to rank against ONCE per request
(`_resolve_meta_source` — the full corpus metadata when the requested range covers the
whole dataset, otherwise the year-filtered dict), so the per-candidate ranking loop is still
plain `dict.get()` lookups, not per-candidate pandas calls. A name absent from a
year-filtered dict is excluded (no evidence in that range), never falls back to full-corpus
data. `SearchRequest` gained `year_min`/`year_max` (`int | None`, both `None` = no filter,
validated `year_min <= year_max`). `/api/health` reports the dataset's actual year bounds so
the frontend can size the slider without hardcoding them.

**Frontend**: `YearRangeSlider` — a dual-handle "ruler" built from two overlapping native
`<input type="range">` elements (a well-known dependency-free technique) rather than a
custom drag implementation or an external slider library, so keyboard/touch/accessibility
come from the browser for free. `useNameSearch` fetches `/api/health` once on mount to learn
the real year bounds (falls back to a hardcoded 1949–2024 if that fails, so the slider still
renders sensibly). The full-range state maps to `yearMin: null, yearMax: null` in the
request (matching the backend's "no filter" semantics exactly), not to explicit bound
values.

## Testing

`test_corpus_store.py` gained 5 tests using two real names with genuinely narrow,
non-overlapping year presence (אילאן: 2015–2024 only; זינובי: 1949–1960 only) — chosen by
querying the actual data, not fabricated. `test_search.py` gained tests for: year-range
narrowing actually excluding a known-absent name, `year_min > year_max` rejection (422), and
that requesting the exact full dataset span produces byte-identical results to omitting the
filter entirely (locks in the "full range == no filter" equivalence). `test_health.py`
gained a year-bounds test. Frontend: `YearRangeSlider.test.tsx` (5 tests: full-range label,
narrowed label, both handles' clamping behavior, disabled state).

## Verification — all done

- ✅ Backend: 45 pytest tests (9 new) + 1 xpass, `ruff check .` clean.
- ✅ Frontend: 19 Vitest tests (5 new), `tsc -b` clean, oxlint clean, prod build succeeds.
- ✅ End-to-end in a real headless browser: slider shows "כל השנים" (all years) at the full
  range; dragging the lower handle to 2015 updates the label to "2015–2024" and visibly
  changes the suggestion list to period-appropriate names; screenshot reviewed; zero console
  errors.
- Hit the same environment snag as Phase 4 again during verification (stale suspended dev
  server holding a port) plus a new variant (a stale server from an *earlier* verification
  session, still bound to the port, silently serving stale responses while a new instance
  failed to bind) — both resolved with `kill -9` + restart + explicit health-response
  inspection to confirm the *actual* running code, not just "did curl get a 200". Worth
  being more disciplined about checking bind errors in the log immediately after each
  restart, rather than only checking curl's exit status.

### Critical files

- `backend/scripts/build_corpus.py`
- `backend/src/nameme/corpus/loader.py`
- `backend/src/nameme/services/search_service.py`
- `backend/src/nameme/schemas/search.py`
- `frontend/src/components/YearRangeSlider.tsx` (new)
- `frontend/src/hooks/useNameSearch.ts`

---

# Phase 6: Manual ML sanity-check notebook

**Status: DONE.**

## Context

Requested: a way to manually poke at the ML logic directly, in a Jupyter notebook, using
the actual project code rather than reimplemented logic.

## What was built

`backend/notebooks/ml_sanity_check.ipynb` — imports the real `nameme` package, loads the
real committed artifacts via `load_corpus_store()`, and calls `search_service.search()`
directly (no HTTP layer). Five sections: (1) direct embedder cosine-similarity checks
bypassing search entirely, (2) full search via a `run_search()` helper returning a tidy
DataFrame, accepting every filter keyword the real endpoint does, (3) a matplotlib version
of the app's scatter plot (liked names as stars, suggestions colored/sized), (4) interactive
versions of the `test_corpus_store.py`/`test_search.py` regression checks using the same
real example names (`דניאל`, `אילאן`, `זינובי`), (5) a blank cell to experiment freely.

Added a new non-default `notebook` uv dependency group (`jupyterlab`, `ipykernel`,
`matplotlib`) — same pattern as the `export` group, kept out of the deployed image/CI.

Generated via a throwaway `nbformat`-based script (not committed) rather than hand-typed
JSON, then **actually executed end to end** (`jupyter execute --inplace`) before committing
— the committed notebook's outputs are real, not placeholders, so it's self-documenting even
unrun (e.g. on GitHub). All printed numbers match previously-verified values exactly (same
sanity-check pairs as `build_artifacts.py`/`export_semantic_model.py`), and running it
surfaced a nice live example of the sex-filter fix working correctly: "נועם" (a well-known
unisex Israeli name, dominant sex M) correctly appears in a `sex="F"`-filtered search.

## Verification

- ✅ Notebook executes cleanly end to end with zero error outputs (verified programmatically
  by inspecting the executed `.ipynb`'s cell outputs, not just "no exception thrown").
- ✅ `ruff check .` covers the notebook too (modern ruff lints `.ipynb` cells) — clean.
- ✅ Backend pytest suite (45 tests + 1 xpass) unaffected by the new dependency group.

### Critical files

- `backend/notebooks/ml_sanity_check.ipynb` (new)
- `backend/notebooks/README.md` (new)
- `backend/pyproject.toml` (new `notebook` dependency group)

---

# Phase 7: TASKS..md #7–9 — sex-filter display bug, slider drag, liked-marker styling

**Status: DONE.**

## Context

`TASKS..md` filed three concrete bug reports/polish requests after Phase 5/6 shipped:

- **#7**: "filter is not working properly. i filter for girls but also get boys on the
  graph." — real, not a misunderstanding: `combos_match` (added in an earlier phase
  specifically so a name like "דניאל" — dominant sex M, but also ~13K real girls — wouldn't
  vanish under a `sex=F` filter) only checked row *existence*. The metadata actually
  *displayed* for a passing name (dominant sex, total, sectors) still came from the
  unfiltered, all-rows aggregate — so a girls-only search could legitimately surface a name
  rendered with `sex="M"`, coloring it blue under the "boys" legend entry on a girls-only
  search. `test_search.py`'s own `test_search_filters_by_sex` docstring already predicted and
  excused this ("a name can pass a sex=F filter even when its *dominant* displayed sex is
  M") — correct about the mechanism, wrong about it being acceptable.
- **#8**: "slider is bad. i can only move it one year at a time and not freely." — App.tsx
  passes `disabled={loading}` to `YearRangeSlider`. Every native range-input step called
  `onChange` synchronously → `setFilters` → `runSearch` → `setLoading(true)`, which flips the
  input to `disabled` mid-gesture. A disabled `<input type="range">` drops the browser's
  mouse capture, ending the drag right there — so every single one-year step killed its own
  drag, and the user had to restart the gesture for each subsequent year.
- **#9**: "make graph nicer. draw a grey circle arround the selected names and make this
  icon black." — straightforward styling change to `LikedPointShape`.

## What was built

- **#7 fix** (`backend/src/nameme/corpus/loader.py`, `services/search_service.py`): added
  `_filter_rows()` (narrows a dataframe to rows matching the active sex/sector filter,
  "any" matching everything) and used it *before* aggregating metadata, not just for a
  post-hoc existence check. New `CorpusStore.sex_sector_filtered_meta()` (full year range +
  sex/sector filter) alongside the extended `year_filtered_meta(..., sex, sector)` (both year
  *and* sex/sector filters combined). `search_service._resolve_meta_source` now picks among
  four cases (no filter / sex-sector only / year only / both) instead of two, and the
  now-redundant per-candidate `combos_match` check was removed from the ranking loop — a
  name present in a filtered `meta_source` is already guaranteed to match by construction.
  Net effect: a `sex=F` search shows every matching name with `sex="F"` and its female-only
  popularity count, never its unfiltered dominant values. `matches_sex_sector`/`combos_match`
  themselves are unchanged (still correct, still used directly by tests and available for
  existence-only checks) — only where/how their result gets used to build display metadata
  changed.
- **#8 fix** (`frontend/src/components/YearRangeSlider.tsx`): the component now keeps a
  local `[from, to]` copy that updates instantly on every drag step (so the fill/label track
  the pointer with zero lag), while the actual `onChange` call up to the parent — the one
  that triggers a network search and flips `disabled` — is debounced 300ms after the last
  move. A whole drag across decades is now one uninterrupted gesture with a single search
  firing once it settles, instead of one search (and one dropped-capture interruption) per
  year. Local state resyncs from the `value` prop keyed on the numeric bounds specifically
  (not the array reference), so an unrelated parent re-render mid-drag can't snap the handle
  back to a stale position.
- **#9 fix** (`frontend/src/components/ScatterChart.tsx`, `styles/global.css`): `--liked`
  changed from pink (`#d6336c`) to near-black (`#111827`); added `--liked-ring`/
  `--liked-ring-fill` (grey stroke/soft-fill) for a new `<circle r=18>` drawn behind each
  liked-name star in `LikedPointShape`, sized to clearly enclose the star's own radius (13).

## Testing

`test_corpus_store.py` gained 3 tests exercising `sex_sector_filtered_meta`/
`year_filtered_meta`'s new narrowing directly against the real "דניאל" unisex-name edge case
(displayed sex flips M→F, total shrinks to the female-only count, combos collapse to
`{"F"}`). `test_search.py`'s `test_search_filters_by_sex` gained a direct assertion that
every `sex=F`-filtered suggestion's `sex` field is actually `"F"` (previously only asserted
the result *set* changed, per its own docstring's caveat — now the caveat is gone because
the bug it described is fixed). `YearRangeSlider.test.tsx` switched to Vitest fake timers:
existing clamping tests now assert `onChange` is debounced (not called until timers run),
plus a new test asserting the label updates immediately on each step regardless, and a new
regression test firing 5 rapid drag steps and asserting `onChange` fires exactly once, with
the final settled value — the direct regression check for #8.

## Verification — all done

- ✅ Backend: `uv run pytest` — 43 passed, 1 xfailed (the 5 pre-existing ONNX-model-file
  failures are unrelated: `model_quantized.onnx` was deliberately excluded from git for size
  in an earlier commit, not caused by this change). `ruff check .` clean (one pre-existing,
  unrelated notebook line-length warning).
- ✅ Frontend: `npm run test` — 21 passed (5 new). `npx tsc -b` clean. `npm run lint`
  (oxlint) clean.

### Critical files

- `backend/src/nameme/corpus/loader.py`
- `backend/src/nameme/services/search_service.py`
- `backend/tests/test_corpus_store.py`
- `backend/tests/test_search.py`
- `frontend/src/components/YearRangeSlider.tsx`
- `frontend/tests/YearRangeSlider.test.tsx`
- `frontend/src/components/ScatterChart.tsx`
- `frontend/src/styles/global.css`

---

# Phase 8: GitHub/data-source links + deployment plan

**Status: DONE** (footer links + Docker verification + deployment plan). **Actual
Render/Vercel deployment: NOT done** — needs account access this environment doesn't have;
see `DEPLOYMENT_PLAN.md` for the plan a human runs.

## Context

`TASKS..md` #10–12: a working GitHub repo link in the footer (the repo now has a real
`origin`, `git@github.com:oregev11/name-me.git` — `VITE_GITHUB_URL` was previously
opt-in/unset since there was no real URL yet), a link to the upstream name-data repo (Phase
4's "add links to github and names list" only covered the source-code repo + the `/names.csv`
static file, not the actual upstream data provenance), and a deployment plan (#12 was
originally phrased "deploy online," then narrowed by the user to "create a plan for
deployment" — this phase delivers the plan, not an executed deploy).

## What was built

- `frontend/.env.example`/`frontend/.env`: `VITE_GITHUB_URL` now defaults to the real repo
  URL instead of being commented out.
- `Footer.tsx`: added a third link, to `https://github.com/aviezerl/babynamesIL` (the
  upstream data source per `DATA_SOURCE.md`) — hardcoded (not an env var like
  `VITE_GITHUB_URL`), since it's a fixed citation independent of which fork/deployment is
  running, not something a deployer would override.
- `DEPLOYMENT_PLAN.md` (new): the full step-by-step plan — platform choice rationale
  (Render backend/Vercel frontend, both already implied by the existing Dockerfile/README),
  a pre-flight section, one real open blocker, 4 ordered deploy steps, costs/limits, and
  rollback notes.
- **Pre-flight verification, done as part of writing the plan** (Docker was unavailable in
  the sandbox this backend was originally built in — see this file's "RAM verification"
  section — but is available now): built `backend/Dockerfile`, ran the container, and hit
  real endpoints. Confirmed: builds cleanly (~2min cold), starts cleanly, `/api/health`
  reports both models loaded, `/api/search` returns correct results (including the sex-filter
  fix from Phase 7, spot-checked inside the container too), idle RSS ~223–235MB (in line
  with the ~250MB measured outside Docker previously), image size 892MB.
- **Real blocker surfaced and documented** (not fixed — needs a decision): the
  `cultural_similarity` model's `model_quantized.onnx` (~112MB) was excluded from git for
  size in an earlier commit and doesn't exist anywhere deployable currently pulls from. Most
  searches are unaffected (precomputed corpus vectors are committed and checked first), but
  the live-encode path for a genuinely novel name under that model would 500 in production.
  `DEPLOYMENT_PLAN.md` lays out 3 options (GitHub Release asset recommended, Git LFS,
  build-time re-export) and asks for a decision before Step 1.
- Two new scripts: `backend/scripts/docker_smoke_test.sh` (build+run+curl+cleanup, turns the
  manual pre-flight check above into something re-runnable before every deploy) and
  `scripts/verify_deployment.sh` (post-deploy check against live URLs — polls through
  Render free tier's cold-start window rather than failing on first timeout; checks both
  models, a real CORS preflight, and that the frontend actually serves the app).
- `render.yaml` (new, repo root): a Render Blueprint so the backend service is defined
  declaratively (Docker runtime, health check path, `CORS_ORIGINS` placeholder) instead of
  hand-clicked through Render's dashboard.
- README: fixed the now-stale "Docker build is unverified" line, added the two scripts'
  one-liners, linked `DEPLOYMENT_PLAN.md`, updated the footer/project-layout descriptions.

## Verification

- ✅ `docker_smoke_test.sh` runs clean end to end (build, health check, search check, memory
  check, teardown) — see script output captured while writing this phase.
- ✅ Frontend: `npm run test` (21 passed, no Footer test existed to update), `tsc -b` clean,
  `oxlint` clean.
- Backend test suite unaffected (no backend logic changed this phase, only frontend +
  deploy tooling/docs).

### Critical files

- `frontend/src/components/Footer.tsx`
- `frontend/.env.example`
- `DEPLOYMENT_PLAN.md` (new)
- `render.yaml` (new)
- `backend/scripts/docker_smoke_test.sh` (new)
- `scripts/verify_deployment.sh` (new)

---

# Phase 9: README CI/CD documentation

**Status: DONE.** Documentation only — no code changes.

## Context

User asked how CI/CD would work in this repo, then asked for that explanation to live in
the README (per `CLAUDE.md`'s "documentation" rules: over-explain, include mermaid,
update at every step). CI (`backend-ci.yml`/`frontend-ci.yml`) already existed from an
earlier session but was undocumented in the README beyond a stale one-line "Future plans"
bullet; CD was never wired up at all (no deployed targets yet — see `DEPLOYMENT_PLAN.md`).

## What was built

New `## CI/CD` README section (between Testing and Manual ML sanity check, cross-linked
from Deployment and Future plans): a mermaid flowchart of the current push → path-filtered
CI jobs → (dotted, "not connected yet") Render/Vercel deploy; a breakdown of each CI
workflow's actual steps; and an explicit "the gap" callout that CI and CD are two
independent reactions to the same push today, not one sequenced pipeline, with two ranked
options to fix that (branch protection, recommended; Actions-driven deploy). Also surfaced
and documented a concrete, previously-unrecorded finding: `backend-ci.yml` checks out the
same repo that's missing `cultural_similarity/model_quantized.onnx`, so the same 5 ONNX
-dependent test failures seen locally this session almost certainly also fail on GitHub's
runners — making `backend-ci` an unreliable gate until the ONNX-hosting decision in
`DEPLOYMENT_PLAN.md` is resolved and applied to CI too, not just the Dockerfile. Rewrote
the stale "Future plans" bullet (previously conflated "add another model" with "CI/CD" as
one item) into two accurate, ordered items.

## Verification

- Markdown structural check: all code fences balanced (18, even), all `#anchor` links
  (`#cicd`, `#deployment`, `#testing`) match real headings via GitHub's slug rules.
- New mermaid flowchart hand-verified against this same README's other diagrams' proven
  syntax patterns (quoted edge labels via `-->|"..."|`, `[[...]]` subroutine-shape nodes,
  `<br/>` line breaks) — no mermaid renderer was available in this environment to render it
  directly (no network install attempted, to avoid re-triggering the sandboxed-network
  prompt this session already hit once).

### Critical files

- `README.md`

---

# Phase 10: Over-explaining pass across all READMEs + per-service CI/CD detail

**Status: DONE.** Documentation only — no code changes.

## Context

Following Phase 9 (root README CI/CD section), the user asked for all READMEs in the repo
to be "over-explaining" and specifically for technical CI/CD detail, not just the root one.
`backend/.pytest_cache/README.md` is pytest's own auto-generated file (not a real project
doc) and was left alone.

## What was built

- `backend/README.md`: new `## CI/CD` section (backend-ci.yml's trigger/path-filter, exact
  step-by-step breakdown including the `--all-extras`-doesn't-mean-`--all-groups` nuance,
  an honest callout that there's no Python static-type-check step unlike the frontend's
  `tsc -b`, the same ONNX-causes-5-CI-failures gap documented in the root README but with
  the exact test names, and how it relates — or rather, doesn't yet relate — to Render CD).
- `frontend/README.md`: new standalone `## Testing` section (previously only a bullet in
  `## Scripts`) explaining *why* `npm run build` is part of the test sequence, not just
  listing it; new `## CI/CD` section (frontend-ci.yml's steps, `npm ci` vs `npm install`,
  and — the one genuinely new technical explanation, not just a restatement — that
  `VITE_*` env vars are baked into the JS bundle at **build** time, so a Vercel dashboard
  env-var edit does nothing until the next rebuild, unlike a backend service reading
  `os.environ` per-request). Also updated the `Structure` section's component descriptions
  to match this session's actual fixes (`YearRangeSlider`'s debounce mechanics and *why* it
  exists, `ScatterChart`'s black-star-in-grey-halo styling, `Footer`'s third link).
- `backend/notebooks/README.md`: small addition connecting to the CI/CD explanation above
  (this notebook's dependency group is invisible to CI by design) and clarifying its
  committed outputs are real, previously-executed results, not empty cells.

## Verification

- All four READMEs' fenced code blocks are balanced (even counts).
- All new/existing cross-doc `#anchor` links (`#cicd`, `#offline-artifact-pipeline`,
  `#memory-footprint-why-this-matters-for-free-tier-hosting`,
  `#data-flow-one-search-request-end-to-end`) hand-verified against GitHub's slug rules and
  each target file's real headings, including relative-path correctness (e.g.
  `backend/notebooks/README.md`'s `../README.md` correctly resolves to `backend/README.md`,
  not repo root, given its own nesting depth).
- Frontend regression check (no source changed, but run anyway since `README.md` content
  now describes real component behavior precisely): `npm run test` (21 passed), `tsc -b`
  clean, `oxlint` clean.

### Critical files

- `backend/README.md`
- `frontend/README.md`
- `backend/notebooks/README.md`

---

# Phase 11: Hebrew model explanations + resolving the ONNX blocker for real deployment

**Status: DONE** (model explanations, ONNX blocker, repo-visibility fix). **Render/Vercel
deploy itself: IN PROGRESS**, guided live with the user per their explicit choice (they run
the account/OAuth steps themselves via `!`-prefixed commands in-session; verified after each
step) — see `DEPLOYMENT_PLAN.md` Steps 1-4.

## Context

`TASKS..md` #13-15: a plain-language Hebrew explanation of the two similarity models for
end users (`ModelToggle` previously only showed the two button labels + a one-line hint
about rebuilding the map — no explanation of what either mode actually *does*); #14 ("add a
link to the names github repo") turned out to already be satisfied by Phase 8's Footer
addition (the `babynamesIL` link) — marked done, no code change needed; #15 ("deploy") is
the real thing this time, not just the plan from Phase 8.

Executing #15 immediately hit the real blocker Phase 8 had only documented (not fixed): the
`cultural_similarity` ONNX model isn't in git. Resolving it surfaced a second, more
consequential problem.

## What was built

- **Hebrew model explanations** (`ModelToggle.tsx`): a `MODEL_EXPLANATIONS` dict keyed by
  `ModelId`, rendered below the toggle buttons and switching live with the selected model —
  plain-language versions of the root README's "The two similarity models" section,
  including an honest "ניסיונית" (experimental) framing for `cultural_similarity`.
  `frontend/tests/ModelToggle.test.tsx` gained a test asserting the explanation text
  actually switches (not just that both strings exist somewhere in the DOM).
- **ONNX blocker, actually resolved**: regenerated the missing `model_quantized.onnx`
  locally (`export_semantic_model.py` — same base model, sanity-check numbers matched
  `PLAN.md`'s previously-recorded values exactly, confirming a deterministic export).
  Uploaded it as a GitHub Release asset
  ([`cultural-similarity-onnx-v1`](https://github.com/oregev11/name-me/releases/tag/cultural-similarity-onnx-v1)).
  `backend/Dockerfile` now fetches + checksum-verifies it via BuildKit's `ADD --checksum`
  (no `curl` binary needed in the image); `backend-ci.yml` fetches + verifies it too, before
  `pytest`. Verified with the local file *removed entirely* that the Docker build still
  produces a working image (proving the fetch, not local disk state, is what makes it work),
  and verified the actual previously-broken code path — a genuinely novel name searched
  under `cultural_similarity` inside a real container — now returns real suggestions
  (idle→post-lazy-load memory: ~231MB → ~637MB, matching the previously-documented ~700MB
  worst case).
- **Repo visibility, a real (not cosmetic) fix**: while wiring the Release-asset download,
  anonymous fetches 404'd — turned out this GitHub repo was **private**. That's not just an
  ONNX-hosting inconvenience: the footer's GitHub link (`TASKS..md` #10) would 404 for any
  real visitor to the deployed portfolio site too. Flagged to the user, who confirmed making
  it public (also the simpler fix for the asset download vs. a PAT-based authenticated
  build). `gh repo edit --visibility public --accept-visibility-change-consequences`.
- **A `gh` CLI auth wrinkle worth recording**: the environment's `GH_TOKEN` env var is
  invalid/stale and, being set, silences `gh`'s normal stored-credential login entirely
  (`gh auth login` refuses to proceed while any `GH_TOKEN` is set, valid or not) — the user
  had to run `unset GH_TOKEN && gh auth login` themselves (device-code browser flow) for
  `gh` to actually authenticate; subsequent `gh`/`curl` calls in this session needed
  `unset GH_TOKEN` prefixed too, since Bash tool calls don't share shell state with the
  user's own `!`-prefixed commands.
- Updated `DEPLOYMENT_PLAN.md` (blocker section rewritten from "decision needed" to
  "resolved", Step 0 marked done, stale "CI not set up" line in Open Items corrected) and
  both READMEs' CI/CD sections (mermaid diagram gained the ONNX-fetch step; the "known gap"
  prose became a "resolved" note) to match reality.

## An interesting side-observation, not acted on

`tests/embedding/test_onnx_sentence.py::test_culturally_linked_pairs_more_similar_than_unrelated_control`
is marked `xfail(strict=False)` with reasoning that the whole `cultural_similarity` premise
is an unproven hypothesis. With the ONNX file now actually present, this test's real logic
runs for (arguably) the first time in CI/local-test form — and it **passes** (4/4
culturally-linked pairs beat their control, `pytest` reports `1 xpassed`). Since `xfail` is
non-strict, this doesn't fail the build either way. Left the marker as-is rather than
declaring the hypothesis validated off one run — that's a modeling-methodology call the user
hasn't asked for, out of scope for this deployment-focused phase — but worth surfacing.

## Verification

- ✅ Backend: `uv run pytest` — 48 passed, 1 xpassed (see above), `ruff check .` clean (same
  pre-existing, unrelated notebook line-length note as every prior phase).
- ✅ Frontend: `npm run test` (22 passed, 1 new), `tsc -b` clean, `oxlint` clean.
- ✅ `docker build` succeeds with the local ONNX file **removed from disk entirely**,
  proving the `ADD --checksum` fetch (not local state) is what makes the image work; the
  resulting container correctly serves both the common (in-corpus) path and the
  previously-broken OOV live-encode path under `cultural_similarity`.
- ✅ Uploaded Release asset's sha256 (`ab9754c5...`) verified three ways: GitHub's own
  recorded asset digest, `gh release download` (authenticated), and a plain anonymous
  `curl` (post-visibility-fix) — all three match.

### Critical files

- `frontend/src/components/ModelToggle.tsx`
- `frontend/tests/ModelToggle.test.tsx`
- `frontend/src/styles/global.css`
- `backend/Dockerfile`
- `.github/workflows/backend-ci.yml`
- `DEPLOYMENT_PLAN.md`
- `README.md`, `backend/README.md`

---

# Phase 12: Real production OOM crash, and the fix

**Status: DONE.**

## Context

Backend deployed to Render (Step 1 of `DEPLOYMENT_PLAN.md`, done live with the user).
`scripts/verify_deployment.sh` passed cleanly. Then, testing the exact scenario Phase 11
had only verified locally (a genuinely novel name under `cultural_similarity`) against the
*real* deployed URL: the backend went unresponsive (502 on every endpoint, including
`/api/health`) for ~35 seconds until Render auto-restarted it. This is the OOM risk
`PLAN.md`'s "RAM verification" section had documented as a *possible* worst case since
Phase 2 — now confirmed as a *real* one, on a real 512MB-capped instance, not just measured
on a 15GB dev machine.

## What was built

User picked the recommended fix (of three offered: restrict-to-corpus / accept-and-move-on
/ pay for more RAM): `cultural_similarity` now rejects out-of-corpus liked names outright
instead of attempting the crash-prone live encode.

- `embedding/registry.py`: new `ModelSpec.allows_oov_encode: bool = True` field --
  `cultural_similarity` sets it `False`; `written_similarity` keeps the default (its OOV
  encode is cheap, no lazy heavyweight session involved).
- `corpus/loader.py`: `ModelStore` carries the same flag (copied from `ModelSpec` at load
  time) so `search_service` can check it without needing the registry in scope.
- `services/search_service.py`: new `UnsupportedOovNameError(names, model_id)`; `_encode_
  liked_names` raises it instead of calling `model.embedder.encode()` when a name is
  missing from the corpus and the model disallows OOV encode.
- `api/routes_search.py`: catches it, returns a structured 422 (`{"detail": {"error":
  "unsupported_oov_name", "model", "names", "message"}}`) -- a matchable tag, not just a
  string, so the frontend doesn't have to parse English prose.
- Frontend: `api/client.ts`'s `ApiError` gained an optional `.detail` (parsed from the JSON
  body when present); `useNameSearch.ts` maps `detail.error === "unsupported_oov_name"` to
  a specific Hebrew message (naming the offending name + suggesting autocomplete or
  switching models) instead of its generic "server might be waking up" fallback.
  `MODEL_LABELS` (the Hebrew display-name map) was hoisted from `ModelToggle.tsx` into
  `types/api.ts` so both the toggle and the new error-message code share one source (also
  fixed an oxlint `only-export-components` warning that caused, since a component file
  should only export the component).

## Verification

- ✅ Backend: `uv run pytest` -- 51 passed, 1 xpassed (3 new: OOV-allowed-under-
  written_similarity, OOV-rejected-under-cultural_similarity at the `_encode_liked_names`
  unit level, and an `/api/search` integration test for the same). `ruff check .` clean
  (same pre-existing unrelated notebook note).
- ✅ Frontend: `npm run test` (24 passed, 2 new: the specific-message case and the
  generic-fallback-still-works case), `tsc -b` clean, `oxlint` clean (0 warnings, was 1).
- ✅ Real container test (not just unit tests): built a fresh image, confirmed the exact
  previously-crashing request now returns a clean 422 with the structured detail, confirmed
  `/api/health` reports 200 immediately after (no crash/restart), and confirmed
  `written_similarity` still handles the same OOV name normally (200, real suggestions).
- Pushed to `main`; Render auto-redeploys (`autoDeploy: true`) -- re-verify against the live
  URL as part of closing out `TASKS..md` #15.

### Critical files

- `backend/src/nameme/embedding/registry.py`
- `backend/src/nameme/corpus/loader.py`
- `backend/src/nameme/services/search_service.py`
- `backend/src/nameme/api/routes_search.py`
- `backend/tests/test_search_service.py`, `backend/tests/test_search.py`
- `frontend/src/api/client.ts`
- `frontend/src/hooks/useNameSearch.ts`
- `frontend/src/types/api.ts`, `frontend/src/components/ModelToggle.tsx`
- `frontend/tests/useNameSearch.test.tsx` (new)
