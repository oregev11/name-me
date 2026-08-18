from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from nameme.api.deps import get_corpus_store
from nameme.corpus.loader import CorpusStore
from nameme.schemas.search import AutocompleteResponse

router = APIRouter()


@router.get("/api/autocomplete", response_model=AutocompleteResponse)
def autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    store: CorpusStore = Depends(get_corpus_store),
) -> AutocompleteResponse:
    q = q.strip()
    # Prefix matches first (more relevant), then other substring matches;
    # both ranked by corpus popularity via the precomputed ordering.
    prefix_matches = [n for n in store.names_by_popularity if n.startswith(q)]
    substring_matches = [n for n in store.names_by_popularity if q in n and not n.startswith(q)]
    matches = (prefix_matches + substring_matches)[:limit]
    return AutocompleteResponse(matches=matches)
