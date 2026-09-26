"""Pydantic schemas for analytics snapshots, cross-platform comparisons, and evidence-backed insights."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricSnapshotCreate(BaseModel):
    """Request payload to record a metric snapshot for a published post."""

    impressions: int | None = Field(default=None, ge=0, description="Total impressions")
    reach: int | None = Field(default=None, ge=0, description="Total unique accounts reached")
    likes: int | None = Field(default=None, ge=0, description="Total likes")
    comments: int | None = Field(default=None, ge=0, description="Total comments")
    shares: int | None = Field(default=None, ge=0, description="Total shares")
    saves: int | None = Field(default=None, ge=0, description="Total saves or bookmarks")
    clicks: int | None = Field(default=None, ge=0, description="Total link or CTA clicks")
    engagement_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Explicit engagement rate (0.0 to 1.0). If omitted, derived from (likes+comments+shares+saves)/reach.",
    )
    captured_at: datetime | None = Field(
        default=None,
        description="Optional custom snapshot timestamp (defaults to current UTC time)",
    )


class MetricSnapshotResponse(BaseModel):
    """Structured response for a single metric snapshot."""

    id: uuid.UUID
    platform_post_id: uuid.UUID
    impressions: int | None = None
    reach: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    clicks: int | None = None
    engagement_rate: float | None = None
    captured_at: datetime

    model_config = {"from_attributes": True}


class ComparisonPost(BaseModel):
    """Normalized metrics for one post in a like-for-like cross-platform comparison."""

    post_id: uuid.UUID
    platform: str
    reach: int | None = None
    impressions: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    clicks: int | None = None
    engagement_rate: float | None = None
    snapshot_id: uuid.UUID | None = None
    captured_at: datetime | None = None


class AnalyticsComparisonResponse(BaseModel):
    """Structured response for cross-platform campaign comparison."""

    campaign_id: uuid.UUID
    comparison_window: str = "latest"
    posts: list[ComparisonPost] = Field(default_factory=list)
    summary: str | None = None


class EvidenceItem(BaseModel):
    """Traceable evidence unit linking an insight claim to an exact stored metric value."""

    post_id: str
    metric_field: str
    value: Any
    snapshot_id: str | None = None


class InsightResponse(BaseModel):
    """Structured response for an evidence-backed campaign insight."""

    id: uuid.UUID
    campaign_id: uuid.UUID
    summary: str
    evidence: list[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}
