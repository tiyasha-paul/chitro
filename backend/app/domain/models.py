import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import PostStatus


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(String, nullable=False)
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brief_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    previous_insights: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    brief_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["PlatformPost"]] = relationship(back_populates="campaign")
    insights: Mapped[list["Insight"]] = relationship(back_populates="campaign")


class PlatformPost(Base):
    __tablename__ = "platform_posts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default=PostStatus.DRAFT.value)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_spec: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    hashtags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    cta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_errors: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_post_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_result: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    generation_attempt: Mapped[int] = mapped_column(Integer, default=0)
    generation_history: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    campaign: Mapped["Campaign"] = relationship(back_populates="posts")
    metrics: Mapped[list["MetricSnapshot"]] = relationship(back_populates="post")


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    platform_post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_posts.id"), nullable=False)
    impressions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reach: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    likes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saves: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clicks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["PlatformPost"] = relationship(back_populates="metrics")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped["Campaign"] = relationship(back_populates="insights")
