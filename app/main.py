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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI

from app.models import (
    ChatRequest,
    ChatResponse,
    DescribeRequest,
    DescribeResponse,
    FeaturesRequest,
    FeaturesResponse,
    GenerateJourneysRequest,
    GenerateJourneysResponse,
    IdeaFeaturesRequest,
    IdeaFeaturesResponse,
    IdeaPersonasRequest,
    IdeaPersonasResponse,
    JiraGenerateRequest,
    JiraGenerateResponse,
    JiraRequest,
    JiraResponse,
    RAGLookupRequest,
    RAGLookupResponse,
    RAGRerankRequest,
    RAGRerankResponse,
    RAGMatchedAPI,
    SearchRequest,
    SearchResponse,
    SuggestedAPIItem,
    SuggestPersonasRequest,
    SuggestPersonasResponse,
    SummariseRequest,
    SummariseResponse,
)
from app import idea as idea_module
from app.idea import FeatureParseError
from app.rag_helpers import (
    build_rag_query,
    record_to_matched_api,
)

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

# CORS: allow UI (e.g. Vite dev server on localhost:5173) to call this API
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").strip().split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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


@app.post("/llm/features", response_model=FeaturesResponse)
def llm_features_endpoint(body: FeaturesRequest):
    """Extract 8-12 features from product idea using gpt-4o (JSON mode). Trigger: Analyse Idea button."""
    try:
        return idea_module.generate_llm_features(body)
    except FeatureParseError:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "FEATURE_PARSE_FAILED"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/suggest-personas", response_model=SuggestPersonasResponse)
def llm_suggest_personas_endpoint(body: SuggestPersonasRequest):
    """Suggest distinct personas for idea + features. Trigger: Map User Journeys."""
    try:
        return idea_module.suggest_personas(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/chat", response_model=ChatResponse)
def llm_chat_endpoint(body: ChatRequest):
    """Stateless product discovery coach: one turn. Frontend sends full message history."""
    try:
        return idea_module.chat(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/summarise", response_model=SummariseResponse)
def llm_summarise_endpoint(body: SummariseRequest):
    """Distill full conversation into structured product brief for features and personas."""
    try:
        return idea_module.summarise(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/generate-journeys", response_model=GenerateJourneysResponse)
def llm_generate_journeys_endpoint(body: GenerateJourneysRequest):
    """Generate journeys for confirmed personas; steps use api keys for RAG. After user confirms personas."""
    try:
        return idea_module.generate_journeys(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/describe", response_model=DescribeResponse)
def llm_describe_endpoint(body: DescribeRequest):
    """Produce capability description for RAG lookup. Called in batches per unique api_key."""
    try:
        return idea_module.describe(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/jira", response_model=JiraResponse)
def llm_jira_endpoint(body: JiraRequest):
    """Generate one Jira ticket for a missing api_key. BRD §4.5; called per api_key from frontend."""
    try:
        return idea_module.generate_jira_ticket(body)
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
    """Embed query → retrieve top 5 → classify → return results."""
    from app.models import APIResult
    from app.retriever import search as retriever_search

    results_raw = retriever_search(body.query, n_results=5)
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
        api_results.append(api_result)

    return SearchResponse(results=api_results)


@app.post("/api/rag/lookup", response_model=RAGLookupResponse)
def rag_lookup_endpoint(body: RAGLookupRequest):
    """RAG pipeline: semantic lookup → best match, suggested_apis (above min_score), match_status."""
    from app.retriever import search as retriever_search

    query = build_rag_query(body)
    results_raw = retriever_search(query, n_results=body.top_k)

    filtered = (
        results_raw
        if body.min_score is None
        else [r for r in results_raw if r["similarity"] >= body.min_score]
    )
    suggested_apis = [
        SuggestedAPIItem(api=record_to_matched_api(r.get("record") or {}), score=round(r["similarity"], 4))
        for r in filtered
    ]

    if not results_raw:
        return RAGLookupResponse(
            query_key=body.query_key,
            match_status="none",
            confidence_score=0.0,
            matched_api=None,
            suggested_apis=[],
            enhancements=[],
            gap_summary=None,
            build_required=True,
        )

    best = results_raw[0]
    record = best.get("record") or {}
    similarity = best["similarity"]
    match_type = best["match_type"]

    # API present only at high confidence (>= 95%)
    if similarity >= 0.95:
        match_status = "exact"
    else:
        match_status = "none"

    build_required = match_status == "none"
    matched_api = record_to_matched_api(record) if record else None
    if suggested_apis and matched_api is None:
        matched_api = suggested_apis[0].api
    confidence_score = round(similarity, 4)

    enhancements: list[str] = []
    gap_summary: str | None = None

    return RAGLookupResponse(
        query_key=body.query_key,
        match_status=match_status,
        confidence_score=confidence_score,
        matched_api=matched_api,
        suggested_apis=suggested_apis,
        enhancements=enhancements,
        gap_summary=gap_summary,
        build_required=build_required,
    )


@app.post("/api/rag/rerank", response_model=RAGRerankResponse)
def rag_rerank_endpoint(body: RAGRerankRequest):
    """Rerank suggested_apis by relevance to description + context + expected_io + additional_info."""
    from app.retriever import search as retriever_search

    lookup_body = RAGLookupRequest(
        query_key=body.query_key,
        description=body.description,
        context=body.context,
        expected_io=body.expected_io,
    )
    query = build_rag_query(lookup_body)
    if body.additional_info and body.additional_info.strip():
        query = query + " " + body.additional_info.strip()

    results_raw = retriever_search(query, n_results=50)
    endpoint_to_score = {}
    for r in results_raw:
        rec = r.get("record") or {}
        ep = rec.get("path") or rec.get("endpoint") or rec.get("url") or ""
        if ep:
            endpoint_to_score[ep] = round(r["similarity"], 4)

    def sort_key(item: SuggestedAPIItem) -> tuple:
        score = endpoint_to_score.get(item.api.endpoint, 0.0)
        return (-score, item.api.endpoint)

    reranked = sorted(body.suggested_apis, key=sort_key)
    reranked_with_scores = []
    for item in reranked:
        new_score = endpoint_to_score.get(item.api.endpoint, item.score)
        reranked_with_scores.append(SuggestedAPIItem(api=item.api, score=new_score))

    return RAGRerankResponse(query_key=body.query_key, suggested_apis=reranked_with_scores)


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
