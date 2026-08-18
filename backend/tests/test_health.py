from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["corpus_size"] > 0


def test_health_reports_both_models(client: TestClient) -> None:
    resp = client.get("/api/health")
    body = resp.json()
    models = {m["id"]: m for m in body["models"]}

    assert set(models) == {"written_similarity", "cultural_similarity"}
    assert models["written_similarity"]["dim"] == 100
    assert models["cultural_similarity"]["dim"] == 384
    for info in models.values():
        assert info["corpus_vectors"] > 0
        assert info["display_name"]
