"""
IdeaGPT LLM: idea → features, idea+features → personas/journeys, missing steps → Jira stories.
"""
import json
import re

from app.models import (
    ChatRequest,
    ChatResponse,
    ConfirmedPersona,
    DescribeRequest,
    DescribeResponse,
    FeatureDescription,
    FeatureItem,
    FeaturesRequest,
    FeaturesResponse,
    GenerateJourneysRequest,
    GenerateJourneysResponse,
    IdeaPersonasResponse,
    IdeaFeaturesResponse,
    JiraGenerateResponse,
    JiraRequest,
    JiraResponse,
    JiraStory,
    Journey,
    JourneyStep,
    LLMJourney,
    LLMJourneyStep,
    PersonaSuggestion,
    PersonaWithJourneys,
    PersonaItem,
    SuggestPersonasRequest,
    SuggestPersonasResponse,
    SummariseRequest,
    SummariseResponse,
    UseCaseDescription,
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


# --- POST /llm/suggest-personas ---
SUGGEST_PERSONAS_MODEL = "gpt-4o"
SUGGEST_PERSONAS_TEMPERATURE = 0.1
SUGGEST_PERSONAS_MAX_TOKENS = 1500

SUGGEST_PERSONAS_SYSTEM = """You are a UX strategist with expertise in enterprise product design.
Given a product idea and its features, suggest the most relevant user personas.
Each persona must be meaningfully distinct in their goals and workflows.
Always respond with valid JSON only. Root key must be 'personas' (array)."""

SUGGEST_PERSONAS_USER = """Product idea: "{idea}"
Summary: "{idea_summary}"
Confirmed features: {selected_features_str}

Suggest {min_personas}-{max_personas} distinct user personas for this product.

For each persona return:
  id: snake_case (e.g. 'clinic_admin')
  label: 2-4 word display name
  icon: single emoji representing the persona
  desc: one sentence description of who this person is
  color: one of ['blue', 'green', 'purple', 'amber']
  rationale: why this persona is critical to this specific product
  suggested_journeys: 2-3 short journey names they would take
  is_primary: true if this persona is central to the product's success

Ensure personas cover both end-users and any operator/admin roles if relevant.
JSON only. Root key: 'personas'."""


# --- POST /llm/generate-journeys ---
GENERATE_JOURNEYS_MODEL = "gpt-4o"
GENERATE_JOURNEYS_TEMPERATURE = 0
GENERATE_JOURNEYS_MAX_TOKENS = 4000

GENERATE_JOURNEYS_SYSTEM = """You generate user journeys for product personas.
Each step has an 'api' field: a snake_case NOUN that is a capability key for API lookup.
NOT a verb phrase. Same capability must use the SAME key everywhere (e.g. Sign In and Log Out both use 'auth').
Examples: Sign In -> auth, Pay Now -> payment, Send Message to Doctor -> secure_messaging, Upload Lab Report -> lab_results, Book Appointment -> scheduling, Get Credit Score -> credit_scoring.
Always respond with valid JSON only. Root key: 'personas' (array of { id, journeys }). Each journey: id, title, steps. Each step: id, label, icon, api (snake_case noun only)."""

GENERATE_JOURNEYS_USER = """Product idea: "{idea}"
Selected features: {selected_features_str}

Confirmed personas (use suggested_journeys as hints for journey names):
{confirmed_personas_str}

Generate journeys: {steps_per_journey} steps per journey (4-7), {journeys_per_persona} journeys per persona (1-3).
For each step set api to a snake_case capability noun. Deduplicate: same capability = same api key.
JSON only. Root key: 'personas'. Each persona: id, journeys (array). Each journey: id, title, steps. Each step: id, label, icon, api."""


# --- POST /llm/describe ---
DESCRIBE_MODEL = "gpt-4o-mini"
DESCRIBE_TEMPERATURE = 0
DESCRIBE_MAX_TOKENS = 300

DESCRIBE_SYSTEM = """You produce a short capability description and input/output schema summary for API search.
Output valid JSON only. Keys: description (1-2 sentences), input_schema (brief), output_schema (brief)."""

DESCRIBE_USER = """Api key (capability): {api_key}
Product idea: {idea}
Step: {step_label}
Persona: {persona_label}
Journey: {journey_title}

Write a 1-2 sentence capability description suitable for semantic API search, and brief input_schema and output_schema text.
JSON only. Keys: description, input_schema, output_schema."""


# --- POST /llm/jira (one ticket per api_key, BRD §4.5) ---
LLM_JIRA_MODEL = "gpt-4o"
LLM_JIRA_TEMPERATURE = 0.2
LLM_JIRA_MAX_TOKENS = 1200

LLM_JIRA_SYSTEM = """You are a tech lead. Given a missing API capability (api_key), product idea, and the workflow steps that need it, generate exactly one Jira ticket.
Always respond with valid JSON only. No markdown, no code fence.
Root keys: title, epic, priority, story, acceptance (array of 4-5 strings), sp (story points: 3/5/8/13/21), days (man-days), sprint, squad, deps (array of 0-3 API/service names)."""

LLM_JIRA_USER = """Missing API capability (api_key): {api_key}
Product idea: {idea}
Suggested priority: {suggested_priority}
RAG gap summary (if any): {rag_gap_summary}
RAG enhancements: {rag_enhancements_str}

Affected workflow steps (persona / journey / step):
{affected_steps_str}

Generate one Jira ticket for building this API. Use the suggested priority.
Story must be in "As a [persona], I want ... So that ..." format.
Return JSON only with keys: title, epic, priority, story, acceptance, sp, days, sprint, squad, deps."""


# --- POST /llm/chat (product discovery coach) ---
CHAT_MODEL = "gpt-4o"
CHAT_TEMPERATURE = 0.7
CHAT_MAX_TOKENS = 600

CHAT_SYSTEM = """You are a product discovery coach helping a user articulate their software product idea.
Your goal is to understand: what the product does, who uses it, and what the core workflows are.

Ask one focused question at a time. Do not overwhelm with multiple questions.
After 4-6 turns, when you have a clear picture of the product, its users, and 2-3 key workflows,
set is_ready_to_summarise to true in your JSON response and tell the user you have enough to proceed.

Always respond with JSON:
{ "reply": "<your message>", "is_ready_to_summarise": <true|false> }
No preamble, no markdown outside the reply field.

Good discovery questions cover:
- What problem does this solve and for whom?
- Who are the different types of users (end users vs admins)?
- What are the 2-3 most important things a user needs to do?
- Are there any integrations, compliance requirements, or constraints?"""


# --- POST /llm/summarise (conversation → structured brief) ---
SUMMARISE_MODEL = "gpt-4o"
SUMMARISE_TEMPERATURE = 0
SUMMARISE_MAX_TOKENS = 3000

SUMMARISE_SYSTEM = """You are a product analyst. Given a discovery conversation between a user and a coach,
extract a structured product brief.

Be specific and detailed — the output will be used to generate an API coverage report,
so vague feature names like "dashboard" or "settings" are not useful.
Prefer: "Real-time order tracking with carrier integration" over "order tracking".

Always respond with valid JSON only matching the specified schema. No preamble."""

SUMMARISE_USER_TEMPLATE = """Here is a product discovery conversation:

{messages_formatted}

Extract a structured product brief with:
- idea: 1-2 sentence summary of the product
- idea_summary: one sentence
- detailed_description: 3-5 sentences covering purpose, users, and context
- inferred_features: 5-10 features, each with a title and a 2-4 sentence description
- use_cases: 2-4 use cases with persona, goal, and workflow
- constraints: any compliance, integration, or technical constraints mentioned
- open_questions: anything that was unclear or not discussed

JSON only."""


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


def _format_features_str(
    titles: list[str],
    descriptions: list[FeatureDescription] | None,
) -> str:
    """Build prompt string for features; use descriptions when provided (same order as titles)."""
    if not titles:
        return "(none)"
    if not descriptions:
        return ", ".join(titles)
    if len(descriptions) >= len(titles):
        parts = []
        for i, t in enumerate(titles):
            d = (descriptions[i].description or "").strip()
            parts.append(f"{t}: {d}" if d else t)
        return "\n".join(parts)
    desc_by_title = {fd.title.strip(): (fd.description or "").strip() for fd in descriptions}
    parts = [f"{t}: {desc_by_title[t]}" if desc_by_title.get(t) else t for t in titles]
    return "\n".join(parts)


def suggest_personas(req: SuggestPersonasRequest) -> SuggestPersonasResponse:
    """Suggest distinct user personas for idea + features. Trigger: Map User Journeys."""
    from app.main import openai_client

    selected_features_str = _format_features_str(
        req.selected_features,
        req.selected_feature_descriptions,
    )
    user_msg = SUGGEST_PERSONAS_USER.format(
        idea=req.idea,
        idea_summary=req.idea_summary,
        selected_features_str=selected_features_str,
        min_personas=req.min_personas,
        max_personas=req.max_personas,
    )
    resp = openai_client.chat.completions.create(
        model=SUGGEST_PERSONAS_MODEL,
        temperature=SUGGEST_PERSONAS_TEMPERATURE,
        max_tokens=SUGGEST_PERSONAS_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SUGGEST_PERSONAS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    personas_raw = data.get("personas") if isinstance(data, dict) else []
    if not isinstance(personas_raw, list):
        raise ValueError("LLM did not return a personas array")
    valid_colors = ["blue", "green", "purple", "amber"]
    personas = []
    for i, p in enumerate(personas_raw):
        if not isinstance(p, dict):
            continue
        raw_color = str(p.get("color", "blue")).lower().strip()
        color = raw_color if raw_color in valid_colors else "blue"
        suggested = p.get("suggested_journeys")
        if not isinstance(suggested, list):
            suggested = []
        suggested = [str(s).strip() for s in suggested if s]
        personas.append(
            PersonaSuggestion(
                id=str(p.get("id", f"persona_{i}")).strip() or f"persona_{i}",
                label=str(p.get("label", "Persona")).strip() or "Persona",
                icon=str(p.get("icon", "👤"))[0] if str(p.get("icon", "👤")).strip() else "👤",
                desc=str(p.get("desc", "")).strip() or "User persona.",
                color=color,
                rationale=str(p.get("rationale", "")).strip() or "Relevant to product.",
                suggested_journeys=suggested,
                is_primary=bool(p.get("is_primary", False)),
            )
        )
    return SuggestPersonasResponse(
        personas=personas,
        model_used=SUGGEST_PERSONAS_MODEL,
    )


def generate_journeys(req: GenerateJourneysRequest) -> GenerateJourneysResponse:
    """Generate journeys for confirmed personas; steps use api (snake_case) for RAG."""
    from app.main import openai_client

    selected_features_str = _format_features_str(
        req.selected_features,
        req.selected_feature_descriptions,
    )
    confirmed_personas_str = json.dumps(
        [
            {
                "id": p.id,
                "label": p.label,
                "suggested_journeys": p.suggested_journeys,
            }
            for p in req.confirmed_personas
        ],
        indent=2,
    )
    user_msg = GENERATE_JOURNEYS_USER.format(
        idea=req.idea,
        selected_features_str=selected_features_str,
        confirmed_personas_str=confirmed_personas_str,
        steps_per_journey=req.steps_per_journey,
        journeys_per_persona=req.journeys_per_persona,
    )
    resp = openai_client.chat.completions.create(
        model=GENERATE_JOURNEYS_MODEL,
        temperature=GENERATE_JOURNEYS_TEMPERATURE,
        max_tokens=GENERATE_JOURNEYS_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": GENERATE_JOURNEYS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    personas_raw = data.get("personas") if isinstance(data, dict) else []
    if not isinstance(personas_raw, list):
        raise ValueError("LLM did not return a personas array")
    all_api_keys: list[str] = []
    persona_list: list[PersonaWithJourneys] = []
    for p in personas_raw:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", "")).strip() or "p"
        journeys_raw = p.get("journeys") or []
        if not isinstance(journeys_raw, list):
            continue
        journeys: list[LLMJourney] = []
        for j in journeys_raw:
            if not isinstance(j, dict):
                continue
            jid = str(j.get("id", "")).strip() or "j"
            title = str(j.get("title", "Journey")).strip() or "Journey"
            steps_raw = j.get("steps") or []
            if not isinstance(steps_raw, list):
                continue
            steps: list[LLMJourneyStep] = []
            for si, s in enumerate(steps_raw):
                if not isinstance(s, dict):
                    continue
                api_val = str(s.get("api", "unknown")).strip().lower() or "unknown"
                api_val = "_".join(api_val.split())  # normalize to snake_case
                steps.append(
                    LLMJourneyStep(
                        id=str(s.get("id", f"step_{si}")).strip() or f"step_{si}",
                        label=str(s.get("label", "Step")).strip() or "Step",
                        icon=str(s.get("icon", "•"))[0] if str(s.get("icon", "•")).strip() else "•",
                        api=api_val,
                    )
                )
                all_api_keys.append(api_val)
            journeys.append(LLMJourney(id=jid, title=title, steps=steps))
        persona_list.append(PersonaWithJourneys(id=pid, journeys=journeys))
    seen: set[str] = set()
    unique_api_keys = [k for k in all_api_keys if k not in seen and not seen.add(k)]
    return GenerateJourneysResponse(
        personas=persona_list,
        unique_api_keys=unique_api_keys,
        model_used=GENERATE_JOURNEYS_MODEL,
    )


def describe(req: DescribeRequest) -> DescribeResponse:
    """Produce capability description and input/output schema for RAG lookup. Called in batches per api_key."""
    from app.main import openai_client

    user_msg = DESCRIBE_USER.format(
        api_key=req.api_key,
        idea=req.idea,
        step_label=req.step_label,
        persona_label=req.persona_label,
        journey_title=req.journey_title,
    )
    resp = openai_client.chat.completions.create(
        model=DESCRIBE_MODEL,
        temperature=DESCRIBE_TEMPERATURE,
        max_tokens=DESCRIBE_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DESCRIBE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")
    description = str(data.get("description", "")).strip() or "API capability."
    input_schema = str(data.get("input_schema", "")).strip() or ""
    output_schema = str(data.get("output_schema", "")).strip() or ""
    return DescribeResponse(
        api_key=req.api_key,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
    )


def generate_jira_ticket(req: JiraRequest) -> JiraResponse:
    """Generate one Jira ticket for a missing api_key. BRD §4.5; called per api_key from frontend."""
    from app.main import openai_client

    affected_steps_str = "\n".join(
        f"  - {s.persona_label} / {s.journey_title} / {s.step_label}"
        for s in (req.affected_steps or [])
    ) or "  (no steps listed)"
    rag_enhancements_str = "\n".join(f"  - {e}" for e in (req.rag_enhancements or [])) or "  (none)"

    user_msg = LLM_JIRA_USER.format(
        api_key=req.api_key,
        idea=req.idea,
        suggested_priority=req.suggested_priority,
        rag_gap_summary=(req.rag_gap_summary or "").strip() or "(none)",
        rag_enhancements_str=rag_enhancements_str,
        affected_steps_str=affected_steps_str,
    )
    resp = openai_client.chat.completions.create(
        model=LLM_JIRA_MODEL,
        temperature=LLM_JIRA_TEMPERATURE,
        max_tokens=LLM_JIRA_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": LLM_JIRA_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")

    title = str(data.get("title", "")).strip() or f"API: {req.api_key}"
    epic = str(data.get("epic", "Platform")).strip() or "Platform"
    priority_raw = str(data.get("priority", "P2")).strip().upper()
    priority = priority_raw if priority_raw in ("P0", "P1", "P2") else "P2"
    story = str(data.get("story", "")).strip() or f"As a user I want {req.api_key} API."
    acceptance_raw = data.get("acceptance")
    if isinstance(acceptance_raw, list):
        acceptance = [str(a).strip() for a in acceptance_raw if a][:5]
    else:
        acceptance = [story]
    if not acceptance:
        acceptance = [story]
    sp = int(data.get("sp", 5)) if isinstance(data.get("sp"), (int, float)) else 5
    days = int(data.get("days", 5)) if isinstance(data.get("days"), (int, float)) else 5
    sprint = str(data.get("sprint", "Sprint 1")).strip() or "Sprint 1"
    squad = str(data.get("squad", "Platform Team")).strip() or "Platform Team"
    deps_raw = data.get("deps")
    deps = [str(d).strip() for d in deps_raw if d] if isinstance(deps_raw, list) else []

    return JiraResponse(
        api_key=req.api_key,
        title=title,
        epic=epic,
        priority=priority,
        story=story,
        acceptance=acceptance,
        sp=sp,
        days=days,
        sprint=sprint,
        squad=squad,
        deps=deps,
        model_used=LLM_JIRA_MODEL,
    )


def chat(req: ChatRequest) -> ChatResponse:
    """Stateless product discovery coach: one turn. Frontend sends full message history."""
    from app.main import openai_client

    messages: list[dict[str, str]] = [
        {"role": "system", "content": CHAT_SYSTEM},
    ]
    if (req.idea_context or "").strip():
        messages.append({
            "role": "user",
            "content": f"Context before starting: {req.idea_context.strip()}",
        })
    for m in req.messages:
        messages.append({"role": m.role, "content": m.content})

    resp = openai_client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=CHAT_TEMPERATURE,
        max_tokens=CHAT_MAX_TOKENS,
        messages=messages,
    )
    content = (resp.choices[0].message.content or "").strip()
    reply = content
    is_ready = False
    raw_json = _extract_json(content)
    if raw_json:
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict):
                reply = str(data.get("reply", reply)).strip() or content
                is_ready = bool(data.get("is_ready_to_summarise", False))
        except json.JSONDecodeError:
            pass
    turn_count = len(req.messages) + 1
    return ChatResponse(
        reply=reply,
        is_ready_to_summarise=is_ready,
        turn_count=turn_count,
        model_used=CHAT_MODEL,
    )


def summarise(req: SummariseRequest) -> SummariseResponse:
    """Distill full conversation into structured product brief for /llm/features and feature scoping."""
    from app.main import openai_client

    lines = []
    for m in req.messages:
        prefix = "User:" if m.role == "user" else "Coach:"
        lines.append(f"{prefix} {m.content}")
    messages_formatted = "\n\n".join(lines)

    user_msg = SUMMARISE_USER_TEMPLATE.format(messages_formatted=messages_formatted)
    resp = openai_client.chat.completions.create(
        model=SUMMARISE_MODEL,
        temperature=SUMMARISE_TEMPERATURE,
        max_tokens=SUMMARISE_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SUMMARISE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM did not return a JSON object")

    idea = str(data.get("idea", "")).strip() or "Product idea."
    idea_summary = str(data.get("idea_summary", "")).strip() or idea
    detailed_description = str(data.get("detailed_description", "")).strip() or idea

    inferred_raw = data.get("inferred_features")
    if not isinstance(inferred_raw, list):
        inferred_raw = []
    inferred_features: list[FeatureDescription] = []
    for i, item in enumerate(inferred_raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip() or f"Feature {i + 1}"
        description = str(item.get("description", "")).strip() or ""
        inferred_features.append(FeatureDescription(title=title, description=description))

    use_cases_raw = data.get("use_cases")
    if not isinstance(use_cases_raw, list):
        use_cases_raw = []
    use_cases: list[UseCaseDescription] = []
    for u in use_cases_raw:
        if not isinstance(u, dict):
            continue
        use_cases.append(
            UseCaseDescription(
                persona=str(u.get("persona", "")).strip() or "User",
                goal=str(u.get("goal", "")).strip() or "",
                workflow=str(u.get("workflow", "")).strip() or "",
            )
        )

    constraints = data.get("constraints")
    if not isinstance(constraints, list):
        constraints = []
    constraints = [str(c).strip() for c in constraints if c]

    open_questions = data.get("open_questions")
    if not isinstance(open_questions, list):
        open_questions = []
    open_questions = [str(q).strip() for q in open_questions if q]

    return SummariseResponse(
        idea=idea,
        idea_summary=idea_summary,
        detailed_description=detailed_description,
        inferred_features=inferred_features,
        use_cases=use_cases,
        constraints=constraints,
        open_questions=open_questions,
        model_used=SUMMARISE_MODEL,
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
