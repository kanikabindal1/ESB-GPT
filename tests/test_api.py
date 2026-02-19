"""
API tests for FastAPI endpoints: GET /health, POST /search, POST /ingest, POST /api/rag/lookup.
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


class TestRAGLookup:
    @patch("app.retriever.search")
    def test_rag_lookup_none_returns_none_status(self, mock_search, client):
        mock_search.return_value = []
        resp = client.post(
            "/api/rag/lookup",
            json={
                "query_key": "secure_messaging",
                "description": "HIPAA-compliant encrypted messaging",
                "top_k": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_key"] == "secure_messaging"
        assert data["match_status"] == "none"
        assert data["confidence_score"] == 0.0
        assert data["matched_api"] is None
        assert data["build_required"] is True
        assert data["enhancements"] == []

    @patch("app.retriever.search")
    def test_rag_lookup_exact_returns_matched_api_and_build_not_required(
        self, mock_search, client
    ):
        mock_search.return_value = [
            {
                "id": "api-store-location",
                "record": {
                    "id": "api-store-location",
                    "name": "Store Location API",
                    "path": "/v1/stores",
                    "method": "GET",
                    "owner": "Jane Doe",
                    "team": "Retail & Store APIs",
                    "readiness": "production",
                    "version": "1.2.0",
                    "description": "Get store locations.",
                    "input": {},
                    "output": {},
                },
                "similarity": 0.92,
                "match_type": "direct",
            },
        ]
        resp = client.post(
            "/api/rag/lookup",
            json={
                "query_key": "store_lookup",
                "description": "find stores near me",
                "top_k": 3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_status"] == "exact"
        assert data["confidence_score"] == 0.92
        assert data["build_required"] is False
        assert data["matched_api"] is not None
        assert data["matched_api"]["name"] == "Store Location API"
        assert data["matched_api"]["endpoint"] == "/v1/stores"
        assert data["matched_api"]["author"] == "Jane Doe"
        assert data["matched_api"]["team"] == "Retail & Store APIs"
        assert data["matched_api"]["status"] == "production"

    @patch("app.recommender.get_enhancement_suggestion")
    @patch("app.retriever.search")
    def test_rag_lookup_partial_includes_enhancements(
        self, mock_search, mock_enhancement, client
    ):
        mock_search.return_value = [
            {
                "id": "api-bank-check",
                "record": {
                    "id": "api-bank-check",
                    "name": "Bank Check Balance API",
                    "path": "/v1/accounts/verify",
                    "method": "POST",
                    "owner": "Alice Chen",
                    "team": "Payments",
                    "readiness": "production",
                    "description": "Verify bank account.",
                    "input": {},
                    "output": {},
                },
                "similarity": 0.65,
                "match_type": "closest",
            },
        ]
        mock_enhancement.return_value = "1. Add idempotency.\n2. What is missing: retry policy."
        resp = client.post(
            "/api/rag/lookup",
            json={
                "query_key": "balance_check",
                "description": "check account balance with retry",
                "top_k": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_status"] == "partial"
        assert data["matched_api"]["name"] == "Bank Check Balance API"
        assert "enhancements" in data
        assert data["build_required"] is False  # 0.65 >= 0.60
