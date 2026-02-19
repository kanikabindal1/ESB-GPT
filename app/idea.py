"""
IdeaGPT LLM: idea → features, idea+features → personas/journeys, missing steps → Jira stories.
"""
import json
import re

from app.models import (
    FeatureItem,
    FeaturesRequest,
    FeaturesResponse,
    IdeaPersonasResponse,
    IdeaFeaturesResponse,
    JiraGenerateResponse,
    JiraStory,
    Journey,
    JourneyStep,
    PersonaItem,
)


class FeatureParseError(Exception):
    """Raised when LLM response cannot be parsed or validated after retry. Maps to HTTP 422."""

    pass

MODEL = "gpt-4o-mini"
MAX_TOKENS = 2000

# Design token colors for personas (UI expects hex)
PERSONA_COLORS = [
    {"color": "#1a4fa0", "colorBg": "#eef4ff", "colorBorder": "#bcd2f5"},
    {"color": "#1c7a4c", "colorBg": "#eef8f2", "colorBorder": "#b4dcc7"},
    {"color": "#6d28d9", "colorBg": "#f5f3ff", "colorBorder": "#d0c4f8"},
]

FEATURES_PROMPT = """You are a product manager. Given a product idea, output a JSON array of 5-12 product features that would be needed to build it.

Product idea: {idea}

For each feature provide:
- id: short snake_case id (e.g. "user_auth", "cart_checkout")
- icon: a single emoji that fits the feature
- title: short title (2-5 words)
- desc: one sentence description
- on: true

Output ONLY a valid JSON array, no markdown or explanation. Example:
[{{"id":"auth","icon":"🔐","title":"User Authentication","desc":"Login, SSO and session management","on":true}}]"""


PERSONAS_PROMPT = """You are a product manager. Given a product idea and list of feature IDs, output 2-4 user personas with their journeys and steps.

Product idea: {idea}
Selected feature IDs: {feature_ids}

For each persona provide:
- id: short snake_case (e.g. "guest", "member", "admin")
- label: display name (e.g. "Guest Shopper")
- icon: one emoji
- desc: one sentence
- journeys: array of 1-2 journeys. Each journey has:
  - id: short id (e.g. "j1", "j2")
  - title: journey name (e.g. "Browse & Discover")
  - steps: array of 4-8 steps. Each step has:
    - id: unique short id (e.g. "s1", "s2")
    - label: short label (e.g. "Search", "Add to Cart")
    - icon: one emoji
    - search_text: a natural language phrase describing what API/capability this step needs (e.g. "search products by query", "add item to shopping cart", "process payment"). This will be used to match against an API catalog.

Do NOT include "color", "colorBg", "colorBorder" in the JSON — the backend will add them.
Output ONLY a valid JSON object with a single key "personas" whose value is an array. No markdown, no code fence."""


JIRA_PROMPT = """You are a tech lead. Given a list of workflow steps that need new APIs (no existing API matched), generate Jira-style stories.

Missing steps (each needs an API to be built):
{missing_steps_json}

For each step, output one story with:
- title: API name (e.g. "Cart Management API")
- epic: epic name (e.g. "Commerce Platform")
- priority: P0, P1, or P2
- story: one sentence user story starting with "As a ... I want ... So that ..."
- acceptance: array of 3-5 acceptance criteria strings
- sp: story points (1-13)
- days: estimated man-days (3-15)
- sprint: "Sprint 1", "Sprint 2", or "Sprint 3"
- squad: team name (e.g. "Commerce Team")
- deps: array of 0-3 dependency API/service names

Output ONLY a valid JSON object with a single key "stories" whose value is an array of objects. No markdown, no code fence."""


# --- POST /llm/features: gpt-4o, response_format json_object ---
LLM_FEATURES_MODEL = "gpt-4o"
LLM_FEATURES_MAX_TOKENS = 2000
LLM_FEATURES_TEMPERATURE = 0

LLM_FEATURES_SYSTEM = """You are a product analyst specialising in enterprise software.
You decompose product ideas into discrete, buildable features.
Always respond with valid JSON only.
No markdown, no explanation, no code fences.
The root key must be 'features' (array) and 'idea_summary' (string)."""

LLM_FEATURES_USER = """Given this product idea, extract {min_features}-{max_features} features.

Idea: "{idea}"

Return JSON with keys: 'features' (array) and 'idea_summary' (string).
Each feature object: {{ id, icon, title, desc, on: true }}
- id: 'f1', 'f2', ... (sequential)
- icon: single relevant emoji
- title: 4-6 word feature name
- desc: max 12 word description
- on: true

idea_summary: one sentence describing what this product does."""

