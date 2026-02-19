"""
Phase 4: Retriever.
Embed query, search ChromaDB (cosine), convert distance to similarity, classify match type.
"""
import json
from typing import Literal

from app.main import api_collection, openai_client

EMBEDDING_MODEL = "text-embedding-3-small"

# Cosine: distance 0 = identical, 2 = opposite → similarity = 1 - (distance / 2)
DIRECT_THRESHOLD = 0.75   # score >= 0.75 → direct match
CLOSEST_THRESHOLD = 0.45  # 0.45 <= score < 0.75 → closest; below → no_match


def embed_query(query: str) -> list[float]:
    """Embed the user's search query with OpenAI."""
    resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[query])
    return resp.data[0].embedding


def distance_to_similarity(distance: float) -> float:
    """Convert ChromaDB cosine distance to similarity in [0, 1]."""
    return 1.0 - (distance / 2.0)


def classify_result(similarity: float) -> Literal["direct", "closest", "no_match"]:
    """Classify match type from similarity score. Tune thresholds in Phase 7."""
    if similarity >= DIRECT_THRESHOLD:
        return "direct"
    if similarity >= CLOSEST_THRESHOLD:
        return "closest"
    return "no_match"


def search(query: str, n_results: int = 5) -> list[dict]:
    """
    Embed query, run similarity search, return results with similarity and parsed record.
    Each result: { "id", "record", "distance", "similarity", "match_type" }.
    """
    if not query or not query.strip():
        return []

    query_embedding = embed_query(query.strip())
    result = api_collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    # Single query → first element of each list
    ids = result["ids"][0]
    distances = result["distances"][0]
    metadatas = result["metadatas"][0]
    documents = result["documents"][0] if result["documents"] else [None] * len(ids)

    results = []
    for i, (idx, dist, meta, doc) in enumerate(zip(ids, distances, metadatas, documents)):
        similarity = distance_to_similarity(dist)
        record = {}
        if meta and "record" in meta:
            try:
                record = json.loads(meta["record"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append({
            "id": idx,
            "record": record,
            "document": doc,
            "distance": dist,
            "similarity": round(similarity, 4),
            "match_type": classify_result(similarity),
        })

    return results
