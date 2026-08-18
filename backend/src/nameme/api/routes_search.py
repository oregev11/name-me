from __future__ import annotations

from fastapi import APIRouter, Depends

from nameme.api.deps import get_corpus_store
from nameme.corpus.loader import CorpusStore
from nameme.schemas.search import SearchRequest, SearchResponse
from nameme.services.search_service import search

router = APIRouter()


@router.post("/api/search", response_model=SearchResponse)
def search_names(
    body: SearchRequest, store: CorpusStore = Depends(get_corpus_store)
) -> SearchResponse:
    return search(
        store,
        body.liked_names,
        body.top_k,
        body.model,
        sex=body.sex,
        popularity=body.popularity,
        sort=body.sort,
    )
