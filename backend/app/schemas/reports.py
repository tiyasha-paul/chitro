"""Pydantic schemas for the Performance Report and ReportContext."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Report Input Context Schemas ---

class CampaignContext(BaseModel):
    """Context summary of the campaign."""

    campaign_id: str
    title: str
    objective: Optional[str] = None
    language: Optional[str] = None


class ReportPeriod(BaseModel):
    """Reporting period window."""

    start: str
    end: str


class ReportPostContext(BaseModel):
    """Summary of a published post within the reporting period."""

    post_id: str
    platform: str
    language: str
    published_at: str
    content_summary: str


# Alias for backward compatibility if referenced
PublishedPostContext = ReportPostContext


class ReportMetricSnapshot(BaseModel):
    """Normalized snapshot metrics for a published post."""

    post_id: str
    platform: str
    snapshot_id: str
    captured_at: str
    metrics: dict[str, Any]


# Alias for backward compatibility if referenced
MetricContext = ReportMetricSnapshot


class ReportInsightContext(BaseModel):
    """Persisted evidence-backed insight from previous evaluations."""

    insight_id: str
    text: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


# Alias for backward compatibility if referenced
InsightContext = ReportInsightContext


class DeterministicAggregates(BaseModel):
    """Pre-computed deterministic aggregations across the reporting period."""

    total_published_posts: int = 0
    total_reach: int = 0
    total_impressions: int = 0
    average_engagement_rate: Optional[float] = None
    snapshot_count: int = 0


class ReportContext(BaseModel):
    """Authoritative structured evidence context supplied to the report synthesizer."""

    campaign: CampaignContext
    period: ReportPeriod
    published_posts: list[ReportPostContext] = Field(default_factory=list)
    metrics: list[ReportMetricSnapshot] = Field(default_factory=list)
    insights: list[ReportInsightContext] = Field(default_factory=list)
    deterministic_aggregates: dict[str, Any] = Field(default_factory=dict)


# --- Report Output Schemas ---

class Citation(BaseModel):
    """Precise citation linking a factual claim to an exact post, snapshot, and metric field."""

    post_id: str = Field(..., description="ID of the cited PlatformPost")
    snapshot_id: Optional[str] = Field(None, description="ID of the cited MetricSnapshot")
    metric_field: str = Field(..., description="Field name of the cited metric, e.g. 'reach', 'engagement_rate'")


class ReportClaim(BaseModel):
    """A factual or quantitative claim accompanied by structured citations."""

    claim_id: str = Field(..., description="Unique claim identifier within the report, e.g. 'claim_1'")
    text: str = Field(..., description="The factual claim text")
    value: Optional[float] = Field(None, description="Numeric value if this claim is quantitative")
    unit: Optional[str] = Field(None, description="Unit of measurement, e.g. 'count', 'ratio', 'percentage'")
    metric_field: Optional[str] = Field(None, description="Associated metric field name")
    citations: list[Citation] = Field(default_factory=list, description="Citations grounding this claim")


class ReportSection(BaseModel):
    """A thematic section of the performance report."""

    heading: str = Field(..., description="Section title")
    summary: str = Field(..., description="High-level narrative summary of the section")
    claims: list[ReportClaim] = Field(default_factory=list, description="Specific factual claims with citations")


class ReportRecommendation(BaseModel):
    """An actionable strategic recommendation grounded in specific report claims."""

    recommendation_id: str = Field(..., description="Unique recommendation identifier, e.g. 'rec_1'")
    text: str = Field(..., description="Actionable recommendation text")
    based_on_claim_ids: list[str] = Field(
        default_factory=list,
        description="List of claim_ids from the report grounding this recommendation",
    )


class PerformanceReport(BaseModel):
    """Canonical structured weekly performance report for a campaign."""

    title: str = Field(..., description="Report title")
    period_start: str = Field(..., description="ISO timestamp of period start")
    period_end: str = Field(..., description="ISO timestamp of period end")
    executive_summary: str = Field(..., description="Executive narrative synthesis of performance")
    sections: list[ReportSection] = Field(default_factory=list, description="Structured thematic report sections")
    recommendations: list[ReportRecommendation] = Field(
        default_factory=list,
        description="Strategic recommendations grounded in cited claims",
    )


class WeeklyReportRequest(BaseModel):
    """Optional payload to specify report time bounds."""

    start: Optional[datetime] = Field(None, description="Optional start timestamp")
    end: Optional[datetime] = Field(None, description="Optional end timestamp")
