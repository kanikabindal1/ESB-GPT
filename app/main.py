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

from app.models import SearchRequest, SearchResponse

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
        )
        if r["match_type"] == "closest" and not enhancement_done:
            try:
                api_result.enhancement_suggestion = get_enhancement_suggestion(body.query, record)
                enhancement_done = True
            except Exception:
                pass
        api_results.append(api_result)

    return SearchResponse(results=api_results)


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
