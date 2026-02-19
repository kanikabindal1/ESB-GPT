"""
Unit tests for app.idea: generate_features, generate_llm_features, suggest_personas,
generate_journeys, describe, generate_personas, generate_jira_stories. All LLM calls mocked.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.idea import FeatureParseError, generate_features
from app.models import (
    ConfirmedPersona,
    DescribeRequest,
    FeaturesRequest,
    GenerateJourneysRequest,
    SuggestPersonasRequest,
)


class TestGenerateFeatures:
    @patch("app.main.openai_client")
    def test_returns_features_from_valid_json_array(self, mock_client):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps([
                {"id": "auth", "icon": "🔐", "title": "Auth", "desc": "Login", "on": True},
                {"id": "cart", "icon": "🛒", "title": "Cart", "desc": "Cart", "on": True},
            ])))]
        )
        result = generate_features("A shopping app")
        assert len(result.features) == 2
        assert result.features[0].id == "auth"
        assert result.features[0].title == "Auth"
        mock_client.chat.completions.create.assert_called_once()
        call = mock_client.chat.completions.create.call_args
        assert call.kwargs["model"] == "gpt-4o-mini"
        assert "A shopping app" in call.kwargs["messages"][0]["content"]

    @patch("app.main.openai_client")
    def test_invalid_json_raises_value_error(self, mock_client):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        with pytest.raises(ValueError, match="valid JSON"):
            generate_features("idea")

    @patch("app.main.openai_client")
    def test_non_array_json_raises_value_error(self, mock_client):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"key": "value"}'))]
        )
        with pytest.raises(ValueError, match="JSON array"):
            generate_features("idea")


class TestGenerateLLMFeatures:
    @patch("app.main.openai_client")
    def test_returns_features_and_idea_summary(self, mock_client):
        payload = {
            "features": [
                {"id": "f1", "icon": "🔐", "title": "Auth", "desc": "Login", "on": True},
            ] * 9,
            "idea_summary": "A banking app.",
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import generate_llm_features
        req = FeaturesRequest(idea="A mobile banking app with login and transfers")
        result = generate_llm_features(req)
        assert len(result.features) >= 1
        assert result.idea_summary == "A banking app."
        assert result.model_used == "gpt-4o"
        call = mock_client.chat.completions.create.call_args
        assert call.kwargs["response_format"] == {"type": "json_object"}

    @patch("app.main.openai_client")
    def test_invalid_json_raises_feature_parse_error(self, mock_client):
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        from app.idea import generate_llm_features
        req = FeaturesRequest(idea="A mobile banking app with login and transfers")
        with pytest.raises(FeatureParseError):
            generate_llm_features(req)


class TestSuggestPersonas:
    @patch("app.main.openai_client")
    def test_returns_personas_with_valid_json(self, mock_client):
        payload = {
            "personas": [
                {"id": "guest", "label": "Guest", "icon": "👤", "desc": "Guest user", "color": "blue", "rationale": "x", "suggested_journeys": [], "is_primary": True},
            ],
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import suggest_personas
        req = SuggestPersonasRequest(idea="Shop", idea_summary="E-commerce", selected_features=[])
        result = suggest_personas(req)
        assert len(result.personas) == 1
        assert result.personas[0].id == "guest"
        assert result.personas[0].label == "Guest"
        call = mock_client.chat.completions.create.call_args
        assert call.kwargs["response_format"] == {"type": "json_object"}


class TestGenerateJourneys:
    @patch("app.main.openai_client")
    def test_returns_personas_with_journeys_and_unique_api_keys(self, mock_client):
        payload = {
            "personas": [
                {
                    "id": "p1",
                    "journeys": [
                        {
                            "id": "j1",
                            "title": "Browse",
                            "steps": [
                                {"id": "s1", "label": "Search", "icon": "🔍", "api": "product_search"},
                            ],
                        },
                    ],
                },
            ],
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import generate_journeys
        req = GenerateJourneysRequest(
            idea="Shop",
            selected_features=[],
            confirmed_personas=[
                ConfirmedPersona(id="p1", label="User", icon="👤", desc="User", color="blue", suggested_journeys=[]),
            ],
        )
        result = generate_journeys(req)
        assert len(result.personas) == 1
        assert len(result.personas[0].journeys) == 1
        assert result.personas[0].journeys[0].steps[0].api == "product_search"
        assert "product_search" in result.unique_api_keys


class TestDescribe:
    @patch("app.main.openai_client")
    def test_returns_description_and_schemas(self, mock_client):
        payload = {
            "description": "Search products by query and filters.",
            "input_schema": "query: string, filters: optional",
            "output_schema": "results: array of product objects",
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import describe
        req = DescribeRequest(
            api_key="product_search",
            idea="E-commerce",
            step_label="Search",
            persona_label="Shopper",
            journey_title="Browse",
        )
        result = describe(req)
        assert result.api_key == "product_search"
        assert "Search" in result.description or "query" in result.description
        assert result.input_schema
        assert result.output_schema


class TestGeneratePersonas:
    @patch("app.main.openai_client")
    def test_returns_personas_with_journeys_and_steps(self, mock_client):
        payload = {
            "personas": [
                {
                    "id": "guest",
                    "label": "Guest",
                    "icon": "👤",
                    "desc": "Guest",
                    "journeys": [
                        {"id": "j1", "title": "Browse", "steps": [{"id": "s1", "label": "Search", "icon": "🔍", "search_text": "search products"}]},
                    ],
                },
            ],
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import generate_personas
        result = generate_personas("Shop", ["auth"])
        assert len(result.personas) == 1
        assert result.personas[0].label == "Guest"
        assert len(result.personas[0].journeys) == 1
        assert result.personas[0].journeys[0].steps[0].search_text == "search products"


class TestGenerateJiraStories:
    def test_empty_steps_returns_empty_stories(self):
        from app.idea import generate_jira_stories
        result = generate_jira_stories([])
        assert result.stories == []

    @patch("app.main.openai_client")
    def test_returns_stories_from_valid_json(self, mock_client):
        payload = {
            "stories": [
                {
                    "title": "Cart API",
                    "epic": "Commerce",
                    "priority": "P1",
                    "story": "As a dev I want a cart API so that...",
                    "acceptance": ["AC1", "AC2"],
                    "sp": 5,
                    "days": 5,
                    "sprint": "Sprint 1",
                    "squad": "Commerce Team",
                    "deps": [],
                },
            ],
        }
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
        from app.idea import generate_jira_stories
        result = generate_jira_stories([
            {"label": "Cart", "search_text": "add to cart", "journey_title": "Shop", "persona_label": "User"},
        ])
        assert len(result.stories) == 1
        assert result.stories[0].title == "Cart API"
        assert result.stories[0].epic == "Commerce"
        call = mock_client.chat.completions.create.call_args
        assert "add to cart" in call.kwargs["messages"][0]["content"] or "Cart" in call.kwargs["messages"][0]["content"]


class TestExtractJson:
    def test_strips_markdown_fence(self):
        from app.idea import _extract_json
        text = "```json\n{\"a\": 1}\n```"
        assert _extract_json(text) == '{"a": 1}'

    def test_returns_plain_text_unchanged(self):
        from app.idea import _extract_json
        text = '{"a": 1}'
        assert _extract_json(text) == '{"a": 1}'
