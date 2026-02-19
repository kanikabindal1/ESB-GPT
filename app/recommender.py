"""
Phase 5: LLM Recommender.
Called when match_type == "closest". Uses gpt-4o-mini to suggest what the API covers,
what's missing, and specific enhancements (params, output fields, behavior).
"""
from app.main import openai_client

MODEL = "gpt-4o-mini"
MAX_TOKENS = 400

PROMPT_TEMPLATE = """You are an API consultant. A developer has a requirement that doesn't exactly match any available API.

Developer requirement: {user_query}

Closest available API:
Name: {api_name}
Description: {description}
Inputs: {inputs}
Outputs: {outputs}

Respond with:
1. What this API covers from the requirement
2. What is missing
3. Specific enhancements (new params, output fields, or behavior)"""


def _format_io(obj: dict) -> str:
    """Format input/output dict as readable lines."""
    if not obj or not isinstance(obj, dict):
        return "—"
    return ", ".join(f"{k}: {v}" for k, v in obj.items())


def get_enhancement_suggestion(user_query: str, record: dict) -> str:
    """
    Call gpt-4o-mini with the user's query and closest API details.
    Returns plain-text enhancement suggestion (what it covers, what's missing, specific enhancements).
    """
    api_name = record.get("name", "Unknown API")
    description = record.get("description", "")
    inputs_str = _format_io(record.get("input"))
    outputs_str = _format_io(record.get("output"))

    prompt = PROMPT_TEMPLATE.format(
        user_query=user_query,
        api_name=api_name,
        description=description,
        inputs=inputs_str,
        outputs=outputs_str,
    )

    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )

    content = resp.choices[0].message.content
    return (content or "").strip()
