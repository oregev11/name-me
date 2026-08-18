"""FastAPI app factory.

Loads the corpus + fitted ML artifacts once at startup (via the `lifespan`
context manager) rather than per-request, and exposes them to route handlers
through `app.state.corpus_store`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nameme.api.routes_autocomplete import router as autocomplete_router
from nameme.api.routes_health import router as health_router
from nameme.api.routes_search import router as search_router
from nameme.config import ARTIFACTS_DIR, get_settings
from nameme.corpus.loader import load_corpus_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.corpus_store = load_corpus_store(ARTIFACTS_DIR)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="name-me", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(search_router)
    app.include_router(autocomplete_router)

    return app


app = create_app()
