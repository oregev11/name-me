from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nameme.main import create_app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Uses the real committed artifacts (small corpus, fast to load) rather
    # than mocking, so the tests exercise the actual embedding/search/PCA
    # pipeline end to end.
    app = create_app()
    with TestClient(app) as c:
        yield c
