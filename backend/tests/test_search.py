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


def test_search_defaults_to_written_similarity_when_model_omitted(client: TestClient) -> None:
    with_default = client.post("/api/search", json={"liked_names": ["דוד"], "top_k": 5})
    explicit = client.post(
        "/api/search",
        json={"liked_names": ["דוד"], "top_k": 5, "model": "written_similarity"},
    )
    assert with_default.status_code == explicit.status_code == 200
    assert with_default.json() == explicit.json()


def test_search_with_cultural_similarity_model(client: TestClient) -> None:
    resp = client.post(
        "/api/search",
        json={"liked_names": ["דוד", "יוסף"], "top_k": 5, "model": "cultural_similarity"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["liked"]) == 2
    suggestions = body["suggestions"]
    assert 1 <= len(suggestions) <= 5
    for s in suggestions:
        assert -1.0 <= s["similarity"] <= 1.0  # sentence embeddings can be mildly negative

    similarities = [s["similarity"] for s in suggestions]
    assert similarities == sorted(similarities, reverse=True)


def test_search_rejects_unknown_model(client: TestClient) -> None:
    resp = client.post(
        "/api/search", json={"liked_names": ["דוד"], "model": "not_a_real_model"}
    )
    assert resp.status_code == 422


def test_search_default_top_k_is_20(client: TestClient) -> None:
    resp = client.post("/api/search", json={"liked_names": ["דוד"]})
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) == 20


def test_search_filters_by_sex(client: TestClient) -> None:
    # Wiring-level test: the filter is applied and changes the result set.
    # Exact per-item correctness (a name can pass a sex=F filter even when
    # its *dominant* displayed sex is M, e.g. mostly-boys names still given
    # to many girls) is covered precisely in test_corpus_store.py, since
    # the API response's `sex` field alone can't prove that from here.
    unfiltered = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 15, "sex": "any"}
    ).json()["suggestions"]
    filtered = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 15, "sex": "F"}
    )
    assert filtered.status_code == 200
    filtered_suggestions = filtered.json()["suggestions"]
    assert len(filtered_suggestions) > 0
    assert {s["name"] for s in filtered_suggestions} != {s["name"] for s in unfiltered}


def test_search_filters_by_sector(client: TestClient) -> None:
    resp = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 15, "sector": "Muslim"}
    )
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) > 0
    assert all("Muslim" in s["sectors"] for s in suggestions)


def test_search_rejects_unknown_sector(client: TestClient) -> None:
    resp = client.post(
        "/api/search", json={"liked_names": ["דוד"], "sector": "Not A Sector"}
    )
    assert resp.status_code == 422


def test_search_filters_by_popularity_top_10_percent(client: TestClient) -> None:
    all_names = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 20, "popularity": "all"}
    ).json()["suggestions"]
    top10 = client.post(
        "/api/search",
        json={"liked_names": ["דוד"], "top_k": 20, "popularity": "top_10_percent"},
    ).json()["suggestions"]

    assert len(top10) > 0
    # top_10_percent is strictly more exclusive -- every popularity in it
    # should be at least as high as the least popular unfiltered result.
    assert min(s["popularity"] for s in top10) >= min(s["popularity"] for s in all_names)


def test_search_filters_by_year_range(client: TestClient) -> None:
    # אילאן only has a yearly breakdown for 2015-2024; requesting an
    # earlier range must exclude it, requesting its actual range must not.
    old_range = client.post(
        "/api/search",
        json={"liked_names": ["דוד"], "top_k": 50, "year_min": 1949, "year_max": 1960},
    ).json()["suggestions"]
    recent_range = client.post(
        "/api/search",
        json={"liked_names": ["דוד"], "top_k": 50, "year_min": 2015, "year_max": 2024},
    ).json()["suggestions"]

    assert "אילאן" not in {s["name"] for s in old_range}
    # (Not asserting אילאן appears in recent_range -- it may simply not be
    # similar enough to "דוד" to rank in the top 50; the exclusion above is
    # the precise, always-true claim. See test_corpus_store.py for the
    # direct membership check.)
    assert {s["name"] for s in old_range} != {s["name"] for s in recent_range}


def test_search_rejects_year_min_greater_than_year_max(client: TestClient) -> None:
    resp = client.post(
        "/api/search", json={"liked_names": ["דוד"], "year_min": 2020, "year_max": 2000}
    )
    assert resp.status_code == 422


def test_search_full_year_range_matches_no_year_filter(client: TestClient) -> None:
    unfiltered = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 10}
    ).json()
    full_range = client.post(
        "/api/search",
        json={"liked_names": ["דוד"], "top_k": 10, "year_min": 1949, "year_max": 2024},
    ).json()
    assert unfiltered == full_range


def test_search_dissimilar_sort_reverses_ranking(client: TestClient) -> None:
    similar = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 10, "sort": "similar"}
    ).json()["suggestions"]
    dissimilar = client.post(
        "/api/search", json={"liked_names": ["דוד"], "top_k": 10, "sort": "dissimilar"}
    ).json()["suggestions"]

    assert {s["name"] for s in similar}.isdisjoint({s["name"] for s in dissimilar})
    sims = [s["similarity"] for s in dissimilar]
    assert sims == sorted(sims)  # ascending -- least similar first
    assert min(s["similarity"] for s in similar) > max(sims)
