"""
Phase 6: Pydantic request/response schemas.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


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


class SearchResponse(BaseModel):
    """Response for POST /search."""

    results: list[APIResult] = Field(..., description="Ordered list of API results (top 5).")
