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
