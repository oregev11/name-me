"""Request/response schemas for the search and autocomplete endpoints."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ModelId = Literal["written_similarity", "cultural_similarity"]
SexFilter = Literal["any", "M", "F"]
PopularityFilter = Literal["all", "top_10_percent", "top_90_percent"]
SortMode = Literal["similar", "dissimilar"]

# Same shape as the filter used when building the corpus (see
# scripts/build_corpus.py) -- keeps user input restricted to Hebrew script so
# similarity results stay meaningful (the n-gram embedder would otherwise
# happily encode garbage input into a meaningless vector).
HEBREW_NAME_RE = re.compile(r"^[א-ת][א-ת \-'\"]*$")


class SearchRequest(BaseModel):
    liked_names: list[str] = Field(..., min_length=1, max_length=10)
    # Default of 20: find the "middle point" (centroid) of the liked names,
    # then the 20 closest names to it.
    top_k: int = Field(default=20, ge=1, le=50)
    # Default preserves the pre-multi-model behavior for any existing caller
    # that omits this field.
    model: ModelId = "written_similarity"
    sex: SexFilter = "any"
    popularity: PopularityFilter = "all"
    sort: SortMode = "similar"

    @field_validator("liked_names")
    @classmethod
    def validate_hebrew_names(cls, names: list[str]) -> list[str]:
        cleaned = [n.strip() for n in names]
        for name in cleaned:
            if not name or not HEBREW_NAME_RE.match(name):
                raise ValueError(f"{name!r} is not a valid Hebrew name")
        return cleaned


class NamePoint(BaseModel):
    name: str
    x: float
    y: float


class SuggestedName(BaseModel):
    name: str
    x: float
    y: float
    similarity: float
    sex: str
    popularity: int


class SearchResponse(BaseModel):
    liked: list[NamePoint]
    suggestions: list[SuggestedName]


class AutocompleteResponse(BaseModel):
    matches: list[str]


class ModelInfo(BaseModel):
    id: str
    display_name: str
    dim: int
    corpus_vectors: int


class HealthResponse(BaseModel):
    status: str
    corpus_size: int
    models: list[ModelInfo]
