"""
Convert OpenAPI 3.x spec (URL or file) to api-knowledge-store JSON format.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen


def _schema_to_input_output(schema: dict | None) -> dict[str, str]:
    """Convert JSON Schema to our format: { "field": "type, required|optional" }."""
    if not schema or "properties" not in schema:
        return {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    out = {}
    for name, prop in props.items():
        t = prop.get("type", "string")
        if "$ref" in prop:
            t = prop["$ref"].split("/")[-1]
        req = "required" if name in required else "optional"
        out[name] = f"{t}, {req}"
    return out


def _schema_to_sample(schema: dict | None) -> str:
    """Build a minimal sample JSON from schema."""
    if not schema or "properties" not in schema:
        return "{}"
    props = schema.get("properties", {})
    sample = {}
    for name, prop in props.items():
        t = prop.get("type", "string")
        if t == "string":
            sample[name] = "string"
        elif t == "integer":
            sample[name] = 0
        elif t == "number":
            sample[name] = 0.0
        elif t == "boolean":
            sample[name] = True
        elif t == "array":
            sample[name] = []
        else:
            sample[name] = "value"
    return json.dumps(sample, indent=2)


def _path_to_id(method: str, path: str) -> str:
    """Generate stable id from method and path."""
    clean = re.sub(r"[{}]", "", path)
    clean = re.sub(r"[^a-zA-Z0-9/]", "_", clean)
    clean = clean.strip("/").replace("/", "_")
    return f"api-{method.lower()}-{clean}".replace("__", "_")


def _path_to_name(path: str, summary: str | None, operation_id: str | None) -> str:
    """Human-readable API name."""
    if summary:
        return summary.replace(" API", "").strip() + (" API" if "API" not in summary else "")
    if operation_id:
        return re.sub(r"([A-Z])", r" \1", operation_id).strip().title() + " API"
    parts = path.strip("/").split("/")
    return " ".join(p.title() for p in parts[-2:] if p) + " API"


def _infer_domain(path: str, tags: list[str]) -> str:
    """Infer domain from path or tags."""
    if tags:
        return tags[0].lower().replace(" ", "-")
    path_lower = path.lower()
    if "kyc" in path_lower or "identity" in path_lower:
        return "identity"
    if "airtelmoney" in path_lower or "wallet" in path_lower or "p2p" in path_lower:
        return "payments"
    if "sim" in path_lower or "registration" in path_lower:
        return "identity"
    if "biller" in path_lower:
        return "payments"
    if "agent" in path_lower:
        return "partner"
    if "fraud" in path_lower or "aml" in path_lower or "kyt" in path_lower:
        return "identity"
    if "care" in path_lower or "complaint" in path_lower:
        return "care"
    if "offer" in path_lower:
        return "customer"
    if "regulatory" in path_lower or "privacy" in path_lower:
        return "compliance"
    if "voucher" in path_lower or "stock" in path_lower or "sales" in path_lower:
        return "retail"
    return "general"


def openapi_to_registry(
    spec: dict,
    base_url: str = "https://api.company.com",
    default_owner: str = "Crawler",
    default_team: str = "Platform",
) -> list[dict]:
    """Convert OpenAPI spec to list of API objects in registry format."""
    apis = []
    paths = spec.get("paths", {})
    info = spec.get("info", {})
    version = info.get("version", "1.0.0")
    servers = spec.get("servers", [])
    if servers and "url" in servers[0]:
        base_url = servers[0]["url"].rstrip("/")

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not op:
                continue
            op_id = op.get("operationId", "")
            summary = op.get("summary") or op.get("description", "")
            description = op.get("description") or summary or f"{method.upper()} {path}"
            tags = op.get("tags", [])

            # Request body schema
            body = op.get("requestBody", {})
            content = (body.get("content") or {}).get("application/json", {})
            req_schema = content.get("schema")
            if req_schema and "$ref" in req_schema:
                req_schema = _resolve_ref(spec, req_schema["$ref"])
            input_schema = _schema_to_input_output(req_schema)
            sample_input = _schema_to_sample(req_schema)

            # Response schema (200)
            responses = op.get("responses", {})
            res_content = (responses.get("200") or responses.get("201") or {}).get("content", {}).get("application/json", {})
            res_schema = res_content.get("schema")
            if res_schema and "$ref" in res_schema:
                res_schema = _resolve_ref(spec, res_schema["$ref"])
            output_schema = _schema_to_input_output(res_schema)
            sample_output = _schema_to_sample(res_schema)

            api_id = _path_to_id(method, path)
            name = _path_to_name(path, summary, op_id)
            domain = _infer_domain(path, tags)

            apis.append({
                "id": api_id,
                "name": name,
                "domain": domain,
                "description": description[:500] if description else name,
                "owner": default_owner,
                "team": default_team,
                "version": version,
                "method": method.upper(),
                "path": path,
                "url": f"{base_url}{path}",
                "confluence": "",
                "bitbucket": "",
                "tags": tags or [domain],
                "sample_input": sample_input,
                "sample_output": sample_output,
                "input": input_schema,
                "output": output_schema,
                "manhours": 0,
                "api_efficiency": "medium",
                "readiness": "production",
            })

    return apis


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve $ref from OpenAPI spec."""
    parts = ref.strip("#/").split("/")
    cur = spec
    for p in parts:
        cur = cur.get(p, {})
    return cur


def load_openapi(source: str) -> dict:
    """Load OpenAPI spec from URL or file path."""
    source = source.strip()
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=30) as f:
            return json.load(f)
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"OpenAPI source not found: {source}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def crawl_from_fastapi_directory(project_dir: str | Path) -> dict:
    """Run FastAPI app in project dir and return OpenAPI spec (main:app)."""
    import subprocess
    project_dir = Path(project_dir).resolve()
    if not project_dir.is_dir():
        raise NotADirectoryError(str(project_dir))
    code = """
import json, sys
sys.path.insert(0, {path!r})
from main import app
print(json.dumps(app.openapi()))
""".format(path=str(project_dir))
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Failed to get OpenAPI from FastAPI app")
    return json.loads(result.stdout)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Crawl API source and output registry JSON.")
    p.add_argument("source", help="OpenAPI URL, path to openapi.json, or path to project dir for FastAPI")
    p.add_argument("-o", "--output", default="crawled-apis.json", help="Output JSON path")
    p.add_argument("--base-url", default="https://api.company.com", help="Base URL for APIs")
    p.add_argument("--owner", default="Crawler", help="Default owner")
    p.add_argument("--team", default="Platform", help="Default team")
    p.add_argument("--fastapi", action="store_true", help="Source is a directory containing FastAPI app (main:app)")
    args = p.parse_args()

    if args.fastapi:
        project_dir = Path(args.source)
        if not project_dir.is_dir():
            sys.exit("With --fastapi, source must be a directory")
        try:
            spec = crawl_from_fastapi_directory(project_dir)
        except Exception as e:
            sys.exit(f"Failed to get OpenAPI from FastAPI app: {e}")
    else:
        spec = load_openapi(args.source)

    apis = openapi_to_registry(spec, base_url=args.base_url, default_owner=args.owner, default_team=args.team)
    out = {
        "_meta": {
            "schema_version": "1.0",
            "description": "API metadata crawled from source",
            "source": args.source,
            "total_apis": len(apis),
        },
        "apis": apis,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(apis)} APIs to {out_path}")


if __name__ == "__main__":
    main()