LLM_FEATURES_USER_STRICT = """Return exactly {exact_count} features for this product idea. No more, no less.

Idea: "{idea}"

Return JSON with keys: 'features' (array) and 'idea_summary' (string).
Each feature object: {{ id, icon, title, desc, on: true }}
- id: 'f1', 'f2', ... (sequential)
- icon: single relevant emoji
- title: 4-6 word feature name
- desc: max 12 word description
- on: true

idea_summary: one sentence describing what this product does."""


def _extract_json(text: str) -> str:
    """Strip markdown code fence if present and return inner JSON string."""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text


def generate_features(idea: str) -> IdeaFeaturesResponse:
    """Call LLM to extract product features from idea. Returns features list."""
    from app.main import openai_client

    prompt = FEATURES_PROMPT.format(idea=idea)
    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )
    content = (resp.choices[0].message.content or "").strip()
    raw = _extract_json(content)
    try:
        arr = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    if not isinstance(arr, list):
        raise ValueError("LLM did not return a JSON array")
    features = []
    for i, item in enumerate(arr):
        if not isinstance(item, dict):
            continue
        features.append(
            FeatureItem(
                id=str(item.get("id", f"f{i}")).strip() or f"f{i}",
                icon=str(item.get("icon", "⚙️"))[:2],
                title=str(item.get("title", "Feature")).strip() or "Feature",
                desc=str(item.get("desc", "")).strip(),
                on=bool(item.get("on", True)),
            )
        )
    return IdeaFeaturesResponse(features=features)


