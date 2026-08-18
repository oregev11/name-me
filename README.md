# שם לי (name-me)

A portfolio web app for choosing a Hebrew baby name with a little machine-learning help.
Enter a couple of Hebrew names you like, and the app finds similar names by embedding them
and running cosine similarity search over a corpus of ~20,000 real Hebrew given names — with
the results plotted on a 2D map so you can see how names relate to each other, then refine
by adding or removing names and re-searching.

## How it works

1. **Corpus**: ~20K unique Hebrew `(name, sex)` pairs derived from official Israeli CBS
   birth-name statistics (1948–2024). See [`DATA_SOURCE.md`](./DATA_SOURCE.md).
2. **Embedding**: each name is encoded as a character n-gram TF-IDF vector, reduced to 100
   dimensions via truncated SVD — no training corpus beyond the name list itself, and it
   generalizes to names it's never seen. The embedding technique sits behind a small
   interface (`NameEmbedder`) so a different technique (e.g. a trained Doc2Vec model) can
   be swapped in later without touching the API or frontend.
3. **Search**: your liked names are encoded, averaged into a centroid vector, and compared
   via cosine similarity against every name in the corpus.
4. **Visualization**: all vectors are projected into 2D using a PCA transform fit once,
   offline, on the whole corpus — so the map's coordinate space stays stable as you refine
   your search across a session.
5. **Refine**: click a suggestion to add it to your liked names, or remove one you no longer
   want, and the app re-searches automatically.

## Project layout

```
backend/    FastAPI service serving the embedding/search/autocomplete API
frontend/   React + TypeScript + Vite single-page app
```

See `backend/README.md` and the sections below for local development.

## Local development

**Backend** (needs [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn nameme.main:app --reload
```

**Frontend** (needs Node 20+):

```bash
cd frontend
npm install
cp .env.example .env   # points at the local backend by default
npm run dev
```

Open the printed local URL — by default the frontend expects the backend at
`http://127.0.0.1:8000`.

## Testing

```bash
cd backend && uv run pytest && uv run ruff check .
cd frontend && npm run test && npm run lint && npx tsc -b
```

## Deployment

- **Backend**: Docker image (`backend/Dockerfile`), designed for a free-tier host like
  [Render](https://render.com) as a web service. Set `CORS_ORIGINS` to your deployed
  frontend URL.
- **Frontend**: static Vite build, designed for a free-tier host like
  [Vercel](https://vercel.com). Set `VITE_API_BASE_URL` to your deployed backend URL.

**Known trade-off**: free-tier backend hosts typically spin down after a period of
inactivity, so the first request after a while can take 30–60s to wake the server back up.
The frontend shows a "waking up..." message during this window rather than a bare spinner.

## License

Code is MIT-licensed (see [`LICENSE`](./LICENSE)). The name corpus has separate provenance
and licensing — see [`DATA_SOURCE.md`](./DATA_SOURCE.md).
