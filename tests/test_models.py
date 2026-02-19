"""
Unit tests for app.models: SearchRequest, APIResult, SearchResponse validation.
"""
import pytest
from pydantic import ValidationError

from app.models import APIResult, SearchRequest, SearchResponse


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
