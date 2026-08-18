from __future__ import annotations

from fastapi.testclient import TestClient


def test_autocomplete_matches_prefix(client: TestClient) -> None:
    resp = client.get("/api/autocomplete", params={"q": "דו", "limit": 10})
    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) > 0
    assert all("דו" in m for m in matches)
    # Prefix matches should be ranked before non-prefix substring matches.
    prefix_matches = [m for m in matches if m.startswith("דו")]
    assert matches[: len(prefix_matches)] == prefix_matches


def test_autocomplete_respects_limit(client: TestClient) -> None:
    resp = client.get("/api/autocomplete", params={"q": "א", "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()["matches"]) <= 3


def test_autocomplete_requires_query(client: TestClient) -> None:
    resp = client.get("/api/autocomplete")
    assert resp.status_code == 422
