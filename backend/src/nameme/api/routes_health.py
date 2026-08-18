from __future__ import annotations

from fastapi import APIRouter, Depends

from nameme.api.deps import get_corpus_store
from nameme.corpus.loader import CorpusStore
from nameme.schemas.search import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health(store: CorpusStore = Depends(get_corpus_store)) -> HealthResponse:
    return HealthResponse(status="ok", corpus_size=store.size, embedder_type=store.embedder_type)
