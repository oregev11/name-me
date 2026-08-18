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

The corpus and fitted embedder/PCA are committed under `src/nameme/artifacts/` so the
service starts with no offline dependencies. To rebuild them (e.g. after refreshing the
data source or changing `EMBEDDER_TYPE`):

```bash
uv run python scripts/build_corpus.py      # only needed if the raw data source changed
uv run python scripts/build_artifacts.py   # refits the embedder + global PCA
```

See `../DATA_SOURCE.md` for data provenance and how to refresh the source.

## Testing & linting

```bash
uv run pytest
uv run ruff check .
```

## Architecture notes

- `embedding/base.py` defines the `NameEmbedder` interface. The MVP implementation
  (`embedding/ngram_svd.py`) is a character n-gram TF-IDF + TruncatedSVD pipeline requiring
  no training corpus beyond the name list itself. To swap in a different technique later
  (e.g. a trained Doc2Vec model), implement the same interface, register it in
  `embedding/factory.py`, and set `EMBEDDER_TYPE` — no API or schema changes needed.
- The 2D PCA projector is fit **once**, offline, on the full corpus
  (`scripts/build_artifacts.py`) and only ever `.transform()`-ed at request time, so the
  scatter plot's coordinate space stays stable across repeated searches in a session.
- Search is stateless: `POST /api/search` takes the full `liked_names` list each call; the
  frontend owns the "refine" loop by adding/removing names and resubmitting.
