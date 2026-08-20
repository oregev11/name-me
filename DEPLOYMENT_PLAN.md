# Deployment plan

`TASKS..md` #12. This is the concrete, step-by-step plan for taking name-me from "runs
locally" to "has a public URL" — chosen platforms, what's already verified, one real blocker
that needs a decision, and the exact steps + scripts to execute and confirm each stage.
Nothing here has been executed yet (no Render/Vercel account access from this environment) —
this document is what a human runs, in order, using their own accounts.

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

## ⚠️ Real blocker: the `cultural_similarity` ONNX model isn't in git

`backend/src/nameme/artifacts/cultural_similarity/model_quantized.onnx` (~112MB) was
deliberately excluded from git in a prior commit ("Exclude oversized ONNX model from git,
over GitHub's limit") — GitHub hard-caps individual file blobs at 100MB. **It does not exist
in this git history at all**, on disk locally, or anywhere deployable currently pulls from.

What this actually breaks: `cultural_similarity`'s precomputed corpus vectors
(`corpus_vectors.npz`, 28MB, **is** committed) still work fine, so **any search using a name
already in the corpus works normally** — which, per README, is the common case since
autocomplete steers users to known names. Only the lazy live-encode path (a name typed that's
genuinely outside the ~20K corpus, searched under `cultural_similarity`) needs the missing
`.onnx` file, and would 500 without it. `written_similarity` is entirely unaffected (it
doesn't use ONNX at all).

This needs to be resolved **before** step 1 below, or `cultural_similarity` ships with a
known gap. Three options, cheapest/simplest first:

1. **GitHub Release asset** (recommended): upload `model_quantized.onnx` as a binary asset
   on a GitHub Release (Releases support files up to 2GB, unlike git blobs) — free, no new
   account, no new infra. Add a `RUN curl -L <release-asset-url> -o
   .../model_quantized.onnx` step to `backend/Dockerfile` (after the `COPY src ./src` step)
   so the image always has it, without ever putting it back in git.
2. **Git LFS**: puts the file back "in" git via a pointer, but adds a new dependency
   (`git-lfs` on every clone/CI machine) and GitHub LFS free bandwidth is capped (1GB/month)
   — probably fine at this project's scale, but more moving parts than option 1 for no clear
   benefit.
3. **Re-export at build time**: run `scripts/export_semantic_model.py` inside the Docker
   build instead of shipping the file. Rejected — it needs the `export` dependency group
   (torch + transformers + optimum), which was deliberately kept **out** of the runtime image
   for size/memory reasons (see README's "Memory footprint" section); pulling it back in for
   a build-time-only step would still bloat the build stage and slow every deploy.

**Decision needed from you**: confirm option 1 (GitHub Release asset), or say if you'd
rather do 2/3/something else. Nothing below depends on which you pick except the one
Dockerfile edit — the rest of the plan is unaffected.

## Step-by-step

### Step 0 — resolve the ONNX asset (see above), then re-verify

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
  doesn't — a genuinely novel name searched under `cultural_similarity`, ~700MB, for that
  process's remaining lifetime (see `PLAN.md`'s "RAM verification") — could OOM-kill a
  Render free instance (512MB limit). This is a **pre-existing, already-documented**
  trade-off, not something this deployment introduces; the fallback order if it becomes a
  real problem is already recorded in `PLAN.md` (paid tier / prune the tokenizer vocab /
  autocomplete-only for that model / split into its own service).
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

- The ONNX asset-hosting decision above.
- A custom domain, if wanted later — both platforms support it on free tiers; out of scope
  for a first deploy.
- CI (GitHub Actions) running `pytest`/`vitest` on every push before Render/Vercel
  auto-deploy from `main` — not set up yet; currently deploys would go out untested beyond
  whatever was run locally before pushing.
