"""Channel publishing adapter protocol and data structures."""

import uuid
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class PublishPayload(BaseModel):
    """Normalized payload delivered to a channel adapter for publishing."""

    post_id: uuid.UUID
    caption: str = Field(..., description="Post caption text")
    media_spec: dict[str, Any] | None = Field(default=None, description="Media specifications")
    hashtags: list[str] | None = Field(default=None, description="Hashtags list")
    cta: str | None = Field(default=None, description="Call to action")
    platform: str = Field(default="instagram", description="Target platform identifier")


class PublishResult(BaseModel):
    """Structured result returned by a channel adapter upon publication."""

    provider: str = Field(..., description="Adapter/Provider identifier, e.g. 'mock_instagram'")
    external_post_id: str = Field(..., description="Unique ID returned by the channel platform")
    published_at: datetime = Field(..., description="Timestamp of publication")
    url: str = Field(..., description="Public or mock URL where the post is viewable")
    status: str = Field(default="published", description="Publishing status result")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional channel-specific metadata")


class ChannelAdapterError(Exception):
    """Raised when publishing through a channel adapter fails."""

    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


@runtime_checkable
class ChannelAdapter(Protocol):
    """Protocol defining the interface for channel publishing adapters."""

    async def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish content to the channel and return the structured result."""
        ...
