from __future__ import annotations

from fastapi.testclient import TestClient


def test_search_returns_suggestions_sorted_by_similarity(client: TestClient) -> None:
    resp = client.post("/api/search", json={"liked_names": ["דוד", "יוסף"], "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["liked"]) == 2
    assert {p["name"] for p in body["liked"]} == {"דוד", "יוסף"}

    suggestions = body["suggestions"]
    assert 1 <= len(suggestions) <= 5

    liked_names = {"דוד", "יוסף"}
    for s in suggestions:
        assert s["name"] not in liked_names
        assert 0.0 <= s["similarity"] <= 1.0
        assert s["sex"] in {"M", "F"}
        assert s["popularity"] >= 0

    similarities = [s["similarity"] for s in suggestions]
    assert similarities == sorted(similarities, reverse=True)


def test_search_respects_top_k(client: TestClient) -> None:
    resp = client.post("/api/search", json={"liked_names": ["שרה"], "top_k": 3})
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) == 3


def test_search_rejects_empty_liked_names(client: TestClient) -> None:
    resp = client.post("/api/search", json={"liked_names": []})
    assert resp.status_code == 422


def test_search_rejects_non_hebrew_input(client: TestClient) -> None:
    resp = client.post("/api/search", json={"liked_names": ["David"]})
    assert resp.status_code == 422
