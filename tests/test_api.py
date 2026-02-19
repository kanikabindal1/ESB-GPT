"""
API tests for FastAPI endpoints: GET /health, POST /search, POST /ingest.
"""
from unittest.mock import patch

import pytest


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSearch:
    @patch("app.retriever.search")
    def test_search_returns_results_from_retriever(
        self, mock_search, client, sample_retriever_results
    ):
        mock_search.return_value = sample_retriever_results
        resp = client.post("/search", json={"query": "customer orders"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2
        first = data["results"][0]
        assert first["api_id"] == "api_001"
        assert first["score"] == 0.9
        assert first["match_type"] == "direct"
        assert first["name"] == "GetCustomerOrders"

    @patch("app.recommender.get_enhancement_suggestion")
    @patch("app.retriever.search")
    def test_search_calls_enhancement_for_closest_once(
        self, mock_search, mock_enhancement, client, sample_retriever_results
    ):
        sample_retriever_results[0]["match_type"] = "closest"
        sample_retriever_results[0]["similarity"] = 0.6
        mock_search.return_value = sample_retriever_results
        mock_enhancement.return_value = "Consider adding a filter."
        resp = client.post("/search", json={"query": "orders"})
        assert resp.status_code == 200
        assert mock_enhancement.call_count == 1
        results = resp.json()["results"]
        assert results[0]["enhancement_suggestion"] == "Consider adding a filter."

    @patch("app.retriever.search")
    def test_search_recommender_exception_leaves_suggestion_none(
        self, mock_search, client, sample_retriever_results
    ):
        sample_retriever_results[0]["match_type"] = "closest"
        mock_search.return_value = sample_retriever_results
        with patch("app.recommender.get_enhancement_suggestion", side_effect=Exception("LLM error")):
            resp = client.post("/search", json={"query": "orders"})
        assert resp.status_code == 200
        assert resp.json()["results"][0]["enhancement_suggestion"] is None

    def test_search_empty_query_validation_error(self, client):
        resp = client.post("/search", json={"query": ""})
        assert resp.status_code == 422

    @patch("app.retriever.search")
    def test_search_all_no_match(self, mock_search, client):
        mock_search.return_value = [
            {
                "id": "api_001",
                "record": {"id": "api_001", "name": "X", "description": "Y", "input": {}, "output": {}},
                "distance": 1.5,
                "similarity": 0.25,
                "match_type": "no_match",
            },
        ]
        resp = client.post("/search", json={"query": "something unrelated"})
        assert resp.status_code == 200
        assert resp.json()["results"][0]["match_type"] == "no_match"
        assert resp.json()["results"][0]["enhancement_suggestion"] is None


class TestIngest:
    @patch("scripts.ingest.run_ingest")
    def test_ingest_returns_ok_and_upserted_count(self, mock_run_ingest, client):
        mock_run_ingest.return_value = 42
        resp = client.post("/ingest")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "upserted": 42}

    @patch("scripts.ingest.run_ingest")
    def test_ingest_file_not_found_returns_404(self, mock_run_ingest, client):
        mock_run_ingest.side_effect = FileNotFoundError("data/apis.json not found.")
        resp = client.post("/ingest")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower() or "apis.json" in resp.json()["detail"]

    @patch("scripts.ingest.run_ingest")
    def test_ingest_value_error_returns_400(self, mock_run_ingest, client):
        mock_run_ingest.side_effect = ValueError("Set OPENAI_API_KEY in .env")
        resp = client.post("/ingest")
        assert resp.status_code == 400
        assert "OPENAI_API_KEY" in resp.json()["detail"]

    @patch("scripts.ingest.run_ingest")
    def test_ingest_generic_exception_returns_500(self, mock_run_ingest, client):
        mock_run_ingest.side_effect = RuntimeError("Unexpected error")
        resp = client.post("/ingest")
        assert resp.status_code == 500
        assert "Unexpected error" in resp.json()["detail"]
