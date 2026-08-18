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

- `src/api/client.ts` — typed fetch wrapper around the backend API
- `src/types/api.ts` — request/response types mirroring the backend's Pydantic schemas
- `src/hooks/useNameSearch.ts` — owns the liked-names state, the selected model, and the
  search filters (sex/popularity/sort), and triggers a re-search on every
  add/remove/model-switch/filter-change (the "refine" loop)
- `src/components/` — `NameInput` (RTL input + autocomplete), `LikedNameChips`,
  `ModelToggle` (switches between `written_similarity`/`cultural_similarity`),
  `SearchFilters` (sex/popularity/sort controls), `ScatterChart` (Recharts 2D plot of liked +
  suggested names, colored by sex and sized by popularity — remounted via `key={model}` on
  model switch since each model has its own unrelated PCA coordinate space),
  `SuggestionsList`, `Footer` (links to `/names.csv` and, if `VITE_GITHUB_URL` is set, the repo)
