"""Request/response schemas for the search and autocomplete endpoints."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Same shape as the filter used when building the corpus (see
# scripts/build_corpus.py) -- keeps user input restricted to Hebrew script so
# similarity results stay meaningful (the n-gram embedder would otherwise
# happily encode garbage input into a meaningless vector).
HEBREW_NAME_RE = re.compile(r"^[א-ת][א-ת \-'\"]*$")


class SearchRequest(BaseModel):
    liked_names: list[str] = Field(..., min_length=1, max_length=10)
    top_k: int = Field(default=10, ge=1, le=30)

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


class HealthResponse(BaseModel):
    status: str
    corpus_size: int
    embedder_type: str
