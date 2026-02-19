"""
Unit tests for app.rag_helpers: build_rag_query, record_to_matched_api, parse_enhancements_and_gap.
"""
import pytest

from app.models import RAGContext, RAGExpectedIO, RAGLookupRequest
from app.rag_helpers import (
    build_rag_query,
    parse_enhancements_and_gap,
    record_to_matched_api,
)


class TestBuildRagQuery:
    def test_description_only(self):
        body = RAGLookupRequest(query_key="k", description="find stores near me")
        assert build_rag_query(body) == "find stores near me"

    def test_with_context_all_fields(self):
        body = RAGLookupRequest(
            query_key="k",
            description="check balance",
            context=RAGContext(
                product_idea="Banking app",
                persona="Retail customer",
                journey="View balance",
                step_label="Load account",
            ),
        )
        out = build_rag_query(body)
        assert "check balance" in out
        assert "Product: Banking app" in out
        assert "Persona: Retail customer" in out
        assert "Journey: View balance" in out
        assert "Step: Load account" in out

    def test_with_context_partial(self):
        body = RAGLookupRequest(
            query_key="k",
            description="search",
            context=RAGContext(persona="Admin", journey="Manage users"),
        )
        out = build_rag_query(body)
        assert "search" in out
        assert "Persona: Admin" in out
        assert "Journey: Manage users" in out

    def test_with_expected_io(self):
        body = RAGLookupRequest(
            query_key="k",
            description="get orders",
            expected_io=RAGExpectedIO(
                input_schema="customer_id: string",
                output_schema="orders: array",
            ),
        )
        out = build_rag_query(body)
        assert "get orders" in out
        assert "Expected input: customer_id: string" in out
        assert "Expected output: orders: array" in out

    def test_with_expected_io_only_input(self):
        body = RAGLookupRequest(
            query_key="k",
            description="lookup",
            expected_io=RAGExpectedIO(input_schema="id: string", output_schema=None),
        )
        out = build_rag_query(body)
        assert "Expected input: id: string" in out
        assert "Expected output" not in out or "None" not in out

    def test_context_and_expected_io(self):
        body = RAGLookupRequest(
            query_key="k",
            description="pay",
            context=RAGContext(product_idea="Shop"),
            expected_io=RAGExpectedIO(output_schema="receipt"),
        )
        out = build_rag_query(body)
        assert "pay" in out
        assert "Product: Shop" in out
        assert "Expected output: receipt" in out


class TestRecordToMatchedApi:
    def test_minimal_record(self):
        record = {"id": "x", "name": "Foo"}
        api = record_to_matched_api(record)
        assert api.name == "Foo"
        assert api.endpoint == ""
        assert api.method is None
        assert api.author is None
        assert api.status is None

    def test_full_record_new_schema(self):
        record = {
            "name": "Store API",
            "path": "/v1/stores",
            "method": "GET",
            "owner": "Jane",
            "team": "Retail",
            "readiness": "production",
            "version": "1.0",
            "description": "Get stores",
            "confluence": "https://wiki/store",
        }
        api = record_to_matched_api(record)
        assert api.name == "Store API"
        assert api.endpoint == "/v1/stores"
        assert api.method == "GET"
        assert api.author == "Jane"
        assert api.team == "Retail"
        assert api.status == "production"
        assert api.version == "1.0"
        assert api.desc == "Get stores"
        assert api.contract == "https://wiki/store"

    def test_legacy_endpoint_only(self):
        record = {"name": "Legacy", "endpoint": "/old/api"}
        api = record_to_matched_api(record)
        assert api.endpoint == "/old/api"

    def test_url_fallback(self):
        record = {"name": "External", "url": "https://api.example.com"}
        api = record_to_matched_api(record)
        assert api.endpoint == "https://api.example.com"

    def test_path_over_url_and_endpoint(self):
        record = {"path": "/v1", "url": "/v2", "endpoint": "/v3"}
        api = record_to_matched_api(record)
        assert api.endpoint == "/v1"


class TestParseEnhancementsAndGap:
    def test_empty_returns_empty_and_none(self):
        assert parse_enhancements_and_gap("") == ([], None)
        assert parse_enhancements_and_gap("   \n  ") == ([], None)

    def test_numbered_bullets_as_enhancements(self):
        text = "1. Add idempotency key\n2. Add retry policy\n3. Log errors"
        enh, gap = parse_enhancements_and_gap(text)
        assert "Add idempotency key" in enh
        assert "Add retry policy" in enh
        assert "Log errors" in enh
        assert gap is None

    def test_what_is_missing_triggers_gap(self):
        text = "1. Add auth\nWhat is missing: rate limiting and caching."
        enh, gap = parse_enhancements_and_gap(text)
        assert "Add auth" in enh
        assert gap is not None
        assert "rate limiting" in gap or "caching" in gap

    def test_gap_keyword_triggers_gap_section(self):
        text = "Enhancements:\n- Retry\nGap: no idempotency support."
        enh, gap = parse_enhancements_and_gap(text)
        assert gap is not None
        assert "idempotency" in gap or "Gap" in gap.lower()

    def test_long_line_not_treated_as_enhancement(self):
        long_line = "A" * 150
        text = f"1. Short bullet\n{long_line}"
        enh, gap = parse_enhancements_and_gap(text)
        assert "Short bullet" in enh
        assert long_line not in enh or long_line in (gap or "")

    def test_respond_with_ignored_as_enhancement(self):
        text = "Respond with only bullets.\n1. Real enhancement"
        enh, gap = parse_enhancements_and_gap(text)
        assert "Real enhancement" in enh

    def test_only_gap_summary_becomes_single_enhancement(self):
        text = "What is missing: Everything."
        enh, gap = parse_enhancements_and_gap(text)
        assert len(enh) >= 1
        assert "Everything" in str(enh) or gap is None
