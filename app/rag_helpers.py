"""
RAG pipeline helpers: build query from request, map record to matched API, parse enhancement text.
"""
from app.models import RAGLookupRequest, RAGMatchedAPI


def build_rag_query(body: RAGLookupRequest) -> str:
    """Build semantic query string from RAG lookup request."""
    parts = [body.description]
    if body.context:
        ctx = body.context
        ctx_parts = []
        if ctx.product_idea:
            ctx_parts.append(f"Product: {ctx.product_idea}")
        if ctx.persona:
            ctx_parts.append(f"Persona: {ctx.persona}")
        if ctx.journey:
            ctx_parts.append(f"Journey: {ctx.journey}")
        if ctx.step_label:
            ctx_parts.append(f"Step: {ctx.step_label}")
        if ctx_parts:
            parts.append(" ".join(ctx_parts))
    if body.expected_io:
        if body.expected_io.input_schema:
            parts.append(f"Expected input: {body.expected_io.input_schema}")
        if body.expected_io.output_schema:
            parts.append(f"Expected output: {body.expected_io.output_schema}")
    return " ".join(parts)


def record_to_matched_api(record: dict) -> RAGMatchedAPI:
    """Map catalog record to RAGMatchedAPI (new schema: path, owner, readiness)."""
    endpoint = record.get("path") or record.get("url") or record.get("endpoint") or ""
    return RAGMatchedAPI(
        name=record.get("name", ""),
        endpoint=endpoint,
        method=record.get("method"),
        team=record.get("team"),
        author=record.get("owner"),
        status=record.get("readiness"),
        version=record.get("version"),
        desc=record.get("description"),
        contract=record.get("confluence"),
        sla=None,
        latency=None,
        calls=None,
    )


def parse_enhancements_and_gap(text: str) -> tuple[list[str], str | None]:
    """Parse LLM enhancement suggestion into list of enhancements and optional gap_summary."""
    if not text or not text.strip():
        return [], None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    enhancements = []
    gap_parts = []
    in_gap = False
    for ln in lines:
        # Strip common list prefixes
        stripped = ln.lstrip()
        for prefix in ("1.", "2.", "3.", "4.", "5.", "- ", "* ", "• "):
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                break
        if not stripped:
            continue
        # Heuristic: short lines often bullets; "what is missing" / "missing" → gap
        lower = stripped.lower()
        if "missing" in lower or "what is missing" in lower or "gap" in lower:
            in_gap = True
            if len(stripped) > 20:
                gap_parts.append(stripped)
            continue
        if in_gap:
            gap_parts.append(stripped)
        elif len(stripped) < 120 and not stripped.startswith("Respond with"):
            enhancements.append(stripped)
        else:
            gap_parts.append(stripped)
    gap_summary = " ".join(gap_parts).strip() or None
    if not enhancements and gap_summary:
        enhancements = [gap_summary]
        gap_summary = None
    return enhancements, gap_summary
