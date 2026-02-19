# API Metadata Crawler

Crawls API source (OpenAPI spec or FastAPI project) and outputs API metadata in the **api-knowledge-store** JSON format.

## Output format

Each API in the generated JSON has:

- `id`, `name`, `domain`, `description`
- `owner`, `team`, `version`
- `method`, `path`, `url`
- `confluence`, `bitbucket` (empty unless provided)
- `tags`
- `sample_input`, `sample_output` (from request/response schemas)
- `input`, `output` (field → "type, required|optional")
- `manhours`, `api_efficiency`, `readiness` (defaults)

## Usage

### 1. From OpenAPI URL (e.g. running server)

```bash
cd api-registry
python -m crawler.openapi_to_registry http://localhost:8000/openapi.json -o crawled-apis.json
```

### 2. From OpenAPI file

```bash
python -m crawler.openapi_to_registry ./openapi.json -o crawled-apis.json
```

### 3. From FastAPI project directory

Runs the app to generate OpenAPI, then converts to registry format. **Requires the FastAPI project’s dependencies to be installed** (e.g. `pip install -r requirements.txt` in that project):

```bash
python -m crawler.openapi_to_registry ../airtel-africa-mock-apis --fastapi -o crawled-apis.json
```

Alternatively, from the FastAPI project run `python dump_openapi.py` to write `openapi.json`, then crawl that file from the api-registry folder.

### Options

- `-o, --output` – Output JSON path (default: `crawled-apis.json`)
- `--base-url` – Base URL for `url` field (default: `https://api.company.com`)
- `--owner` – Default owner (default: `Crawler`)
- `--team` – Default team (default: `Platform`)
- `--fastapi` – Treat source as FastAPI project directory (main:app)

## Example: crawl Airtel Africa mock APIs

```bash
# Start mock server (optional, for URL mode)
cd airtel-africa-mock-apis && uvicorn main:app --port 8000 &

# From URL
cd api-registry && python -m crawler.openapi_to_registry http://localhost:8000/openapi.json -o crawled-apis.json --base-url http://localhost:8000

# Or from project dir (no server needed)
cd api-registry && python -m crawler.openapi_to_registry ../airtel-africa-mock-apis --fastapi -o crawled-apis.json --base-url http://localhost:8000
```

Then merge or use `crawled-apis.json` in your registry pipeline.
