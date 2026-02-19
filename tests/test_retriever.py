"""
Unit tests for app.retriever: distance_to_similarity, classify_result, embed_query, search.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.retriever import (
    classify_result,
    distance_to_similarity,
    embed_query,
    search,
)


class TestDistanceToSimilarity:
    def test_distance_zero_gives_similarity_one(self):
        assert distance_to_similarity(0.0) == 1.0

    def test_distance_two_gives_similarity_zero(self):
        assert distance_to_similarity(2.0) == 0.0

    def test_distance_one_gives_similarity_half(self):
        assert distance_to_similarity(1.0) == 0.5

    def test_other_values(self):
        assert distance_to_similarity(0.5) == 0.75
        assert distance_to_similarity(1.5) == 0.25


class TestClassifyResult:
    def test_direct_match(self):
        assert classify_result(0.75) == "direct"
        assert classify_result(0.9) == "direct"
        assert classify_result(1.0) == "direct"

    def test_closest_match(self):
        assert classify_result(0.45) == "closest"
        assert classify_result(0.6) == "closest"
        assert classify_result(0.74) == "closest"

    def test_no_match(self):
        assert classify_result(0.44) == "no_match"
        assert classify_result(0.0) == "no_match"

    def test_boundary_values(self):
        assert classify_result(0.75) == "direct"
        assert classify_result(0.45) == "closest"
        assert classify_result(0.449) == "no_match"


class TestEmbedQuery:
    @patch("app.retriever.openai_client")
    def test_returns_embedding_from_openai(self, mock_client):
        fake_embedding = [0.1, -0.2, 0.3]
        mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=fake_embedding)]
        )
        result = embed_query("test query")
        assert result == fake_embedding
        mock_client.embeddings.create.assert_called_once()


class TestSearch:
    def test_empty_query_returns_empty_list(self):
        result = search("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = search("   ")
        assert result == []

    @patch("app.retriever.api_collection")
    @patch("app.retriever.embed_query")
    def test_returns_parsed_results_with_similarity_and_match_type(
        self, mock_embed, mock_collection, sample_api_record
    ):
        mock_embed.return_value = [0.0] * 1536  # typical embedding size
        mock_collection.query.return_value = {
            "ids": [["api_001"]],
            "distances": [[0.2]],
            "metadatas": [[{"record": json.dumps(sample_api_record)}]],
            "documents": [["doc text"]],
        }
        results = search("customer orders", n_results=1)
        assert len(results) == 1
        r = results[0]
        assert r["id"] == "api_001"
        assert r["record"] == sample_api_record
        assert r["similarity"] == 0.9  # 1 - 0.2/2
        assert r["match_type"] == "direct"
        assert "distance" in r

    @patch("app.retriever.api_collection")
    @patch("app.retriever.embed_query")
    def test_malformed_metadata_record_yields_empty_record(self, mock_embed, mock_collection):
        mock_embed.return_value = [0.0] * 1536
        # distance 0.8 -> similarity 0.6 -> "closest"
        mock_collection.query.return_value = {
            "ids": [["api_001"]],
            "distances": [[0.8]],
            "metadatas": [[{"record": "not valid json"}]],
            "documents": [[None]],
        }
        results = search("something", n_results=1)
        assert len(results) == 1
        assert results[0]["record"] == {}
        assert results[0]["match_type"] == "closest"

    @patch("app.retriever.api_collection")
    @patch("app.retriever.embed_query")
    def test_missing_metadata_yields_empty_record(self, mock_embed, mock_collection):
        mock_embed.return_value = [0.0] * 1536
        mock_collection.query.return_value = {
            "ids": [["api_001"]],
            "distances": [[0.1]],
            "metadatas": [[None]],
            "documents": [[None]],
        }
        results = search("query", n_results=1)
        assert len(results) == 1
        assert results[0]["record"] == {}
        assert results[0]["match_type"] == "direct"
