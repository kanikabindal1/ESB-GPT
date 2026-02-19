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

## Summary table

| Method | Path     | Request body      | Response body                    |
|--------|----------|--------------------|----------------------------------|
| GET    | `/health`| —                  | `{ "status": "ok" }`            |
| POST   | `/search`| `{ "query": "..." }`| `{ "results": [ APIResult, ... ] }` |
| POST   | `/ingest`| —                  | `{ "status": "ok", "upserted": N }` |
