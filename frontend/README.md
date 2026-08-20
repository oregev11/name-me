# name-me frontend

React + TypeScript + Vite single-page app for the name-me Hebrew name recommender.

## Local development

```bash
npm install
cp .env.example .env   # points at the local backend by default
npm run dev
```

Requires the backend running (see `../backend/README.md`) at the URL configured in
`VITE_API_BASE_URL`.

## Scripts

- `npm run dev` — start the dev server
- `npm run build` — type-check (`tsc -b`) and produce a production build in `dist/`
- `npm run test` — run the Vitest suite
- `npm run lint` — run oxlint
- `npm run format` / `npm run format:check` — Prettier

## Testing

```bash
npm run lint       # oxlint
npx tsc -b         # typecheck, no emit (tsc -b = project-references build mode)
npm run test       # vitest, jsdom environment (see tests/setup.ts)
npm run build      # production build -- also a compile-time check `dev` alone doesn't do
```

Run in that order — it's exactly the order `frontend-ci.yml` runs them in (see CI/CD
below), so a local pass and a CI pass mean the same thing. `npm run build` is included
deliberately, not just for the artifact: Vite's dev server (`npm run dev`) transpiles files
individually and can stay green on things a full build catches (e.g. certain unused-export
tree-shaking issues, or a stray reference to a Node-only API that dev-mode's browser-native
ESM loading tolerates differently than the bundled build).

## Structure

- `src/api/client.ts` — typed fetch wrapper around the backend API, incl. `getHealth()`
  (used once on mount to learn the dataset's real year bounds for the slider)
- `src/types/api.ts` — request/response types mirroring the backend's Pydantic schemas
- `src/hooks/useNameSearch.ts` — owns the liked-names state, the selected model, and the
  search filters (sex/sector/popularity/sort/year range), and triggers a re-search on every
  add/remove/model-switch/filter-change (the "refine" loop). Fetches `/api/health` once on
  mount to get the real year-range bounds (falls back to a hardcoded 1949–2024 if that fails
  — the slider still works, just against an assumed rather than confirmed range).
- `src/components/` — `NameInput` (RTL input + autocomplete), `LikedNameChips`,
  `ModelToggle` (switches between `written_similarity`/`cultural_similarity`),
  `YearRangeSlider` (dual-handle year-range "ruler" — two overlapping native
  `<input type="range">` elements, no external slider dependency; keeps a local copy of the
  `[from, to]` value that updates instantly on every drag step for visual feedback, but
  debounces the actual `onChange` call up to the parent — which triggers a network search
  and flips `disabled` while it's in flight — by 300ms after the last move. Without that
  debounce, every single one-year step fired its own search immediately, and the resulting
  `disabled` mid-drag dropped the browser's native mouse capture, ending the drag right
  there — the slider was only ever movable one year at a time before this fix), `SearchFilters`
  (sex/sector/popularity/sort controls), `ScatterChart` (Recharts 2D plot of liked +
  suggested names — suggestions colored by sex and sized by popularity; liked names render
  as large black stars inside a soft grey halo ring via a custom `shape` fn, deliberately not
  tied to the popularity size scale so they're never mistaken for a suggestion — remounted
  via `key={model}` on model switch since each model has its own unrelated PCA coordinate
  space), `SuggestionsList`, `Footer` (links to `/names.csv`, the upstream `babynamesIL`
  data-source repo, and — via `VITE_GITHUB_URL`, defaulted to this project's real repo in
  `.env.example` — the source code)

## CI/CD

See the root [`README.md`](../README.md#cicd) for the repo-wide picture. This section is
the frontend-specific detail: what `.github/workflows/frontend-ci.yml` actually does, and a
Vite/Vercel-specific gotcha worth knowing before touching env vars in production.

### What triggers it

Same shape as the backend's workflow: `push` to `main` and every `pull_request`, both
filtered to `paths: ["frontend/**", ".github/workflows/frontend-ci.yml"]` — a
backend-only change never spins up this Node job.

### The steps, and why each one is there

`defaults.run.working-directory: frontend`, then:

1. **`actions/setup-node@v4`** with `node-version: 22` and `cache: npm` (keyed on
   `package-lock.json`) — pins the Node version explicitly rather than trusting the runner's
   default, and caches `~/.npm` between runs so `npm ci` doesn't re-download every package
   on every push.
2. **`npm ci`** (not `npm install`) — installs exactly what `package-lock.json` pins, and
   fails outright if the lockfile and `package.json` have drifted, instead of silently
   updating the lockfile the way `npm install` would. This is the standard CI-vs-local
   distinction: reproducibility over convenience.
3. **`npm run lint`** (oxlint) → **`npx tsc -b`** (typecheck) → **`npm run test`** (vitest)
   → **`npm run build`** — the exact four steps and order documented in this file's
   [Testing](#testing) section above, for the reason given there (`build` catches things
   `dev`/`test` alone don't).

### Env vars in CI vs. in the app: two completely different things

The `VITE_API_BASE_URL`/`VITE_GITHUB_URL` env vars this README's [Local
development](#local-development) section sets via `.env` are **not** read by CI at all —
`frontend-ci.yml` never sets them, and `npm run build` succeeds without them (Vite falls
back to `import.meta.env.VITE_*` being `undefined`, which the code already handles — e.g.
`Footer.tsx` simply doesn't render the GitHub link when unset). CI's `build` step is a
compile-time correctness check (does the TypeScript/bundle build succeed at all), not a
check that the *deployed* app will have the right URLs configured — that's a deploy-time
concern, set in Vercel's own dashboard (see below), completely separate from anything in
this repo's CI config.

### CD: Vercel, and a real gotcha with `VITE_*` env vars

Like the backend, this workflow only tests — no `deploy` job. Vercel's GitHub integration
deploys independently, on the same push, once the project is connected (see
`../DEPLOYMENT_PLAN.md` Step 2) — same "not sequenced with CI" caveat as the root
[CI/CD](../README.md#cicd) section explains.

**The gotcha**: Vite bakes every `VITE_*` env var into the built JS bundle **at build
time** — `import.meta.env.VITE_API_BASE_URL` becomes a literal string constant in the
output; there is no runtime lookup happening in the browser. This means:

- Env vars must be set in Vercel's **Project Settings → Environment Variables**, not
  discovered from `.env`/`.env.example` (those are gitignored/example-only and never reach
  Vercel's build).
- Changing an env var in Vercel's dashboard does **nothing** to an already-deployed build —
  it only takes effect on the *next* build. If you update `VITE_API_BASE_URL` after
  deploying, you must trigger a redeploy (Vercel's dashboard, or any new push) for the new
  value to actually reach users — the trap is assuming a dashboard env-var edit alone goes
  live immediately, the way it would for a backend service reading `os.environ` fresh on
  each request.
