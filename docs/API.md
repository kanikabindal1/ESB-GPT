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

### `POST /llm/features`

Extract 8–12 product features from a raw idea using gpt-4o with deterministic JSON output. Called when the user clicks “Analyse Idea →”.

**Request:** `application/json`

```ts
{
  idea: string;        // min 10 characters
  max_features?: number;  // default 12
  min_features?: number;  // default 8
}
```

**Response:** `200 OK`

```ts
{
  features: Array<{
    id: string;      // e.g. "f1", "f2"
    icon: string;    // single emoji
    title: string;   // 4-6 words
    desc: string;    // max 12 words
    on: boolean;     // default true
  }>;
  idea_summary: string;   // one sentence LLM summary
  model_used: string;    // "gpt-4o"
}
```

**Errors:**

- `422 Unprocessable Entity` — LLM response could not be parsed or validated after retry. Body: `{ "error_code": "FEATURE_PARSE_FAILED" }`.
- `400` — Validation error (e.g. idea too short, min_features > max_features).
- `500` — Server or OpenAI error.

---

### `POST /llm/suggest-personas`

Suggest distinct user personas for a product idea and its selected features. Called when the user clicks "Map User Journeys →". Frontend shows persona cards; user can rename, edit desc, change icon, select/deselect. Only confirmed (selected) personas are sent to `/llm/generate-journeys`.

**Request:** `application/json`

```ts
{
  idea: string;
  idea_summary: string;           // from FeaturesResponse.idea_summary
  selected_features: string[];    // titles of features where on=true
  max_personas?: number;         // default 4
  min_personas?: number;         // default 2
}
```

**Response:** `200 OK`

```ts
{
  personas: Array<{
    id: string;                  // e.g. "guest_shopper"
    label: string;
    icon: string;                 // single emoji
    desc: string;
    color: "blue" | "green" | "purple" | "amber";
    rationale: string;
    suggested_journeys: string[]; // 2-3 journey names
    is_primary: boolean;
  }>;
  model_used: string;             // "gpt-4o"
}
```

**Errors:** `400` (validation, e.g. min_personas > max_personas), `500` (server/OpenAI).

---

### `POST /llm/generate-journeys`

Generate journeys for confirmed personas in a single call. Called after the user confirms selected personas (and any edits). Each step has an `api` field: a snake_case **noun** (capability key) used for RAG lookup; same capability reuses the same key. Response includes `unique_api_keys` for batching `/llm/describe` calls.

**Request:** `application/json`

```ts
{
  idea: string;
  selected_features: string[];
  confirmed_personas: Array<{
    id: string;
    label: string;
    icon: string;
    desc: string;
    color: string;
    suggested_journeys: string[];
  }>;
  steps_per_journey?: number;     // default 5, 4-7
  journeys_per_persona?: number;  // default 2, 1-3
}
```

**Response:** `200 OK`

```ts
{
  personas: Array<{
    id: string;
    journeys: Array<{
      id: string;
      title: string;              // 3-5 words
      steps: Array<{
        id: string;
        label: string;
        icon: string;
        api: string;              // snake_case capability key (noun)
      }>;
    }>;
  }>;
  unique_api_keys: string[];      // deduplicated step.api for batch /llm/describe
  model_used: string;
}
```

**Api key rules:** Step label "Sign In" → api `auth`; "Pay Now" → `payment`; "Send Message to Doctor" → `secure_messaging`. Noun only, deduplicated across all steps.

**Errors:** `400`, `500`.

---

### `POST /llm/describe`

Produce a short capability description and input/output schema for one api_key. Called in batches (e.g. 10 at a time) from the frontend, one call per unique api_key. Results are used as the `description` (and optional expected_io) when calling `/api/rag/lookup`.

**Request:** `application/json`

```ts
{
  api_key: string;                // snake_case from journey step
  idea: string;
  step_label: string;
  persona_label: string;
  journey_title: string;
}
```

**Response:** `200 OK`

```ts
{
  api_key: string;                // echoed for correlation
  description: string;             // 1-2 sentence capability description for RAG
  input_schema: string;
  output_schema: string;
}
```

**Errors:** `400`, `500`.

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
| POST   | `/llm/features`    | FeaturesRequest (idea, min/max_features) | FeaturesResponse (features, idea_summary, model_used) |
| POST   | `/llm/suggest-personas` | SuggestPersonasRequest          | SuggestPersonasResponse (personas, model_used) |
| POST   | `/llm/generate-journeys` | GenerateJourneysRequest        | GenerateJourneysResponse (personas, unique_api_keys, model_used) |
| POST   | `/llm/describe`    | DescribeRequest (api_key, idea, step_label, persona_label, journey_title) | DescribeResponse (api_key, description, input_schema, output_schema) |
| POST   | `/api/rag/lookup`  | RAGLookupRequest                 | RAGLookupResponse |
| POST   | `/ingest`          | —                                | `{ "status": "ok", "upserted": N }` |
