"""Campaign API request and response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.briefs import ContentBrief
from app.schemas.posts import PlatformPostResponse


class CreateCampaignRequest(BaseModel):
    """Payload for creating a new campaign from a content brief."""

    name: str | None = Field(None, description="Campaign name (defaults to brief title)")
    brief: ContentBrief = Field(..., description="Structured content brief")
    previous_insights: uuid.UUID | None = Field(
        default=None,
        description="Optional source campaign whose saved insights should inform this new campaign",
    )


class CampaignResponse(BaseModel):
    """Structured response for campaign details."""

    id: uuid.UUID
    name: str
    objective: str | None = None
    target_audience: str | None = None
    brief_context: str | None = None
    brief_payload: dict[str, Any] | None = None
    previous_insights: dict[str, Any] | list[Any] | None = None
    created_at: datetime
    posts: list[PlatformPostResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
