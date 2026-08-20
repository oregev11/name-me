from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from nameme.api.deps import get_corpus_store
from nameme.corpus.loader import CorpusStore
from nameme.schemas.search import SearchRequest, SearchResponse
from nameme.services.search_service import UnsupportedOovNameError, search

router = APIRouter()


@router.post("/api/search", response_model=SearchResponse)
def search_names(
    body: SearchRequest, store: CorpusStore = Depends(get_corpus_store)
) -> SearchResponse:
    try:
        return search(
            store,
            body.liked_names,
            body.top_k,
            body.model,
            sex=body.sex,
            sector=body.sector,
            popularity=body.popularity,
            sort=body.sort,
            year_min=body.year_min,
            year_max=body.year_max,
        )
    except UnsupportedOovNameError as exc:
        # A structured `detail`, not just a string: the frontend matches on
        # `detail.error` to show a specific, actionable message instead of
        # its generic "server might be waking up" fallback -- see
        # api/client.ts and hooks/useNameSearch.ts.
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_oov_name",
                "model": exc.model_id,
                "names": exc.names,
                "message": (
                    f"{exc.model_id} does not support names outside its corpus "
                    f"(unrecognized: {exc.names!r}). Pick a name from autocomplete, "
                    "or switch models."
                ),
            },
        ) from exc
