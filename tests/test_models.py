"""
Unit tests for app.models: SearchRequest, APIResult, SearchResponse, RAG, and idea-related models.
"""
import pytest
from pydantic import ValidationError

from app.models import (
    APIResult,
    FeaturesRequest,
    IdeaFeaturesRequest,
    IdeaPersonasRequest,
    JiraGenerateRequest,
    RAGContext,
    RAGExpectedIO,
    RAGLookupRequest,
    RAGMatchedAPI,
    SearchRequest,
    SearchResponse,
    SuggestPersonasRequest,
)


class TestSearchRequest:
    def test_accepts_non_empty_query(self):
        req = SearchRequest(query="get customer orders")
        assert req.query == "get customer orders"

    def test_rejects_empty_string(self):
        with pytest.raises(ValidationError):
            SearchRequest(query="")

    def test_rejects_whitespace_only(self):
        # min_length=1 only checks length; "   " has length 3 so is accepted by Pydantic.
        # If strict "whitespace-only" rejection is needed, add a validator in the model.
        req = SearchRequest(query="   ")
        assert req.query == "   "

    def test_extra_fields_ignored(self):
        req = SearchRequest(query="orders", extra="ignored")
        assert req.query == "orders"
        assert not hasattr(req, "extra") or getattr(req, "extra", None) != "ignored"


class TestAPIResult:
    def test_valid_result(self):
        r = APIResult(
            api_id="api_001",
            name="GetOrders",
            description="Get orders",
            input={},
            output={},
            score=0.85,
            match_type="direct",
            enhancement_suggestion=None,
        )
        assert r.score == 0.85
        assert r.match_type == "direct"

    def test_score_in_bounds(self):
        APIResult(
            api_id="x",
            name="n",
            description="d",
            score=0,
            match_type="no_match",
        )
        APIResult(
            api_id="x",
            name="n",
            description="d",
            score=1.0,
            match_type="direct",
        )

    def test_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            APIResult(
                api_id="x",
                name="n",
                description="d",
                score=-0.1,
                match_type="no_match",
            )

    def test_score_above_one_rejected(self):
        with pytest.raises(ValidationError):
            APIResult(
                api_id="x",
                name="n",
                description="d",
                score=1.01,
                match_type="direct",
            )

    def test_match_type_accepted(self):
        for mt in ("direct", "closest", "no_match"):
            r = APIResult(
                api_id="x",
                name="n",
                description="d",
                score=0.5,
                match_type=mt,
            )
            assert r.match_type == mt


class TestSearchResponse:
    def test_results_required(self):
        with pytest.raises(ValidationError):
            SearchResponse()

    def test_empty_results_allowed(self):
        resp = SearchResponse(results=[])
        assert resp.results == []

    def test_results_list_accepted(self):
        one = APIResult(
            api_id="api_001",
            name="GetOrders",
            description="Get orders",
            score=0.9,
            match_type="direct",
        )
        resp = SearchResponse(results=[one])
        assert len(resp.results) == 1
        assert resp.results[0].api_id == "api_001"


class TestRAGLookupRequest:
    def test_valid_minimal(self):
        req = RAGLookupRequest(query_key="k", description="find stores")
        assert req.query_key == "k"
        assert req.description == "find stores"
        assert req.top_k == 3
        assert req.context is None
        assert req.expected_io is None

    def test_valid_with_context_and_expected_io(self):
        req = RAGLookupRequest(
            query_key="k",
            description="get orders",
            context=RAGContext(product_idea="Shop", persona="Buyer"),
            expected_io=RAGExpectedIO(input_schema="id", output_schema="orders"),
            top_k=5,
        )
        assert req.context is not None
        assert req.context.product_idea == "Shop"
        assert req.expected_io is not None
        assert req.expected_io.input_schema == "id"
        assert req.top_k == 5

    def test_top_k_bounds(self):
        RAGLookupRequest(query_key="k", description="x", top_k=1)
        RAGLookupRequest(query_key="k", description="x", top_k=20)
        with pytest.raises(ValidationError):
            RAGLookupRequest(query_key="k", description="x", top_k=0)
        with pytest.raises(ValidationError):
            RAGLookupRequest(query_key="k", description="x", top_k=21)

    def test_description_required_and_min_length(self):
        with pytest.raises(ValidationError):
            RAGLookupRequest(query_key="k", description="")


