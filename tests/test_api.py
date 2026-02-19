"""
API tests for FastAPI endpoints: GET /, GET /health, GET /catalog, POST /search, POST /ingest,
POST /api/rag/lookup, idea/LLM/jira endpoints.
"""
from pathlib import Path
from unittest.mock import patch

import pytest


class TestUI:
    @patch("app.main.UI_INDEX", new_callable=lambda: Path("/nonexistent/index.html"))
    def test_ui_fallback_when_file_missing(self, _patched_ui_index, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "docs" in data

    def test_ui_returns_file_when_index_exists(self, client):
        # UI_INDEX is real static/index.html in repo
        resp = client.get("/")
        assert resp.status_code == 200
        # FileResponse: could be text/html or application/octet-stream
        assert "html" in resp.headers.get("content-type", "").lower() or len(resp.content) > 0


class TestCatalog:
    def test_catalog_returns_apis_when_file_exists(self, client):
        resp = client.get("/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "apis" in data
        assert isinstance(data["apis"], list)

    @patch("app.main.DATA_PATH", new_callable=lambda: Path("/nonexistent/apis.json"))
    def test_catalog_404_when_file_missing(self, _patched_data_path, client):
        resp = client.get("/catalog")
        assert resp.status_code == 404
        assert "detail" in resp.json()


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

    @patch("app.retriever.search")
    def test_search_closest_returns_no_enhancement_suggestion(
        self, mock_search, client, sample_retriever_results
    ):
        sample_retriever_results[0]["match_type"] = "closest"
        sample_retriever_results[0]["similarity"] = 0.6
        mock_search.return_value = sample_retriever_results
        resp = client.post("/search", json={"query": "orders"})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert results[0]["enhancement_suggestion"] is None

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
                "similarity": 0.96,
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
        assert data["confidence_score"] == 0.96
        assert data["build_required"] is False
        assert data["matched_api"] is not None
        assert data["matched_api"]["name"] == "Store Location API"
        assert data["matched_api"]["endpoint"] == "/v1/stores"
        assert data["matched_api"]["author"] == "Jane Doe"
        assert data["matched_api"]["team"] == "Retail & Store APIs"
        assert data["matched_api"]["status"] == "production"

    @patch("app.retriever.search")
    def test_rag_lookup_below_95_confidence_returns_none_and_build_required(
        self, mock_search, client
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
        assert data["match_status"] == "none"
        assert data["matched_api"]["name"] == "Bank Check Balance API"
        assert data["enhancements"] == []
        assert data["build_required"] is True

    @patch("app.retriever.search")
    def test_rag_lookup_low_similarity_none_build_required_true(self, mock_search, client):
        mock_search.return_value = [
            {
                "id": "api-x",
                "record": {"id": "api-x", "name": "Near Match", "path": "/v1/near", "input": {}, "output": {}},
                "similarity": 0.55,
                "match_type": "closest",
            },
        ]
        resp = client.post(
            "/api/rag/lookup",
            json={"query_key": "k", "description": "exact capability", "top_k": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_status"] == "none"
        assert data["confidence_score"] == 0.55
        assert data["build_required"] is True

    def test_rag_lookup_empty_description_validation_error(self, client):
        resp = client.post(
            "/api/rag/lookup",
            json={"query_key": "k", "description": "", "top_k": 3},
        )
        assert resp.status_code == 422

    def test_rag_lookup_top_k_out_of_bounds_validation_error(self, client):
        resp = client.post(
            "/api/rag/lookup",
            json={"query_key": "k", "description": "x", "top_k": 0},
        )
        assert resp.status_code == 422
        resp2 = client.post(
            "/api/rag/lookup",
            json={"query_key": "k", "description": "x", "top_k": 21},
        )
        assert resp2.status_code == 422

    @patch("app.retriever.search")
    def test_rag_lookup_with_context_and_expected_io(self, mock_search, client):
        mock_search.return_value = [
            {
                "id": "api-orders",
                "record": {"id": "api-orders", "name": "Orders API", "path": "/v1/orders", "input": {}, "output": {}},
                "similarity": 0.91,
                "match_type": "direct",
            },
        ]
        resp = client.post(
            "/api/rag/lookup",
            json={
                "query_key": "orders_step",
                "description": "get customer orders",
                "context": {"product_idea": "Shop", "persona": "Buyer", "journey": "Checkout", "step_label": "View orders"},
                "expected_io": {"input_schema": "customer_id", "output_schema": "orders[]"},
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_key"] == "orders_step"
        assert data["match_status"] == "exact"
        assert data["matched_api"]["name"] == "Orders API"
        # Retriever was called with query built from description + context + expected_io
        call_args = mock_search.call_args
        query = call_args[0][0]
        assert "get customer orders" in query
        assert "Product: Shop" in query or "Shop" in query
        assert "Persona: Buyer" in query or "Buyer" in query
        assert "Expected input" in query or "customer_id" in query


class TestIdeaFeatures:
    @patch("app.main.idea_module.generate_features")
    def test_idea_features_success(self, mock_gen, client):
        mock_gen.return_value = {"features": [{"id": "f1", "icon": "🔐", "title": "Auth", "desc": "Login", "on": True}]}
        resp = client.post("/idea/features", json={"idea": "A mobile banking app"})
        assert resp.status_code == 200
        assert resp.json()["features"]

    def test_idea_features_empty_idea_validation_error(self, client):
        resp = client.post("/idea/features", json={"idea": ""})
        assert resp.status_code == 422

    @patch("app.main.idea_module.generate_features")
    def test_idea_features_value_error_returns_400(self, mock_gen, client):
        mock_gen.side_effect = ValueError("Invalid idea")
        resp = client.post("/idea/features", json={"idea": "x"})
        assert resp.status_code == 400

    @patch("app.main.idea_module.generate_features")
    def test_idea_features_exception_returns_500(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("LLM down")
        resp = client.post("/idea/features", json={"idea": "A cool app"})
        assert resp.status_code == 500


class TestLLMFeatures:
    @patch("app.main.idea_module.generate_llm_features")
    def test_llm_features_success(self, mock_gen, client):
        mock_gen.return_value = {
            "features": [{"id": "auth", "icon": "🔐", "title": "Auth", "desc": "Login", "on": True}],
            "idea_summary": "Summary",
            "model_used": "gpt-4o",
        }
        resp = client.post(
            "/llm/features",
            json={"idea": "A mobile banking app with login and transfers"},
        )
        assert resp.status_code == 200
        assert "features" in resp.json()

    @patch("app.main.idea_module.generate_llm_features")
    def test_llm_features_feature_parse_error_returns_422(self, mock_gen, client):
        from app.idea import FeatureParseError
        mock_gen.side_effect = FeatureParseError()
        resp = client.post(
            "/llm/features",
            json={"idea": "A mobile banking app with login and transfers"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"].get("error_code") == "FEATURE_PARSE_FAILED"

    @patch("app.main.idea_module.generate_llm_features")
    def test_llm_features_value_error_returns_400(self, mock_gen, client):
        mock_gen.side_effect = ValueError("Bad request")
        resp = client.post(
            "/llm/features",
            json={"idea": "A mobile banking app with login and transfers"},
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.generate_llm_features")
    def test_llm_features_exception_returns_500(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("Unexpected")
        resp = client.post(
            "/llm/features",
            json={"idea": "A mobile banking app with login and transfers"},
        )
        assert resp.status_code == 500


class TestLLMSuggestPersonas:
    @patch("app.main.idea_module.suggest_personas")
    def test_llm_suggest_personas_success(self, mock_suggest, client):
        mock_suggest.return_value = {
            "personas": [{"id": "p1", "label": "User", "icon": "👤", "desc": "End user", "color": "blue", "rationale": "x", "suggested_journeys": [], "is_primary": True}],
            "model_used": "gpt-4o",
        }
        resp = client.post(
            "/llm/suggest-personas",
            json={"idea": "Banking app", "idea_summary": "Summary", "selected_features": []},
        )
        assert resp.status_code == 200
        assert "personas" in resp.json()

    @patch("app.main.idea_module.suggest_personas")
    def test_llm_suggest_personas_value_error_returns_400(self, mock_suggest, client):
        mock_suggest.side_effect = ValueError("Bad")
        resp = client.post(
            "/llm/suggest-personas",
            json={"idea": "x", "idea_summary": "y", "selected_features": []},
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.suggest_personas")
    def test_llm_suggest_personas_exception_returns_500(self, mock_suggest, client):
        mock_suggest.side_effect = RuntimeError("LLM error")
        resp = client.post(
            "/llm/suggest-personas",
            json={"idea": "x", "idea_summary": "y", "selected_features": []},
        )
        assert resp.status_code == 500


class TestLLMGenerateJourneys:
    @patch("app.main.idea_module.generate_journeys")
    def test_llm_generate_journeys_success(self, mock_gen, client):
        mock_gen.return_value = {
            "personas": [{"id": "p1", "journeys": [{"id": "j1", "title": "Browse", "steps": [{"id": "s1", "label": "Search", "icon": "🔍", "api": "product_search"}]}]}],
            "unique_api_keys": ["product_search"],
            "model_used": "gpt-4o",
        }
        resp = client.post(
            "/llm/generate-journeys",
            json={
                "idea": "Shop",
                "selected_features": [],
                "confirmed_personas": [{"id": "p1", "label": "User", "icon": "👤", "desc": "User", "color": "blue", "suggested_journeys": []}],
            },
        )
        assert resp.status_code == 200
        assert "personas" in resp.json()

    @patch("app.main.idea_module.generate_journeys")
    def test_llm_generate_journeys_value_error_returns_400(self, mock_gen, client):
        mock_gen.side_effect = ValueError("Bad")
        resp = client.post(
            "/llm/generate-journeys",
            json={
                "idea": "x",
                "confirmed_personas": [{"id": "p1", "label": "L", "icon": "👤", "desc": "d", "color": "blue", "suggested_journeys": []}],
            },
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.generate_journeys")
    def test_llm_generate_journeys_exception_returns_500(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("Error")
        resp = client.post(
            "/llm/generate-journeys",
            json={
                "idea": "x",
                "confirmed_personas": [{"id": "p1", "label": "L", "icon": "👤", "desc": "d", "color": "blue", "suggested_journeys": []}],
            },
        )
        assert resp.status_code == 500


class TestLLMDescribe:
    @patch("app.main.idea_module.describe")
    def test_llm_describe_success(self, mock_describe, client):
        mock_describe.return_value = {
            "api_key": "product_search",
            "description": "Search products by query.",
            "input_schema": "query: string",
            "output_schema": "results: array",
        }
        resp = client.post(
            "/llm/describe",
            json={
                "api_key": "product_search",
                "idea": "E-commerce",
                "step_label": "Search",
                "persona_label": "Shopper",
                "journey_title": "Browse",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["api_key"] == "product_search"
        assert "description" in resp.json()

    @patch("app.main.idea_module.describe")
    def test_llm_describe_value_error_returns_400(self, mock_describe, client):
        mock_describe.side_effect = ValueError("Bad")
        resp = client.post(
            "/llm/describe",
            json={
                "api_key": "k",
                "idea": "x",
                "step_label": "s",
                "persona_label": "p",
                "journey_title": "j",
            },
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.describe")
    def test_llm_describe_exception_returns_500(self, mock_describe, client):
        mock_describe.side_effect = RuntimeError("Error")
        resp = client.post(
            "/llm/describe",
            json={
                "api_key": "k",
                "idea": "x",
                "step_label": "s",
                "persona_label": "p",
                "journey_title": "j",
            },
        )
        assert resp.status_code == 500


class TestLLMChat:
    @patch("app.main.idea_module.chat")
    def test_llm_chat_success(self, mock_chat, client):
        mock_chat.return_value = {
            "reply": "What problem are you trying to solve?",
            "is_ready_to_summarise": False,
            "turn_count": 1,
            "model_used": "gpt-4o",
        }
        resp = client.post(
            "/llm/chat",
            json={"messages": [{"role": "user", "content": "I want to build a booking app"}], "idea_context": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "What problem are you trying to solve?"
        assert data["is_ready_to_summarise"] is False
        assert data["turn_count"] == 1
        assert data["model_used"] == "gpt-4o"

    @patch("app.main.idea_module.chat")
    def test_llm_chat_value_error_returns_400(self, mock_chat, client):
        mock_chat.side_effect = ValueError("Bad request")
        resp = client.post(
            "/llm/chat",
            json={"messages": [{"role": "user", "content": "Hi"}], "idea_context": ""},
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.chat")
    def test_llm_chat_exception_returns_500(self, mock_chat, client):
        mock_chat.side_effect = RuntimeError("LLM error")
        resp = client.post(
            "/llm/chat",
            json={"messages": [{"role": "user", "content": "Hi"}], "idea_context": ""},
        )
        assert resp.status_code == 500


class TestLLMSummarise:
    @patch("app.main.idea_module.summarise")
    def test_llm_summarise_success(self, mock_summarise, client):
        mock_summarise.return_value = {
            "idea": "A clinic booking app for patients and staff.",
            "idea_summary": "Product for booking appointments.",
            "detailed_description": "Full description here.",
            "inferred_features": [
                {"title": "Appointment booking", "description": "Book and manage appointments."},
            ],
            "use_cases": [
                {"persona": "Patient", "goal": "Book a visit", "workflow": "Search, pick slot, confirm."},
            ],
            "constraints": [],
            "open_questions": [],
            "model_used": "gpt-4o",
        }
        resp = client.post(
            "/llm/summarise",
            json={
                "messages": [
                    {"role": "user", "content": "I want a booking app"},
                    {"role": "assistant", "content": "Who will use it?"},
                    {"role": "user", "content": "Patients and clinic staff"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "idea" in data
        assert "inferred_features" in data
        assert data["model_used"] == "gpt-4o"

    @patch("app.main.idea_module.summarise")
    def test_llm_summarise_value_error_returns_400(self, mock_summarise, client):
        mock_summarise.side_effect = ValueError("Invalid JSON")
        resp = client.post(
            "/llm/summarise",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.summarise")
    def test_llm_summarise_exception_returns_500(self, mock_summarise, client):
        mock_summarise.side_effect = RuntimeError("LLM error")
        resp = client.post(
            "/llm/summarise",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert resp.status_code == 500


class TestIdeaPersonas:
    @patch("app.main.idea_module.generate_personas")
    def test_idea_personas_success(self, mock_gen, client):
        mock_gen.return_value = {
            "personas": [{"id": "p1", "label": "User", "icon": "👤", "color": "blue", "colorBg": "#eee", "colorBorder": "#ccc", "desc": "User", "journeys": [{"id": "j1", "title": "J", "steps": []}]}],
        }
        resp = client.post("/idea/personas", json={"idea": "Banking app", "feature_ids": ["auth"]})
        assert resp.status_code == 200
        assert "personas" in resp.json()

    @patch("app.main.idea_module.generate_personas")
    def test_idea_personas_value_error_returns_400(self, mock_gen, client):
        mock_gen.side_effect = ValueError("Bad")
        resp = client.post("/idea/personas", json={"idea": "x", "feature_ids": []})
        assert resp.status_code == 400

    @patch("app.main.idea_module.generate_personas")
    def test_idea_personas_exception_returns_500(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("Error")
        resp = client.post("/idea/personas", json={"idea": "x", "feature_ids": []})
        assert resp.status_code == 500


class TestJiraGenerate:
    @patch("app.main.idea_module.generate_jira_stories")
    def test_jira_generate_success(self, mock_gen, client):
        mock_gen.return_value = {
            "stories": [{"title": "API X", "epic": "E", "priority": "P1", "story": "As a...", "acceptance": [], "sp": 3, "days": 5, "sprint": "S1", "squad": "S", "deps": []}],
        }
        resp = client.post(
            "/jira/generate",
            json={"missing_steps": [{"label": "Step", "search_text": "search products", "journey_title": "J", "persona_label": "P"}]},
        )
        assert resp.status_code == 200
        assert "stories" in resp.json()

    @patch("app.main.idea_module.generate_jira_stories")
    def test_jira_generate_value_error_returns_400(self, mock_gen, client):
        mock_gen.side_effect = ValueError("Bad")
        resp = client.post(
            "/jira/generate",
            json={"missing_steps": [{"label": "S", "search_text": "x", "journey_title": "", "persona_label": ""}]},
        )
        assert resp.status_code == 400

    @patch("app.main.idea_module.generate_jira_stories")
    def test_jira_generate_exception_returns_500(self, mock_gen, client):
        mock_gen.side_effect = RuntimeError("Error")
        resp = client.post(
            "/jira/generate",
            json={"missing_steps": [{"label": "S", "search_text": "x", "journey_title": "", "persona_label": ""}]},
        )
        assert resp.status_code == 500
