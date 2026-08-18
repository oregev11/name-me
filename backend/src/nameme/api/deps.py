"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from nameme.corpus.loader import CorpusStore


def get_corpus_store(request: Request) -> CorpusStore:
    return request.app.state.corpus_store
