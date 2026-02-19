"""Dump OpenAPI spec to openapi.json (run from this dir: python dump_openapi.py)."""
import json
from pathlib import Path
from main import app

spec = app.openapi()
path = Path(__file__).parent / "openapi.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=2)
print(f"Wrote {path}")
