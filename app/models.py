"""
Phase 6: Pydantic request/response schemas.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    """Request body for POST /search."""

    query: str = Field(..., min_length=1, description="Natural language description of the API needed.")


class APIResult(BaseModel):
    """One API match (or near-match) with optional enhancement suggestion."""

    api_id: str = Field(..., description="Unique API identifier.")
    name: str = Field(..., description="API name.")
    description: str = Field(..., description="API description.")
    input: dict[str, Any] = Field(default_factory=dict, description="Input parameters schema.")
    output: dict[str, Any] = Field(default_factory=dict, description="Output schema.")
    score: float = Field(..., ge=0, le=1, description="Similarity score in [0, 1].")
    match_type: str = Field(..., description="One of: direct, closest, no_match.")
    enhancement_suggestion: Optional[str] = Field(
        default=None,
        description="LLM suggestion when match_type is 'closest' (what it covers, what's missing, enhancements).",
    )
    method: Optional[str] = Field(default=None, description="HTTP method (GET, POST, etc.).")
    endpoint: Optional[str] = Field(default=None, description="API endpoint path.")
    tags: Optional[list[str]] = Field(default=None, description="Tags for the API.")


class SearchResponse(BaseModel):
    """Response for POST /search."""

    results: list[APIResult] = Field(..., description="Ordered list of API results (top 5).")


# --- RAG Pipeline: POST /api/rag/lookup ---
class RAGContext(BaseModel):
    """Context from /llm/describe for semantic lookup."""

    product_idea: Optional[str] = None
    persona: Optional[str] = None
    journey: Optional[str] = None
    step_label: Optional[str] = None


class RAGExpectedIO(BaseModel):
    """Expected input/output schemas for the capability."""

    input_schema: Optional[str] = None
    output_schema: Optional[str] = None


class RAGLookupRequest(BaseModel):
    """Request body for POST /api/rag/lookup."""

    query_key: str = Field(..., description="Key identifying the query.")
    description: str = Field(..., min_length=1, description="Semantic description of the API/capability needed.")
    context: Optional[RAGContext] = None
    expected_io: Optional[RAGExpectedIO] = None
    top_k: int = Field(default=3, ge=1, le=20, description="Number of top matches to consider.")


class RAGMatchedAPI(BaseModel):
    """Best-matched API in RAG lookup response. Maps from catalog (path→endpoint, owner→author, readiness→status)."""

    name: str = ""
    endpoint: str = Field(..., description="Path or URL (from catalog path/url).")
    method: Optional[str] = None
    team: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None
    desc: Optional[str] = None
    contract: Optional[str] = None
    sla: Optional[str] = None
    latency: Optional[str] = None
    calls: Optional[Any] = None


class RAGLookupResponse(BaseModel):
    """Response for POST /api/rag/lookup."""

    query_key: str
    match_status: Literal["exact", "partial", "none"]
    confidence_score: float = Field(..., ge=0, le=1)
    matched_api: Optional[RAGMatchedAPI] = None
    enhancements: list[str] = Field(default_factory=list)
    gap_summary: Optional[str] = None
    build_required: bool = True


# --- IdeaGPT: Idea → Features ---
class IdeaFeaturesRequest(BaseModel):
    idea: str = Field(..., min_length=1)


class FeatureItem(BaseModel):
    id: str
    icon: str
    title: str
    desc: str
    on: bool = True


class IdeaFeaturesResponse(BaseModel):
    features: list[FeatureItem]


# --- POST /llm/features (gpt-4o, JSON mode) ---
class FeaturesRequest(BaseModel):
    """Request body for POST /llm/features."""

    idea: str = Field(..., min_length=10, description="User's raw product idea text.")
    max_features: int = Field(default=12, description="Max features to extract.")
    min_features: int = Field(default=8, description="Min features to extract.")

    @model_validator(mode="after")
    def min_max_order(self):
        if self.min_features > self.max_features:
            raise ValueError("min_features must be <= max_features")
        return self


class FeaturesResponse(BaseModel):
    """Response for POST /llm/features."""

    features: list[FeatureItem] = Field(..., description="8-12 feature items.")
    idea_summary: str = Field(..., description="One sentence LLM summary of the idea.")
    model_used: str = Field(..., description="Model echoed back, e.g. 'gpt-4o'.")


# --- IdeaGPT: Features → Personas & Journeys ---
class IdeaPersonasRequest(BaseModel):
    idea: str = Field(..., min_length=1)
    feature_ids: list[str] = Field(default_factory=list)


class JourneyStep(BaseModel):
    id: str
    label: str
    icon: str
    search_text: str = Field(..., description="Semantic description for API search.")


class Journey(BaseModel):
    id: str
    title: str
    steps: list[JourneyStep]


class PersonaItem(BaseModel):
    id: str
    label: str
    icon: str
    color: str
    color_bg: str = Field(..., alias="colorBg")
    color_border: str = Field(..., alias="colorBorder")
    desc: str
    journeys: list[Journey]

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class IdeaPersonasResponse(BaseModel):
    personas: list[PersonaItem]


# --- POST /llm/suggest-personas, /llm/generate-journeys, /llm/describe ---
PersonaColorLiteral = Literal["blue", "green", "purple", "amber"]


class SuggestPersonasRequest(BaseModel):
    """Request body for POST /llm/suggest-personas."""

    idea: str = Field(..., min_length=1, description="The original product idea.")
    idea_summary: str = Field(..., description="From FeaturesResponse.idea_summary.")
    selected_features: list[str] = Field(
        default_factory=list,
        description="Titles of features where on=True.",
    )
    max_personas: int = Field(default=4, description="How many personas to suggest.")
    min_personas: int = Field(default=2, description="Minimum personas to suggest.")

    @model_validator(mode="after")
    def min_max_order(self):
        if self.min_personas > self.max_personas:
            raise ValueError("min_personas must be <= max_personas")
        return self


class PersonaSuggestion(BaseModel):
    """One suggested persona from POST /llm/suggest-personas."""

    id: str = Field(..., description="snake_case unique id, e.g. 'guest_shopper'")
    label: str = Field(..., description="Display name, e.g. 'Guest Shopper'")
    icon: str = Field(..., description="Single emoji.")
    desc: str = Field(..., description="One sentence describing this persona.")
    color: PersonaColorLiteral = Field(
        ..., description="One of blue, green, purple, amber."
    )
    rationale: str = Field(
        ..., description="Why this persona is relevant to the idea."
    )
    suggested_journeys: list[str] = Field(
        default_factory=list,
        description="2-3 journey names as hints for user.",
    )
    is_primary: bool = Field(
        default=False,
        description="True if this is a core/critical persona.",
    )


class SuggestPersonasResponse(BaseModel):
    """Response for POST /llm/suggest-personas."""

    personas: list[PersonaSuggestion] = Field(..., description="Suggested personas.")
    model_used: str = Field(..., description="Model echoed back, e.g. 'gpt-4o'.")


class ConfirmedPersona(BaseModel):
    """User-confirmed persona passed to POST /llm/generate-journeys."""

    id: str = Field(..., description="From PersonaSuggestion, possibly user-edited.")
    label: str = Field(..., description="Possibly user-edited.")
    icon: str = Field(..., description="Possibly user-edited.")
    desc: str = Field(..., description="Possibly user-edited.")
    color: str = Field(..., description="User may keep or change.")
    suggested_journeys: list[str] = Field(
        default_factory=list,
        description="From LLM suggestion (hints for journey gen).",
    )


class GenerateJourneysRequest(BaseModel):
    """Request body for POST /llm/generate-journeys."""

    idea: str = Field(..., description="Product idea.")
    selected_features: list[str] = Field(
        default_factory=list,
        description="Feature titles where on=True.",
    )
    confirmed_personas: list[ConfirmedPersona] = Field(
        ...,
        description="User-confirmed personas including edits.",
    )
    steps_per_journey: int = Field(
        default=5,
        ge=4,
        le=7,
        description="Target steps per journey.",
    )
    journeys_per_persona: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Target journeys per persona.",
    )


class LLMJourneyStep(BaseModel):
    """One step in a journey from POST /llm/generate-journeys; api = RAG query key."""

    id: str = Field(..., description="Unique, e.g. 'step_guest_browse_1'")
    label: str = Field(..., description="2-3 word step label.")
    icon: str = Field(..., description="Single emoji.")
    api: str = Field(
        ...,
        description="snake_case capability key for RAG lookup; noun not verb-phrase.",
    )


class LLMJourney(BaseModel):
    """One journey from POST /llm/generate-journeys (4-7 steps)."""

    id: str = Field(..., description="Journey id.")
    title: str = Field(..., description="3-5 word journey name.")
    steps: list[LLMJourneyStep] = Field(..., description="4-7 steps.")


class PersonaWithJourneys(BaseModel):
    """Persona with generated journeys; response shape for generate-journeys."""

    id: str = Field(..., description="Matches ConfirmedPersona.id.")
    journeys: list[LLMJourney] = Field(..., description="Generated journeys.")


class GenerateJourneysResponse(BaseModel):
    """Response for POST /llm/generate-journeys."""

    personas: list[PersonaWithJourneys] = Field(
        ..., description="Personas with their journeys."
    )
    unique_api_keys: list[str] = Field(
        ...,
        description="Deduplicated list of all step.api keys for batch /llm/describe.",
    )
    model_used: str = Field(..., description="Model echoed back, e.g. 'gpt-4o'.")


class DescribeRequest(BaseModel):
    """Request body for POST /llm/describe (one call per unique api_key)."""

    api_key: str = Field(
        ...,
        description="The snake_case api key from journey step.",
    )
    idea: str = Field(..., description="Product idea for context.")
    step_label: str = Field(..., description="Step label for richer context.")
    persona_label: str = Field(
        ..., description="The persona this step belongs to."
    )
    journey_title: str = Field(
        ..., description="The journey this step belongs to."
    )


class DescribeResponse(BaseModel):
    """Response for POST /llm/describe; feeds RAG lookup description."""

    api_key: str = Field(..., description="Echoed back for correlation.")
    description: str = Field(
        ...,
        description="1-2 sentence capability description for semantic RAG search.",
    )
    input_schema: str = Field(
        ..., description="Brief description of key input fields."
    )
    output_schema: str = Field(
        ..., description="Brief description of key output fields."
    )


# --- IdeaGPT: Jira stories for missing steps ---
class MissingStep(BaseModel):
    label: str
    search_text: str = ""
    journey_title: str = ""
    persona_label: str = ""


class JiraGenerateRequest(BaseModel):
    missing_steps: list[MissingStep]


class JiraStory(BaseModel):
    title: str
    epic: str
    priority: str
    story: str
    acceptance: list[str]
    sp: int
    days: int
    sprint: str
    squad: str
    deps: list[str] = Field(default_factory=list)


class JiraGenerateResponse(BaseModel):
    stories: list[JiraStory]
