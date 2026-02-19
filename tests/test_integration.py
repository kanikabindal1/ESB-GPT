"""
Integration tests: real ChromaDB (tmp path), ingest with mocked OpenAI, then search/rag without retriever mock.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Fixture path for minimal API catalog
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_APIS = FIXTURES_DIR / "apis.json"

# Embedding dimension for text-embedding-3-small
EMBEDDING_DIM = 1536


def _make_embedding(seed: float):
    """Deterministic embedding for testing."""
    return [seed] * EMBEDDING_DIM


class TestIngestThenSearch:
    """Run ingest into tmp ChromaDB (mocked OpenAI), then POST /search using that DB (mocked query embedding)."""

    @pytest.fixture(autouse=True)
    def _ensure_fixture_exists(self):
        assert FIXTURE_APIS.exists(), f"Fixture {FIXTURE_APIS} missing"

    def test_ingest_then_search_returns_matching_api(self, client, tmp_path):
        # Deterministic embeddings for the two fixture docs
        vec0 = _make_embedding(0.01)
        vec1 = _make_embedding(0.02)
        mock_embed_response = MagicMock()
        mock_embed_response.data = [
            MagicMock(index=0, embedding=vec0),
            MagicMock(index=1, embedding=vec1),
        ]
        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = mock_embed_response

        with patch("scripts.ingest.DATA_PATH", FIXTURE_APIS):
            with patch("scripts.ingest.DB_PATH", tmp_path):
                with patch("scripts.ingest.os.getenv", return_value="test-key"):
                    with patch("scripts.ingest.OpenAI", return_value=mock_openai):
                        from scripts.ingest import run_ingest
                        count = run_ingest()
        assert count == 2

        # Point app at the same ChromaDB
        import chromadb
        chroma_client = chromadb.PersistentClient(path=str(tmp_path))
        api_collection = chroma_client.get_or_create_collection(
            name="apis",
            metadata={"hnsw:space": "cosine"},
        )
        query_embedding = vec0  # same as first doc → top match
        mock_query_response = MagicMock()
        mock_query_response.data = [MagicMock(embedding=query_embedding)]
        mock_openai_for_query = MagicMock()
        mock_openai_for_query.embeddings.create.return_value = mock_query_response

        with patch("app.main.api_collection", api_collection):
            with patch("app.retriever.api_collection", api_collection):
                with patch("app.main.openai_client", mock_openai_for_query):
                    with patch("app.retriever.openai_client", mock_openai_for_query):
                        resp = client.post("/search", json={"query": "store locations"})

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        assert data["results"][0]["name"] == "Store Location API"
        assert data["results"][0]["api_id"] == "api-store-location"

    def test_ingest_then_rag_lookup_returns_match(self, client, tmp_path):
        vec0 = _make_embedding(0.01)
        vec1 = _make_embedding(0.02)
        mock_embed_response = MagicMock()
        mock_embed_response.data = [
            MagicMock(index=0, embedding=vec0),
            MagicMock(index=1, embedding=vec1),
        ]
        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = mock_embed_response

        with patch("scripts.ingest.DATA_PATH", FIXTURE_APIS):
            with patch("scripts.ingest.DB_PATH", tmp_path):
                with patch("scripts.ingest.os.getenv", return_value="test-key"):
                    with patch("scripts.ingest.OpenAI", return_value=mock_openai):
                        from scripts.ingest import run_ingest
                        run_ingest()

        import chromadb
        chroma_client = chromadb.PersistentClient(path=str(tmp_path))
        api_collection = chroma_client.get_or_create_collection(
            name="apis",
            metadata={"hnsw:space": "cosine"},
        )
        query_embedding = vec0
        mock_query_response = MagicMock()
        mock_query_response.data = [MagicMock(embedding=query_embedding)]
        mock_openai_for_query = MagicMock()
        mock_openai_for_query.embeddings.create.return_value = mock_query_response

        with patch("app.main.api_collection", api_collection):
            with patch("app.retriever.api_collection", api_collection):
                with patch("app.main.openai_client", mock_openai_for_query):
                    with patch("app.retriever.openai_client", mock_openai_for_query):
                        resp = client.post(
                            "/api/rag/lookup",
                            json={
                                "query_key": "store_lookup",
                                "description": "find stores",
                                "top_k": 3,
                            },
                        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_key"] == "store_lookup"
        assert data["match_status"] in ("exact", "partial")
        assert data["matched_api"] is not None
        assert data["matched_api"]["name"] == "Store Location API"