def _parse_llm_features_response(
    content: str, min_features: int, max_features: int
) -> tuple[list[dict], str]:
    """Parse LLM JSON content into (features_raw, idea_summary). Raises FeatureParseError on parse/structure failure only (not on count)."""
    content = (content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise FeatureParseError("Invalid JSON")
    if not isinstance(data, dict):
        raise FeatureParseError("Response is not a JSON object")
    features_raw = data.get("features")
    idea_summary = data.get("idea_summary")
    if not isinstance(features_raw, list):
        raise FeatureParseError("Missing or invalid 'features' array")
    if not isinstance(idea_summary, str):
        idea_summary = str(idea_summary or "").strip() or "Product idea."
    return features_raw, idea_summary


def _patch_feature_item(i: int, item: dict) -> FeatureItem:
    """Ensure all 5 fields with safe defaults. Single emoji: take first character for icon."""
    raw_icon = str(item.get("icon", "⚙️")).strip()
    icon = raw_icon[0] if raw_icon else "⚙️"
    return FeatureItem(
        id=str(item.get("id", f"f{i + 1}")).strip() or f"f{i + 1}",
        icon=icon,
        title=str(item.get("title", "Feature")).strip() or "Feature",
        desc=str(item.get("desc", "")).strip(),
        on=bool(item.get("on", True)),
    )


def generate_llm_features(req: FeaturesRequest) -> FeaturesResponse:
    """Extract 8-12 features from idea using gpt-4o with JSON mode. Retry once on count mismatch or parse failure."""
    min_f = req.min_features
    max_f = req.max_features
    idea = req.idea

    def call_llm(strict_count: int | None) -> str:
        from app.main import openai_client

        if strict_count is not None:
            user_msg = LLM_FEATURES_USER_STRICT.format(
                idea=idea, exact_count=strict_count
            )
        else:
            user_msg = LLM_FEATURES_USER.format(
                idea=idea, min_features=min_f, max_features=max_f
            )
        resp = openai_client.chat.completions.create(
            model=LLM_FEATURES_MODEL,
            temperature=LLM_FEATURES_TEMPERATURE,
            max_tokens=LLM_FEATURES_MAX_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": LLM_FEATURES_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    # First attempt
    content = call_llm(None)
    try:
        features_raw, idea_summary = _parse_llm_features_response(
            content, min_f, max_f
        )
    except FeatureParseError:
        # Retry once with same-style prompt
        content = call_llm(None)
        try:
            features_raw, idea_summary = _parse_llm_features_response(
                content, min_f, max_f
            )
        except FeatureParseError:
            raise

    # Count in range? If not, retry once with stricter prompt
    n = len(features_raw)
    if n < min_f or n > max_f:
        exact = min_f if n < min_f else max_f
        content = call_llm(exact)
        try:
            features_raw, idea_summary = _parse_llm_features_response(
                content, min_f, max_f
            )
        except FeatureParseError:
            raise
        n = len(features_raw)
        if n < min_f or n > max_f:
            raise FeatureParseError(
                f"Feature count {n} outside range [{min_f}, {max_f}] after retry"
            )

    # Patch each feature to FeatureItem with safe defaults
    features = []
    for i, item in enumerate(features_raw):
        if not isinstance(item, dict):
            features.append(
                FeatureItem(
                    id=f"f{i + 1}",
                    icon="⚙️",
                    title="Feature",
                    desc="",
                    on=True,
                )
            )
        else:
            features.append(_patch_feature_item(i, item))

    return FeaturesResponse(
        features=features,
        idea_summary=idea_summary,
        model_used=LLM_FEATURES_MODEL,
    )


def generate_personas(idea: str, feature_ids: list[str]) -> IdeaPersonasResponse:
    """Call LLM to generate personas and journeys. Backend adds colors."""
    from app.main import openai_client

    prompt = PERSONAS_PROMPT.format(
        idea=idea,
        feature_ids=json.dumps(feature_ids) if feature_ids else "[]",
    )
    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )
    content = (resp.choices[0].message.content or "").strip()
    raw = _extract_json(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    personas_raw = data.get("personas") if isinstance(data, dict) else None
    if not isinstance(personas_raw, list):
        raise ValueError("LLM did not return a personas array")
    personas = []
    for idx, p in enumerate(personas_raw):
        if not isinstance(p, dict):
            continue
        colors = PERSONA_COLORS[idx % len(PERSONA_COLORS)]
        journeys = []
        for j_idx, j in enumerate(p.get("journeys") or []):
            if not isinstance(j, dict):
                continue
            steps = []
            for s_idx, s in enumerate(j.get("steps") or []):
                if not isinstance(s, dict):
                    continue
                steps.append(
                    JourneyStep(
                        id=str(s.get("id", f"step_{idx}_{j_idx}_{s_idx}")).strip() or f"s{s_idx}",
                        label=str(s.get("label", "Step")).strip() or "Step",
                        icon=str(s.get("icon", "•"))[:2],
                        search_text=str(s.get("search_text", s.get("label", ""))).strip() or str(s.get("label", "")),
                    )
                )
            journeys.append(
                Journey(
                    id=str(j.get("id", f"j{j_idx}")).strip() or f"j{j_idx}",
                    title=str(j.get("title", "Journey")).strip() or "Journey",
                    steps=steps,
                )
            )
        personas.append(
            PersonaItem(
                id=str(p.get("id", f"p{idx}")).strip() or f"p{idx}",
                label=str(p.get("label", "Persona")).strip() or "Persona",
                icon=str(p.get("icon", "👤"))[:2],
                color=colors["color"],
                color_bg=colors["colorBg"],
                color_border=colors["colorBorder"],
                desc=str(p.get("desc", "")).strip(),
                journeys=journeys,
            )
        )
    return IdeaPersonasResponse(personas=personas)


def generate_jira_stories(missing_steps: list[dict]) -> JiraGenerateResponse:
    """Call LLM to generate Jira stories for missing API steps."""
    if not missing_steps:
        return JiraGenerateResponse(stories=[])
    missing_steps_json = json.dumps(
        [
            {
                "label": s.get("label", ""),
                "search_text": s.get("search_text", s.get("label", "")),
                "journey_title": s.get("journey_title", ""),
                "persona_label": s.get("persona_label", ""),
            }
            for s in missing_steps
        ],
        indent=2,
    )
    from app.main import openai_client

    prompt = JIRA_PROMPT.format(missing_steps_json=missing_steps_json)
    resp = openai_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
    )
    content = (resp.choices[0].message.content or "").strip()
    raw = _extract_json(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    stories_raw = data.get("stories") if isinstance(data, dict) else None
    if not isinstance(stories_raw, list):
        raise ValueError("LLM did not return a stories array")
    stories = []
    for i, st in enumerate(stories_raw):
        if not isinstance(st, dict):
            continue
        acceptance = st.get("acceptance") or []
        if isinstance(acceptance, str):
            acceptance = [acceptance]
        stories.append(
            JiraStory(
                title=str(st.get("title", "API Story")).strip() or "API Story",
                epic=str(st.get("epic", "Platform")).strip() or "Platform",
                priority=str(st.get("priority", "P2")).strip().upper()[:2] or "P2",
                story=str(st.get("story", "")).strip() or "As a developer I want this API.",
                acceptance=[str(a).strip() for a in acceptance if a],
                sp=int(st.get("sp", 5)) if isinstance(st.get("sp"), (int, float)) else 5,
                days=int(st.get("days", 5)) if isinstance(st.get("days"), (int, float)) else 5,
                sprint=str(st.get("sprint", "Sprint 1")).strip() or "Sprint 1",
                squad=str(st.get("squad", "Platform Team")).strip() or "Platform Team",
                deps=[str(d).strip() for d in (st.get("deps") or []) if d],
            )
        )
    return JiraGenerateResponse(stories=stories)
