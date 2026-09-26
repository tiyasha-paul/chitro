from app.schemas.analytics import (
    AnalyticsComparisonResponse,
    ComparisonPost,
    EvidenceItem,
    InsightResponse,
    MetricSnapshotCreate,
    MetricSnapshotResponse,
)
from app.schemas.briefs import ContentBrief
from app.schemas.campaigns import CampaignResponse, CreateCampaignRequest
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.schemas.media import MediaAssetSpec
from app.schemas.posts import (
    GenerationHistoryEntry,
    GeneratePostRequest,
    PlatformPostResponse,
    RejectPostRequest,
    SchedulePostRequest,
)

__all__ = [
    "ContentBrief",
    "GeneratedInstagramPost",
    "MediaDirection",
    "MediaAssetSpec",
    "CreateCampaignRequest",
    "CampaignResponse",
    "GeneratePostRequest",
    "RejectPostRequest",
    "SchedulePostRequest",
    "GenerationHistoryEntry",
    "PlatformPostResponse",
    "MetricSnapshotCreate",
    "MetricSnapshotResponse",
    "ComparisonPost",
    "AnalyticsComparisonResponse",
    "EvidenceItem",
    "InsightResponse",
]


from app.schemas.reports import (
    CampaignContext,
    Citation,
    DeterministicAggregates,
    InsightContext,
    MetricContext,
    PerformanceReport,
    PublishedPostContext,
    ReportClaim,
    ReportContext,
    ReportInsightContext,
    ReportMetricSnapshot,
    ReportPeriod,
    ReportPostContext,
    ReportRecommendation,
    ReportSection,
    WeeklyReportRequest,
)

__all__ += [
    "CampaignContext",
    "Citation",
    "DeterministicAggregates",
    "InsightContext",
    "MetricContext",
    "PerformanceReport",
    "PublishedPostContext",
    "ReportClaim",
    "ReportContext",
    "ReportInsightContext",
    "ReportMetricSnapshot",
    "ReportPeriod",
    "ReportPostContext",
    "ReportRecommendation",
    "ReportSection",
    "WeeklyReportRequest",
]
