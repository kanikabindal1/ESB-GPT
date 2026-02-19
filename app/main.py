"""
FastAPI app for API Discovery RAG.
Phase 1: OpenAI + ChromaDB clients and collection initialization.
Phase 6: POST /search, POST /ingest.
"""
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI

from app.models import (
    IdeaFeaturesRequest,
    IdeaFeaturesResponse,
    IdeaPersonasRequest,
    IdeaPersonasResponse,
    JiraGenerateRequest,
    JiraGenerateResponse,
    RAGLookupRequest,
    RAGLookupResponse,
    RAGMatchedAPI,
    SearchRequest,
    SearchResponse,
)
from app import idea as idea_module

load_dotenv()

# Project root (parent of app/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db"

# OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ChromaDB persistent client
chroma_client = chromadb.PersistentClient(path=str(DB_PATH))

# Collection with cosine similarity (0 = identical, 2 = opposite)
# We'll convert distance to similarity as: similarity = 1 - (distance / 2)
api_collection = chroma_client.get_or_create_collection(
    name="apis",
    metadata={"hnsw:space": "cosine"},
)

app = FastAPI(
    title="API Discovery RAG",
    description="Lightweight RAG for API recommendation — search by natural language.",
)

STATIC_DIR = PROJECT_ROOT / "static"
UI_INDEX = STATIC_DIR / "index.html"
DATA_PATH = PROJECT_ROOT / "data" / "apis.json"


@app.get("/")
def ui():
    """Serve the search UI. Use /docs for API docs."""
    if UI_INDEX.exists():
        return FileResponse(UI_INDEX)
    return {"message": "UI not found. Use /docs for API docs.", "docs": "/docs"}


@app.get("/health")
def health():
    """Uptime check for load balancers / ngrok."""
    return {"status": "ok"}


@app.get("/catalog")
def get_catalog():
    """Return full API catalog from data/apis.json for UI drawer and coverage."""
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Catalog file not found.")
    import json
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # New schema: { _meta, apis }; legacy: array
    if isinstance(data, dict) and "apis" in data:
        return {"apis": data["apis"], "_meta": data.get("_meta")}
    return {"apis": data}


@app.post("/idea/features", response_model=IdeaFeaturesResponse)
def idea_features_endpoint(body: IdeaFeaturesRequest):
    """Generate product features from idea text using LLM."""
    try:
        return idea_module.generate_features(body.idea)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/idea/personas", response_model=IdeaPersonasResponse)
def idea_personas_endpoint(body: IdeaPersonasRequest):
    """Generate personas and journeys from idea + feature IDs using LLM."""
    try:
        return idea_module.generate_personas(body.idea, body.feature_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/jira/generate", response_model=JiraGenerateResponse)
def jira_generate_endpoint(body: JiraGenerateRequest):
    """Generate Jira stories for missing API steps using LLM."""
    try:
        steps = [
            {"label": s.label, "search_text": s.search_text, "journey_title": s.journey_title, "persona_label": s.persona_label}
            for s in body.missing_steps
        ]
        return idea_module.generate_jira_stories(steps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
def search_endpoint(body: SearchRequest):
    """Embed query → retrieve top 5 → classify → call LLM for 'closest' → return results."""
    from app.models import APIResult
    from app.recommender import get_enhancement_suggestion
    from app.retriever import search as retriever_search

    results_raw = retriever_search(body.query, n_results=5)
    enhancement_done = False
    api_results = []

    for r in results_raw:
        record = r.get("record") or {}
        api_result = APIResult(
            api_id=record.get("id", r.get("id", "")),
            name=record.get("name", ""),
            description=record.get("description", ""),
            input=record.get("input", {}),
            output=record.get("output", {}),
            score=r["similarity"],
            match_type=r["match_type"],
            enhancement_suggestion=None,
            method=record.get("method"),
            endpoint=record.get("path") or record.get("endpoint"),
            tags=record.get("tags"),
        )
        if r["match_type"] == "closest" and not enhancement_done:
            try:
                api_result.enhancement_suggestion = get_enhancement_suggestion(body.query, record)
                enhancement_done = True
            except Exception:
                pass
        api_results.append(api_result)

    return SearchResponse(results=api_results)


def _build_rag_query(body: RAGLookupRequest) -> str:
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


def _record_to_matched_api(record: dict) -> RAGMatchedAPI:
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


def _parse_enhancements_and_gap(text: str) -> tuple[list[str], str | None]:
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


@app.post("/api/rag/lookup", response_model=RAGLookupResponse)
def rag_lookup_endpoint(body: RAGLookupRequest):
    """RAG pipeline: semantic lookup → best match, match_status, enhancements, gap_summary, build_required."""
    from app.recommender import get_enhancement_suggestion
    from app.retriever import search as retriever_search

    query = _build_rag_query(body)
    results_raw = retriever_search(query, n_results=body.top_k)

    if not results_raw:
        return RAGLookupResponse(
            query_key=body.query_key,
            match_status="none",
            confidence_score=0.0,
            matched_api=None,
            enhancements=[],
            gap_summary=None,
            build_required=True,
        )

    best = results_raw[0]
    record = best.get("record") or {}
    similarity = best["similarity"]
    match_type = best["match_type"]

    # exact >= 0.90; else partial (direct/closest) or none
    if similarity >= 0.90:
        match_status = "exact"
    elif match_type in ("direct", "closest"):
        match_status = "partial"
    else:
        match_status = "none"

    build_required = match_status == "none" or (match_status == "partial" and similarity < 0.60)
    matched_api = _record_to_matched_api(record) if record else None

    enhancements: list[str] = []
    gap_summary: str | None = None
    if match_status == "partial" or (match_status == "exact" and similarity < 0.95):
        try:
            raw_suggestion = get_enhancement_suggestion(query, record)
            enhancements, gap_summary = _parse_enhancements_and_gap(raw_suggestion)
        except Exception:
            pass

    return RAGLookupResponse(
        query_key=body.query_key,
        match_status=match_status,
        confidence_score=round(similarity, 4),
        matched_api=matched_api,
        enhancements=enhancements,
        gap_summary=gap_summary,
        build_required=build_required,
    )


@app.post("/ingest")
def ingest_endpoint():
    """Run ingestion (load apis.json → embed → upsert). Safe to re-run. For demo use."""
    try:
        from scripts.ingest import run_ingest
        count = run_ingest()
        return {"status": "ok", "upserted": count}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