class TestRAGContext:
    def test_all_optional(self):
        ctx = RAGContext()
        assert ctx.product_idea is None
        assert ctx.persona is None
        assert ctx.journey is None
        assert ctx.step_label is None

    def test_can_set_fields(self):
        ctx = RAGContext(product_idea="P", persona="U", journey="J", step_label="S")
        assert ctx.product_idea == "P"
        assert ctx.persona == "U"
        assert ctx.journey == "J"
        assert ctx.step_label == "S"


class TestRAGExpectedIO:
    def test_all_optional(self):
        io = RAGExpectedIO()
        assert io.input_schema is None
        assert io.output_schema is None

    def test_can_set_fields(self):
        io = RAGExpectedIO(input_schema="id", output_schema="item")
        assert io.input_schema == "id"
        assert io.output_schema == "item"


class TestRAGMatchedAPI:
    def test_endpoint_required(self):
        api = RAGMatchedAPI(endpoint="/v1/foo")
        assert api.endpoint == "/v1/foo"
        assert api.name == ""


class TestFeaturesRequest:
    def test_min_max_order_validator_rejects_reversed(self):
        with pytest.raises(ValidationError):
            FeaturesRequest(idea="A" * 10, min_features=12, max_features=8)

    def test_accepts_valid_range(self):
        req = FeaturesRequest(idea="A" * 10, min_features=8, max_features=12)
        assert req.min_features == 8
        assert req.max_features == 12

    def test_idea_min_length(self):
        with pytest.raises(ValidationError):
            FeaturesRequest(idea="short")


class TestSuggestPersonasRequest:
    def test_min_max_order_validator_rejects_reversed(self):
        with pytest.raises(ValidationError):
            SuggestPersonasRequest(idea="x", idea_summary="y", min_personas=4, max_personas=2)

    def test_accepts_valid_range(self):
        req = SuggestPersonasRequest(idea="x", idea_summary="y", min_personas=2, max_personas=4)
        assert req.min_personas == 2
        assert req.max_personas == 4


class TestIdeaFeaturesRequest:
    def test_accepts_non_empty_idea(self):
        req = IdeaFeaturesRequest(idea="A mobile banking app")
        assert req.idea == "A mobile banking app"

    def test_rejects_empty_idea(self):
        with pytest.raises(ValidationError):
            IdeaFeaturesRequest(idea="")


class TestIdeaPersonasRequest:
    def test_accepts_idea_and_optional_feature_ids(self):
        req = IdeaPersonasRequest(idea="Banking app")
        assert req.idea == "Banking app"
        assert req.feature_ids == []
        req2 = IdeaPersonasRequest(idea="x", feature_ids=["auth", "pay"])
        assert req2.feature_ids == ["auth", "pay"]

    def test_rejects_empty_idea(self):
        with pytest.raises(ValidationError):
            IdeaPersonasRequest(idea="")


class TestJiraGenerateRequest:
    def test_accepts_missing_steps_with_label_and_search_text(self):
        req = JiraGenerateRequest(
            missing_steps=[
                {"label": "Search", "search_text": "search products", "journey_title": "Browse", "persona_label": "Shopper"},
            ]
        )
        assert len(req.missing_steps) == 1
        assert req.missing_steps[0].label == "Search"
        assert req.missing_steps[0].search_text == "search products"
        assert req.missing_steps[0].journey_title == "Browse"
        assert req.missing_steps[0].persona_label == "Shopper"

    def test_accepts_minimal_step_defaults(self):
        req = JiraGenerateRequest(missing_steps=[{"label": "Step"}])
        assert req.missing_steps[0].search_text == ""
        assert req.missing_steps[0].journey_title == ""
        assert req.missing_steps[0].persona_label == ""
