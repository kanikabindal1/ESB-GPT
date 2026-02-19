"""
Unit tests for scripts.ingest: flatten_record, run_ingest (with mocks).
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.ingest import flatten_record, run_ingest


class TestFlattenRecord:
    def test_minimal_record(self):
        record = {"id": "api_1", "name": "Foo"}
        out = flatten_record(record)
        assert "Foo" in out
        assert "—" in out or "Foo" in out

    def test_full_record(self, sample_api_record):
        out = flatten_record(sample_api_record)
        assert "GetCustomerOrders" in out
        assert "Retrieves all orders" in out
        assert "order history" in out or "customer lookup" in out
        assert "customer_id" in out
        assert "orders" in out
        assert "GET" in out
        assert "/customers" in out
        assert "e-commerce" in out

    def test_empty_and_malformed_fields(self):
        record = {
            "id": "x",
            "name": "N",
            "description": "",
            "use_cases": "not a list",
            "input": [],
            "output": None,
            "method": "",
            "endpoint": "",
            "tags": 123,
        }
        out = flatten_record(record)
        assert "N" in out
        assert isinstance(out, str)
        assert len(out) >= 1

    def test_empty_input_output_dict(self):
        record = {"id": "y", "name": "Bar", "description": "Desc", "input": {}, "output": {}}
        out = flatten_record(record)
        assert "Bar" in out
        assert "Desc" in out


class TestRunIngest:
    def test_missing_file_raises_file_not_found(self):
        with patch("scripts.ingest.DATA_PATH", Path("/nonexistent/apis.json")):
            with pytest.raises(FileNotFoundError, match="not found"):
                run_ingest()

    def test_missing_api_key_raises_value_error(self):
        with patch("scripts.ingest.DATA_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("scripts.ingest.os.getenv", return_value=None):
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    run_ingest()

    def test_placeholder_api_key_raises_value_error(self):
        with patch("scripts.ingest.DATA_PATH") as mock_path:
            mock_path.exists.return_value = True
            with patch("scripts.ingest.os.getenv", return_value="your_key_here"):
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    run_ingest()

    def test_empty_json_array_returns_zero(self, tmp_path):
        data_file = tmp_path / "apis.json"
        data_file.write_text("[]", encoding="utf-8")
        with patch("scripts.ingest.DATA_PATH", data_file):
            with patch("scripts.ingest.os.getenv", return_value="test-key"):
                count = run_ingest()
        assert count == 0

    def test_ingest_upserts_and_returns_count(self, tmp_path, sample_api_record):
        records = [
            sample_api_record,
            {"id": "api_002", "name": "Other", "description": "Other API"},
        ]
        data_file = tmp_path / "apis.json"
        data_file.write_text(json.dumps(records), encoding="utf-8")
        fake_embedding = [0.0] * 1536
        mock_embeddings_response = MagicMock()
        mock_embeddings_response.data = [
            MagicMock(index=0, embedding=fake_embedding),
            MagicMock(index=1, embedding=fake_embedding),
        ]
        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = mock_embeddings_response
        mock_collection = MagicMock()
        mock_chroma = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection

        with patch("scripts.ingest.DATA_PATH", data_file):
            with patch("scripts.ingest.os.getenv", return_value="test-key"):
                with patch("scripts.ingest.OpenAI", return_value=mock_openai):
                    with patch("scripts.ingest.chromadb.PersistentClient", return_value=mock_chroma):
                        count = run_ingest()
        assert count == 2
        mock_collection.upsert.assert_called_once()
        call_kw = mock_collection.upsert.call_args[1]
        assert call_kw["ids"] == ["api_001", "api_002"]
        assert len(call_kw["embeddings"]) == 2
        assert len(call_kw["documents"]) == 2
        assert len(call_kw["metadatas"]) == 2

    def test_records_without_id_skipped(self, tmp_path):
        records = [
            {"id": "api_001", "name": "One"},
            {"name": "NoId"},
            {"id": "api_003", "name": "Three"},
        ]
        data_file = tmp_path / "apis.json"
        data_file.write_text(json.dumps(records), encoding="utf-8")
        fake_embedding = [0.0] * 1536
        mock_embeddings_response = MagicMock()
        mock_embeddings_response.data = [
            MagicMock(index=0, embedding=fake_embedding),
            MagicMock(index=1, embedding=fake_embedding),
        ]
        mock_openai = MagicMock()
        mock_openai.embeddings.create.return_value = mock_embeddings_response
        mock_collection = MagicMock()
        mock_chroma = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection

        with patch("scripts.ingest.DATA_PATH", data_file):
            with patch("scripts.ingest.os.getenv", return_value="test-key"):
                with patch("scripts.ingest.OpenAI", return_value=mock_openai):
                    with patch("scripts.ingest.chromadb.PersistentClient", return_value=mock_chroma):
                        count = run_ingest()
        assert count == 2
        call_kw = mock_collection.upsert.call_args[1]
        assert call_kw["ids"] == ["api_001", "api_003"]
