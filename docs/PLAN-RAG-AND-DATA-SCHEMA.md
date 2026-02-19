# RAG Pipeline + New apis.json Schema — Integration Plan

## Overview

1. **New data schema**: [data/apis.json](data/apis.json) is now an object `{ _meta, apis }` with richer per-API fields. All code that loads or references the catalog must support this structure and the new field set.
2. **RAG contract**: Add `POST /api/rag/lookup` with the specified request/response contracts, reusing retriever + recommender and mapping responses to `match_status`, `confidence_score`, `matched_api`, `enhancements`, `gap_summary`, `build_required`.

---

## Part A: New apis.json Schema and Code Updates

### A.1 New apis.json structure

- **Root**: `{ "_meta": { ... }, "apis": [ ... ] }` (no longer a bare array).
- **_meta**: `schema_version`, `description`, `last_updated`, `total_apis`.
- **apis**: Array of API objects (40 entries).

### A.2 Per-API fields (new schema)

| Field | Type | Notes |
|-------|------|--------|
| id | string | Same as before |
| name | string | Same |
| description | string | Same |
| domain | string | New — e.g. "retail", "payments", "identity", "customer" |
| owner | string | New — e.g. "Jane Doe" (→ contract **author**) |
| team | string | New — e.g. "Retail & Store APIs" |
| version | string | New — e.g. "1.2.0" |
| method | string | Same |
| **path** | string | New — e.g. "/v1/stores" (replaces **endpoint** in old schema) |
| url | string | New — full base URL |
| confluence | string | New — doc link |
| bitbucket | string | New — repo link |
| tags | array | Same |
| sample_input | string | New — JSON string |
| sample_output | string | New — JSON string |
| input | object | Same |
| output | object | Same |
| manhours | number | New |
| api_efficiency | string | New — "high" \| "medium" \| "low" |
| readiness | string | New — e.g. "production", "beta" (→ contract **status**) |

**Removed / renamed**: `endpoint` → use `path`; `use_cases` no longer present.

### A.3 Catalog loading (all consumers)

- **Ingest** [scripts/ingest.py](scripts/ingest.py):
  - Load: `data = json.load(f)`. If `isinstance(data, dict) and "apis" in data`: use `records = data["apis"]`; else use `records = data` (support legacy array).
  - **flatten_record**: Use `path` (fallback to `endpoint` for old data). Include `domain` in the searchable string. Remove or replace `use_cases` with `domain` + `tags` (e.g. "Domain: {domain}. Tags: {tags}").
  - Keep storing full `record` in ChromaDB metadata so RAG and /search get all new fields.

- **GET /catalog** [app/main.py](app/main.py):
  - Load: `data = json.load(f)`. If `isinstance(data, dict) and "apis" in data`: return `{"apis": data["apis"], "_meta": data.get("_meta")}`; else return `{"apis": data}` (legacy array).

### A.4 Existing POST /search and APIResult

- [app/main.py](app/main.py) builds `APIResult` from `record`. Update mapping to be schema-agnostic:
  - **endpoint**: use `record.get("path") or record.get("endpoint")` so both old and new schemas work.
- [app/models.py](app/models.py): `APIResult` can keep `endpoint` as the field name (API contract); populate from `path` or `endpoint` in the handler. Optionally add optional `team`, `version`, `readiness` to `APIResult` if the UI should show them.

### A.5 Recommender and retriever

- [app/recommender.py](app/recommender.py): `_format_io` and `get_enhancement_suggestion` already use `record.get("name")`, `description`, `input`, `output`. No change except that record may now also have `path`, `domain`, etc.; they are not used in the prompt today.
- [app/retriever.py](app/retriever.py): No change; it only needs the stored `record` in metadata to contain the new fields after ingest is updated.

---

## Part B: RAG Pipeline Contract Integration

### B.1 Request/response models ([app/models.py](app/models.py))

- **RAGLookupRequest**
  - `query_key: str`
  - `description: str`
  - `context: Optional[RAGContext]` with optional `product_idea`, `persona`, `journey`, `step_label`
  - `expected_io: Optional[RAGExpectedIO]` with optional `input_schema`, `output_schema`
  - `top_k: int = 3`

- **RAGLookupResponse**
  - `query_key: str`
  - `match_status: Literal["exact", "partial", "none"]`
  - `confidence_score: float`
  - `matched_api: Optional[RAGMatchedAPI]`
  - `enhancements: list[str]`
  - `gap_summary: Optional[str]`
  - `build_required: bool`

- **RAGMatchedAPI** — align with contract and **new catalog**:
  - `name`, `endpoint` (from catalog `path` or `url`), `method`
  - `team`, `author` (from catalog `owner`), `status` (from catalog `readiness`), `version`, `desc` (from catalog `description`)
  - Optional: `sla`, `latency`, `contract`, `calls` (omit or null if not in catalog; new schema does not provide them)

### B.2 Semantic query and handler

- Build query string from `description` + optional context line (product_idea, persona, journey, step_label) + optional expected_io schemas.
- Call existing `retriever_search(query, n_results=top_k)`.
- Take **first** result as best match; map to `match_status` (exact ≥ 0.90, else partial/none), `confidence_score`, `matched_api` (from record using **path**, **owner**→author, **readiness**→status, etc.), `build_required`.

### B.3 Enhancements and gap_summary

- For partial (and optionally low exact): call `get_enhancement_suggestion(...)`; parse bullet/numbered list into `enhancements`; use "what's missing" or full text as `gap_summary`.

### B.4 New endpoint

- **POST /api/rag/lookup** in [app/main.py](app/main.py): accept `RAGLookupRequest`, build query, call retriever, map to `RAGLookupResponse`, return it. Keep **POST /search** unchanged.

---

## Part C: Order of implementation

1. **Data schema (Part A)**  
   - Update [scripts/ingest.py](scripts/ingest.py) (load `apis` from root, update `flatten_record` for path/domain, drop use_cases).  
   - Update [app/main.py](app/main.py) GET /catalog and POST /search record mapping (path/endpoint, optional new fields).  
   - Re-run ingest so ChromaDB has the new records.  
   - Optionally extend [app/models.py](app/models.py) `APIResult` with optional team/version/readiness.

2. **RAG contract (Part B)**  
   - Add RAG request/response and `RAGMatchedAPI` models in [app/models.py](app/models.py) with **new schema** mapping (path→endpoint, owner→author, readiness→status).  
   - Add POST /api/rag/lookup handler in [app/main.py](app/main.py).  
   - Add tests and update [docs/API.md](docs/API.md).

---

## Summary

- **apis.json**: Treated as `{ _meta, apis }`; ingest and GET /catalog load `apis` and support legacy array. Ingest uses `path`/domain in flatten_record; search and RAG use `path` (or endpoint), `owner`, `team`, `version`, `readiness` from stored records.
- **RAG**: New endpoint and models; single best match; match_status from confidence; `matched_api` populated from the new catalog fields (team, author, status, version, desc, endpoint from path); enhancements/gap_summary from existing recommender.
