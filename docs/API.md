# ESB-GPT API reference

## How to run and try a sample

**1. Start the server** (from project root, conda env active):

```bash
uvicorn app.main:app --reload
```

**2. Call search with a natural-language API description:**

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "get all orders for a customer"}'
```

Or open **http://localhost:8000/docs** and use the "Try it out" button on `POST /search` with a body like:

```json
{"query": "get all orders for a customer"}
```

**3. Example queries to try:**

- `"get all orders for a customer"`
- `"charge a credit card for 10 dollars"`
- `"send an email to a user"`
- `"refund a payment"`
- `"list products by category"`
- `"authenticate user with email and password"`

---

## API signatures

Base URL: `http://localhost:8000` (or your ngrok/Railway URL).

---

### `GET /health`

**Request:** no body.

**Response:** `200 OK`

```json
{
  "status": "ok"
}
```

---

### `POST /search`

Find APIs that match a natural-language description. Returns top 5 matches with scores and, for the best “closest” match, an LLM enhancement suggestion.

**Request:** `application/json`

```ts
{
  query: string;   // min length 1; e.g. "get customer orders"
}
```

**Response:** `200 OK`

```ts
{
  results: Array<{
    api_id: string;
    name: string;
    description: string;
    input: Record<string, string>;   // e.g. { "customer_id": "string, required" }
    output: Record<string, string>;  // e.g. { "orders": "array of order objects" }
    score: number;                   // 0–1 similarity
    match_type: "direct" | "closest" | "no_match";
    enhancement_suggestion: string | null;  // only for first "closest" result
  }>;
}
```

**Example request:**

```json
{
  "query": "get all orders for a customer"
}
```

**Example response (trimmed):**

```json
{
  "results": [
    {
      "api_id": "api_001",
      "name": "GetCustomerOrders",
      "description": "Retrieves all orders placed by a customer within a date range.",
      "input": {
        "customer_id": "string, required",
        "from_date": "ISO date, optional",
        "to_date": "ISO date, optional"
      },
      "output": {
        "orders": "array of order objects",
        "total_count": "integer",
        "status": "string"
      },
      "score": 0.89,
      "match_type": "direct",
      "enhancement_suggestion": null
    }
  ]
}
```

---

### `GET /catalog`

Return the full API catalog from `data/apis.json`. Supports new schema `{ _meta, apis }` or legacy array.

**Response:** `200 OK` — `{ "apis": [ ... ], "_meta": { ... } }` (optional)

---

### `POST /ingest`

Re-run ingestion: load `data/apis.json`, embed via OpenAI, upsert into ChromaDB. Safe to call multiple times.

**Request:** no body.

**Response:** `200 OK`

```ts
{
  status: "ok";
  upserted: number;
}
```

**Errors:** `404` (file not found), `400` (e.g. missing `OPENAI_API_KEY`), `500` (server error).

---

### `POST /api/rag/lookup`

RAG pipeline: semantic lookup against the embedded API catalog. Returns a single best match with `match_status` (exact / partial / none), `confidence_score`, `matched_api`, `enhancements`, `gap_summary`, and `build_required`. Intended for use with pre-processed input from `/llm/describe`.

**Request:** `application/json`

```ts
{
  query_key: string;       // e.g. "secure_messaging"
  description: string;      // semantic description (min length 1)
  context?: {
    product_idea?: string;
    persona?: string;
    journey?: string;
    step_label?: string;
  };
  expected_io?: {
    input_schema?: string;
    output_schema?: string;
  };
  top_k?: number;            // default 3, 1–20
}
```

**Response:** `200 OK`

```ts
{
  query_key: string;
  match_status: "exact" | "partial" | "none";
  confidence_score: number;   // 0–1 (exact ≥ 0.90)
  matched_api: {
    name: string;
    endpoint: string;         // from catalog path/url
    method?: string;
    team?: string;
    author?: string;          // from catalog owner
    status?: string;          // from catalog readiness
    version?: string;
    desc?: string;
    contract?: string;
    sla?: string | null;
    latency?: string | null;
    calls?: unknown;
  } | null;
  enhancements: string[];
  gap_summary: string | null;
  build_required: boolean;
}
```

**Example request:**

```json
{
  "query_key": "secure_messaging",
  "description": "HIPAA-compliant encrypted messaging between patients and care providers",
  "context": {
    "product_idea": "Healthcare patient portal",
    "persona": "Patient",
    "journey": "Care Journey",
    "step_label": "Message Doctor"
  },
  "expected_io": {
    "input_schema": "{ sender_id, recipient_id, message_body, attachments[] }",
    "output_schema": "{ message_id, status, delivered_at }"
  },
  "top_k": 3
}
```

---

## Summary table

| Method | Path               | Request body                    | Response body |
|--------|--------------------|----------------------------------|---------------|
| GET    | `/health`          | —                                | `{ "status": "ok" }` |
| GET    | `/catalog`         | —                                | `{ "apis": [...], "_meta"?: {...} }` |
| POST   | `/search`          | `{ "query": "..." }`             | `{ "results": [ APIResult, ... ] }` |
| POST   | `/api/rag/lookup`  | RAGLookupRequest                 | RAGLookupResponse |
| POST   | `/ingest`          | —                                | `{ "status": "ok", "upserted": N }` |
