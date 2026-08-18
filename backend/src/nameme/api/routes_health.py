from __future__ import annotations

from fastapi import APIRouter, Depends

from nameme.api.deps import get_corpus_store
from nameme.corpus.loader import CorpusStore
from nameme.embedding.registry import MODEL_REGISTRY
from nameme.schemas.search import HealthResponse, ModelInfo

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health(store: CorpusStore = Depends(get_corpus_store)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        corpus_size=store.corpus_size,
        year_min=store.year_min,
        year_max=store.year_max,
        models=[
            ModelInfo(
                id=model_id,
                display_name=MODEL_REGISTRY[model_id].display_name_he,
                dim=model_store.vectors.shape[1],
                corpus_vectors=len(model_store.unique_names),
            )
            for model_id, model_store in store.models.items()
        ],
    )
