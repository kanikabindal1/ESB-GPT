# ESB-GPT
API and Workflow Recommender

## Setup (Conda)

From the project root:

```bash
# Option A: named env (stored in conda’s envs dir)
conda env create -f environment.yml
conda activate esb-gpt
```

```bash
# Option B: env inside project (no write to ~/.conda)
conda env create -f environment.yml --prefix ./env
conda activate ./env
```

Then set your OpenAI key in `.env`:

```
OPENAI_API_KEY=your_key_here
```

Install deps if you used a blank env:

```bash
pip install -r requirements.txt
```

Ingest API records into the vector DB (run once after adding/changing `data/apis.json`):

```bash
python scripts/ingest.py
```

Run the API:

```bash
uvicorn app.main:app --reload
```

- **UI:** [http://localhost:8000/](http://localhost:8000/) — search box and results in the browser
- Health: [http://localhost:8000/health](http://localhost:8000/health)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Hosting (Phase 8)

### Option A: ngrok (instant public URL)

1. Start the API locally: `uvicorn app.main:app --reload`
2. In another terminal: `ngrok http 8000`
3. Use the HTTPS URL ngrok prints (e.g. `https://abc123.ngrok.io`) to call the API from anywhere.

Replace `localhost:8000` with your ngrok URL in the examples below.

### Option B: Railway (cloud deploy)

1. Push the repo to GitHub and connect it at [railway.app](https://railway.app).
2. Add a variable: `OPENAI_API_KEY` = your key (no `.env` file in cloud).
3. Deploy; Railway uses `railway.json` to run:  
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. In the dashboard, open the generated public URL.

**Note:** ChromaDB stores data under `./db`. On Railway this is ephemeral unless you add a volume. For a persistent index, re-run ingestion after deploy (e.g. `POST /ingest` with data in `data/apis.json` baked into the image, or ingest on startup).

## Sample queries & cURL

Base URL: use `http://localhost:8000` or your ngrok/Railway URL.  
You can also import **`docs/ESB-GPT.postman_collection.json`** into Postman and set the `baseUrl` variable to your host.

**Health**
```bash
curl -s http://localhost:8000/health
```

**Search** (natural language → API match + optional enhancement)
```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "get all orders for a customer"}'
```

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "charge a credit card for 10 dollars"}'
```

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "send an email to a user"}'
```

**Re-run ingestion** (e.g. after adding APIs to `data/apis.json`)
```bash
curl -s -X POST http://localhost:8000/ingest
```

## Testing

Install dev dependencies, then run tests from the project root:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Optional: coverage report with `pytest tests/ --cov=app --cov=scripts --cov-report=term-missing`.
