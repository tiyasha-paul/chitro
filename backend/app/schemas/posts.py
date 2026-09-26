"""Post and workflow API request and response schemas."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import Language, Platform, PostStatus


class GeneratePostRequest(BaseModel):
    """Payload to request content generation for a specific platform and language."""

    platform: Platform = Field(default=Platform.INSTAGRAM, description="Target platform")
    language: Language = Field(default=Language.BENGALI, description="Content language")


class RejectPostRequest(BaseModel):
    """Payload to reject a pending post with human feedback."""

    reason: str = Field(..., min_length=1, description="Human rejection reason")


class SchedulePostRequest(BaseModel):
    """Payload to schedule an approved post for publication."""

    scheduled_at: datetime = Field(..., description="Target scheduled timestamp (UTC)")

    @field_validator("scheduled_at")
    @classmethod
    def validate_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("scheduled_at must be in the future")
        return v


class GenerationHistoryEntry(BaseModel):
    """Audit snapshot of a single generation attempt."""

    attempt: int
    status: str
    caption: str | None = None
    hook: str | None = None
    hashtags: list[str] | None = None
    cta: str | None = None
    media_spec: dict[str, Any] | None = None
    validation_errors: list[dict[str, Any]] | None = None
    rejection_reason: str | None = None
    timestamp: str | None = None


class PlatformPostResponse(BaseModel):
    """Structured response for a platform post and its lifecycle state."""

    id: uuid.UUID
    campaign_id: uuid.UUID
    platform: Platform
    language: Language
    status: PostStatus
    caption: str | None = None
    hook: str | None = None
    hashtags: list[str] | None = None
    cta: str | None = None
    media_spec: dict[str, Any] | None = None
    validation_errors: list[dict[str, Any]] | None = None
    rejection_reason: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    published_post_id: str | None = None
    publish_result: dict[str, Any] | None = None
    generation_attempt: int = 0
    generation_history: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
