"""
Unit tests for app.recommender: _format_io, get_enhancement_suggestion (with mock).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.recommender import _format_io, get_enhancement_suggestion


class TestFormatIo:
    def test_none_returns_em_dash(self):
        assert _format_io(None) == "—"

    def test_empty_dict_returns_em_dash(self):
        assert _format_io({}) == "—"

    def test_non_dict_returns_em_dash(self):
        assert _format_io([]) == "—"
        assert _format_io("x") == "—"

    def test_dict_formatted_as_k_v(self):
        assert _format_io({"a": "1", "b": "2"}) == "a: 1, b: 2"

    def test_single_key(self):
        assert _format_io({"x": "y"}) == "x: y"


class TestGetEnhancementSuggestion:
    @patch("app.recommender.openai_client")
    def test_returns_stripped_content(self, mock_client, sample_api_record):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(message=MagicMock(content="  Suggestion text here.  "))
            ]
        )
        result = get_enhancement_suggestion("get orders", sample_api_record)
        assert result == "Suggestion text here."

    @patch("app.recommender.openai_client")
    def test_prompt_contains_query_and_api_details(self, mock_client, sample_api_record):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )
        get_enhancement_suggestion("my requirement", sample_api_record)
        call = mock_client.chat.completions.create.call_args
        assert call.kwargs["model"] == "gpt-4o-mini"
        messages = call.kwargs["messages"]
        assert len(messages) == 1
        prompt = messages[0]["content"]
        assert "my requirement" in prompt
        assert "GetCustomerOrders" in prompt
        assert "Retrieves all orders" in prompt
        assert "customer_id" in prompt or "Inputs" in prompt
        assert "orders" in prompt or "Outputs" in prompt
