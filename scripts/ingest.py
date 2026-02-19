"""
Phase 3: Ingestion script.
Loads apis.json, flattens each record to an embedding string, embeds via OpenAI,
and upserts into ChromaDB. Safe to re-run (upsert by id).
"""
import json
import os
import sys
from pathlib import Path

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(PROJECT_ROOT / ".env")

DATA_PATH = PROJECT_ROOT / "data" / "apis.json"
DB_PATH = PROJECT_ROOT / "db"
EMBEDDING_MODEL = "text-embedding-3-small"


def flatten_record(record: dict) -> str:
    """Build a single searchable string for embedding. Supports new schema (path, domain) and legacy (endpoint, use_cases)."""
    name = record.get("name", "")
    description = record.get("description", "")
    domain = record.get("domain", "")
    use_cases = record.get("use_cases", [])
    inp = record.get("input", {})
    out = record.get("output", {})
    method = record.get("method", "")
    path = record.get("path") or record.get("endpoint", "")
    tags = record.get("tags", [])

    use_cases_str = ", ".join(use_cases) if isinstance(use_cases, list) else str(use_cases)
    inputs_str = ", ".join(f"{k} ({v})" for k, v in inp.items()) if isinstance(inp, dict) else str(inp)
    outputs_str = ", ".join(f"{k} {v}" for k, v in out.items()) if isinstance(out, dict) else str(out)
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)

    parts = [
        f"{name} — {description}.",
        f"Domain: {domain}." if domain else "",
        f"Use cases: {use_cases_str}." if use_cases_str else "",
        f"Inputs: {inputs_str}.",
        f"Outputs: {outputs_str}.",
        f"Method: {method}, Path: {path}.",
        f"Tags: {tags_str}.",
    ]
    return " ".join(p for p in parts if p.strip())


def run_ingest() -> int:
    """
    Load apis.json, embed via OpenAI, upsert into ChromaDB.
    Returns the number of APIs upserted. Raises on missing file or missing API key.
    Callable from CLI (scripts/ingest.py) or from API (POST /ingest).
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_key_here":
        raise ValueError("Set OPENAI_API_KEY in .env")

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    # Support new schema { _meta, apis } or legacy array
    if isinstance(data, dict) and "apis" in data:
        records = data["apis"]
    else:
        records = data if isinstance(data, list) else []

    if not records:
        return 0

    ids = []
    documents = []
    metadatas = []

    for record in records:
        rid = record.get("id")
        if not rid:
            continue
        ids.append(rid)
        documents.append(flatten_record(record))
        metadatas.append({"record": json.dumps(record)})

    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=documents)
    by_index = {e.index: e.embedding for e in resp.data}
    embeddings = [by_index[i] for i in range(len(documents))]

    chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = chroma_client.get_or_create_collection(
        name="apis",
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    return len(ids)


def main() -> None:
    try:
        count = run_ingest()
        print(f"Ingestion complete: {count} API(s) upserted.")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
