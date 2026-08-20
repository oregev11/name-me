# Deployment plan

`TASKS..md` #12/#15. This is the concrete, step-by-step plan for taking name-me from "runs
locally" to "has a public URL" — chosen platforms, what's already verified, and the exact
steps + scripts to execute and confirm each stage. Render/Vercel account setup (Steps 1-4)
needs a human clicking through each dashboard's OAuth — this document is what to run, in
order, at that point.

## Chosen platforms (already decided, see README's "Deployment" section)

- **Backend** → [Render](https://render.com), as a Docker web service. Chosen because the
  backend already has a working `Dockerfile`, Render's free tier needs no credit card, and
  it (unlike most serverless platforms) keeps one process alive between requests — which
  matters here because the whole point of the offline artifact pipeline is loading models
  **once** at startup, not per-request.
- **Frontend** → [Vercel](https://vercel.com), as a static Vite build. Chosen because it's
  zero-config for Vite, free, and fast (global CDN) — the frontend has no server-side logic
  of its own, it only talks to the one backend API.

Both are $0/month on free tiers for this project's traffic level (a portfolio demo, not
production load) — see "Costs & limits" below for the trade-offs that come with "free."

## Pre-flight: what's already verified (done as part of writing this plan)

Docker wasn't available in the sandbox the backend was originally built in (see
`PLAN.md`'s "RAM verification" section), so the build itself was flagged as an open risk.
It's available now, so this plan verified it directly rather than leaving it as a guess:

- ✅ `docker build` on `backend/Dockerfile` succeeds cleanly (~2 min from a cold cache).
- ✅ The built image **runs** and serves real traffic: `/api/health` reports both models
  loaded (19,882-name corpus), `/api/search` returns real, correctly-filtered suggestions
  (including the sex-filter fix from `TASKS..md` #7, verified inside the container too).
- ✅ Idle memory in-container: **~223–235MB** — in line with (slightly better than) the
  ~250MB measured outside Docker in `PLAN.md`. Comfortably fits Render free's 512MB.
- ✅ Image size: **892MB** (mostly `onnxruntime` + `pandas` + `scikit-learn` + `scipy`) — no
  known Render free-tier limit this would hit, just noted for awareness.
- This is now a repeatable script, not a one-off check — see `backend/scripts/docker_smoke_test.sh`
  below. Re-run it any time before deploying, e.g. after dependency bumps.

## ✅ Resolved: the `cultural_similarity` ONNX model + a repo-visibility fix

`backend/src/nameme/artifacts/cultural_similarity/model_quantized.onnx` (~112MB) was
excluded from git in a prior commit — GitHub hard-caps individual git blobs at 100MB. Fixed
via the recommended option (GitHub Release asset):

1. Regenerated the file locally (`uv sync --group export && uv run --group export python
   scripts/export_semantic_model.py`) — the previous export was never committed to begin
   with, only referenced. Its sanity-check numbers matched `PLAN.md`'s previously-recorded
   values exactly (same base model, deterministic export).
2. Uploaded it as a Release asset:
   [`cultural-similarity-onnx-v1`](https://github.com/oregev11/name-me/releases/tag/cultural-similarity-onnx-v1),
   sha256 `ab9754c56dc012929bebb839bbe79e276fbb8306ed212ffd00bf816914bb8b03`.
3. **Discovered along the way: this repo was private.** GitHub returns a plain 404 (not 403)
   for a private repo's Release assets when fetched unauthenticated — which is exactly what
   an anonymous Docker build does. This wasn't just an asset-hosting problem: the footer's
   "קוד המקור ב-GitHub" link (`TASKS..md` #10) would 404 for any real visitor too, defeating
   the point of a portfolio app linking to its own source. **Made the repo public** — fixes
   both at once, no auth/secrets needed for either the Docker build or CI.
4. `backend/Dockerfile` now fetches + checksum-verifies it via BuildKit's `ADD --checksum`
   (no `curl` package needed in the image; a corrupted/wrong download fails the build
   loudly). `backend-ci.yml` fetches it too, before `pytest` — the 5 tests that need it
   (`tests/embedding/test_onnx_sentence.py`, one case in `test_search_service.py`) now pass
   in CI, not just locally.
5. Verified end to end in an actual container, twice: once via
   `docker_smoke_test.sh` (in-corpus search), once manually forcing the lazy-load path with
   a genuinely made-up name (`קסניופולוס`) under `cultural_similarity` — at the time,
   confirmed real suggestions come back and idle→post-load memory moves ~231MB → ~637MB,
   matching `PLAN.md`'s previously-measured worst case.
6. **Then it actually shipped, and the exact scenario from step 5 crashed the real Render
   deploy** — the live process went unresponsive (502 on every endpoint, including
   `/api/health`) for ~35s until Render auto-restarted it, when that same OOV name was
   searched under `cultural_similarity` against the deployed instance (512MB cap, not the
   15GB dev machine step 5 was measured on). Confirmed this was a known-but-previously-only
   theoretical risk actually materializing, not a new bug.
7. **Fixed properly**: `cultural_similarity` now rejects out-of-corpus names outright
   (`ModelSpec.allows_oov_encode = False`, a clean 422 instead of the crash-prone live
   encode) — see the root README's "Memory footprint" section for the full mechanism. Step
   5's "confirmed real suggestions come back" is no longer today's behavior for that
   scenario by design; `written_similarity` is unaffected (its OOV path is cheap and stays
   allowed).

## Step-by-step

### Step 0 — done (see above); re-verify any time with

```bash
./backend/scripts/docker_smoke_test.sh
```

### Step 1 — deploy the backend to Render

`render.yaml` (repo root) is a ready-made Blueprint — Render reads it automatically:

1. Push this repo to GitHub (already done — `origin` is `github.com/oregev11/name-me`).
2. Render dashboard → **New** → **Blueprint** → select this repo → Render proposes the
   `nameme-backend` web service from `render.yaml` → **Apply**.
3. First deploy takes a few minutes (Docker build on Render's infra). Once live, copy its
   URL (`https://nameme-backend.onrender.com` or similar — Render assigns the exact
   subdomain).
4. Verify it immediately, before touching the frontend:
   ```bash
   BACKEND_URL=https://<your-render-url> ./scripts/verify_deployment.sh
   ```

`render.yaml` sets `CORS_ORIGINS` to this project's *expected* Vercel URL
(`https://name-me.vercel.app`, per `frontend/.env.example`) as a placeholder — step 3 below
fixes it once the frontend's real URL is confirmed.

### Step 2 — deploy the frontend to Vercel

No `vercel.json` needed — Vite is zero-config on Vercel once the project root is set:

1. Vercel dashboard → **Add New** → **Project** → import this same GitHub repo.
2. **Root Directory**: set to `frontend` (this repo is not a monorepo Vercel auto-detects —
   the default root has no `package.json`).
3. Framework Preset: Vercel should auto-detect **Vite**; leave build/output settings default.
4. **Environment variables** (Project Settings → Environment Variables — these are
   `.env.example`'s keys, not read from the gitignored `.env` file):
   - `VITE_API_BASE_URL` = the Render URL from step 1.
   - `VITE_GITHUB_URL` = `https://github.com/oregev11/name-me`
5. Deploy. Copy the real assigned URL (Vercel appends a suffix, e.g.
   `name-me-<username>.vercel.app`, if the plain `name-me.vercel.app` is already taken).

### Step 3 — close the CORS loop

If the Vercel URL from step 2 differs from the `render.yaml` placeholder:

1. Render dashboard → `nameme-backend` → Environment → update `CORS_ORIGINS` to the real
   Vercel URL (comma-separate if you want to also keep `localhost` for local dev against the
   prod backend — see `backend/.env.example` for the format).
2. Render redeploys automatically on env var change (no code push needed).

### Step 4 — verify the whole thing, live

```bash
BACKEND_URL=https://<your-render-url> \
FRONTEND_URL=https://<your-vercel-url> \
./scripts/verify_deployment.sh
```

This checks: backend wakes up and reports healthy, `/api/search` returns real suggestions
for **both** models, a CORS preflight from the real frontend origin succeeds, and the
frontend actually serves the app (not a blank page or a build-error screen). Then also
open the frontend URL in an actual browser and run one real search by hand — the script
proves the wiring works, but only a human glance confirms the UI itself looks right (this
is also where you'd notice the free-tier "waking up..." message on the first cold request,
per README's "Known trade-offs").

## Costs & limits (both free tiers — read before relying on this in production)

- **$0/month** on both platforms at this project's expected traffic.
- **Render free spins down after ~15 min idle.** The first request after that takes 30–60s
  to wake back up — the frontend already shows a "waking up..." message during this window
  (existing behavior, not new). Not fixable on the free tier short of paying for an
  always-on instance.
- **Memory**: idle fits comfortably (see pre-flight numbers above). The one scenario that
  didn't — a genuinely novel name searched under `cultural_similarity`, ~700MB, for that
  process's remaining lifetime (see `PLAN.md`'s "RAM verification") — actually OOM-killed
  the real Render free-tier deploy the first time this was tested against a live URL (not
  just a theoretical risk anymore). **Fixed, not just documented**: `cultural_similarity`
  now rejects out-of-corpus names outright with a 422 instead of attempting the expensive
  live encode (`ModelSpec.allows_oov_encode = False` in `embedding/registry.py`) — see the
  root README's "Memory footprint" section for the mechanism and the frontend-facing error
  message.
- **Rollback**: both platforms keep prior deploys. Render → Deploys tab → redeploy an older
  one. Vercel → Deployments tab → "Promote to Production" on an older one. Both also
  auto-deploy on every push to `main` by default — disable `autoDeploy` in `render.yaml` (or
  the equivalent Vercel Git setting) if you'd rather deploy manually.

## Scripts this plan added

- `backend/scripts/docker_smoke_test.sh` — build the backend image, run it, hit
  `/api/health` + `/api/search`, check memory, tear down. Run before every deploy.
- `scripts/verify_deployment.sh` — hit the **live** Render/Vercel URLs after each deploy
  step; polls through Render's free-tier cold start rather than failing on the first
  timeout.
- `render.yaml` — Render Blueprint (Step 1); defines the one backend service declaratively
  so it isn't hand-configured through the dashboard.

## Open items (not blocking, but worth tracking)

- A custom domain, if wanted later — both platforms support it on free tiers; out of scope
  for a first deploy.
- CI (`.github/workflows/{backend,frontend}-ci.yml`) already runs `pytest`/`vitest` on every
  push — see the root README's [CI/CD](./README.md#cicd) section — but isn't *sequenced*
  with Render/Vercel's auto-deploy: both react to the same push independently, so a red test
  run doesn't currently block a deploy. That section lays out two fixes (branch protection,
  recommended; Actions-driven deploy); neither is implemented.
