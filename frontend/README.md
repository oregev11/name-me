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
  `<input type="range">` elements, no external slider dependency), `SearchFilters`
  (sex/sector/popularity/sort controls), `ScatterChart` (Recharts 2D plot of liked +
  suggested names — suggestions colored by sex and sized by popularity; liked names render
  as large, labeled stars via a custom `shape` fn, deliberately not tied to the popularity
  size scale so they're never mistaken for a suggestion — remounted via `key={model}` on
  model switch since each model has its own unrelated PCA coordinate space),
  `SuggestionsList`, `Footer` (links to `/names.csv` and, if `VITE_GITHUB_URL` is set, the
  repo)
