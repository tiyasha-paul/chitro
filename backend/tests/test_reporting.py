"""Comprehensive tests for Milestone 7: Evidence-Backed AI Performance Report.

Covers:
1. Deterministic Citation Validation:
   - Valid citations match exact context, metrics, and quantitative values.
   - Percentage conversion tolerance strictly for rate/ratio fields (engagement_rate).
   - Count metrics (likes, reach, impressions, comments, shares, saves, clicks) strictly reject percentage scaling.
   - Unknown post_id rejection.
   - Unknown snapshot_id rejection.
   - Snapshot belonging to different post rejection.
   - Non-existent metric field rejection.
   - Metric field with None value rejection.
   - Claim missing citations rejection.
   - Numerical value mismatch rejection.
   - Recommendation referencing unknown claim_id rejection.

2. Reporting Service Logic & Period Filtering:
   - Campaign not found raises ResourceNotFoundError.
   - Graceful handling when campaign has 0 published posts (no LLM call, empty claims).
   - Graceful handling when campaign has 0 metric snapshots (no LLM call, empty claims).
   - Published posts inside requested period are included.
   - Published posts before period_start are excluded.
   - Published posts after period_end are excluded.
   - Snapshots outside requested period are excluded.
   - Snapshots inside requested period are included.
   - Aggregation computation (total reach, impressions, average engagement rate).
   - Context building includes posts, metrics, aggregates, and prior insights.
   - LLM generation + citation validation pipeline.

3. Narrative Citation Prompt Contract:
   - System instruction mandates synthesis only in executive_summary and section.summary.
   - System instruction strictly forbids specific numeric metrics in summary fields.
   - Mandatory placement of all numeric factual claims in claims[].

4. HTTP API (POST /api/campaigns/{campaign_id}/reports/weekly):
   - 200 OK: Valid report returned.
   - 200 OK: Graceful empty report when no metrics.
   - 200 OK: Custom start/end time window.
   - 404 Not Found: Non-existent campaign.
   - 502 Bad Gateway: LLM hallucination / citation validation failure.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.adapters import MockInstagramAdapter
from app.ai.prompts import build_reporting_system_instruction
from app.ai.provider import LLMProvider
from app.api.deps import get_channel_adapter, get_llm_provider
from app.database import async_session_maker
from app.domain.enums import PostStatus
from app.domain.exceptions import CitationValidationError, ResourceNotFoundError
from app.domain.models import Campaign, Insight, MetricSnapshot, PlatformPost
from app.main import app
from app.schemas.reports import (
    CampaignContext,
    Citation,
    PerformanceReport,
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
from app.services.reporting import ReportingService
from app.services.auth import AuthService, create_access_token

T = TypeVar("T", bound=BaseModel)


# --- Test Fakes & Helpers ---

class MockReportingLLMProvider(LLMProvider):
    """Mock LLM Provider that returns a configured PerformanceReport or captures the prompt."""

    def __init__(self, report_to_return: PerformanceReport | None = None) -> None:
        self.report_to_return = report_to_return
        self.last_prompt: str | None = None
        self.last_system_instruction: str | None = None
        self.call_count: int = 0

    async def generate_structured(
        self,
        *,
        prompt: str,
        system_instruction: str,
        output_schema: type[T],
        temperature: float = 0.8,
    ) -> T:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        if self.report_to_return is not None:
            return self.report_to_return  # type: ignore[return-value]
        raise RuntimeError("No report configured for MockReportingLLMProvider")


@pytest.fixture
def mock_adapter():
    adapter = MockInstagramAdapter()
    app.dependency_overrides[get_channel_adapter] = lambda: adapter
    yield adapter
    app.dependency_overrides.pop(get_channel_adapter, None)


@pytest_asyncio.fixture
async def client(mock_adapter):
    async with async_session_maker() as db:
        user, workspace = await AuthService().register_user(
            db,
            email=f"reporting-api-{uuid.uuid4().hex}@example.com",
            password="secure-password",
            display_name="Reporting API",
        )
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {create_access_token(user.id)}",
            "X-Workspace-ID": str(workspace.id),
        },
    ) as c:
        yield c


def build_sample_report_context(
    post_id: str = "post-1",
    snapshot_id: str = "snap-1",
    reach: int = 15000,
    impressions: int = 22000,
    engagement_rate: float = 0.0825,
) -> ReportContext:
    """Helper creating a valid ReportContext for unit testing citation validation."""
    return ReportContext(
        campaign=CampaignContext(
            campaign_id="camp-1",
            title="Nikhoj Launch",
            objective="Hype teaser",
            language="bn",
        ),
        period=ReportPeriod(
            start="2026-09-01T00:00:00Z",
            end="2026-09-08T00:00:00Z",
        ),
        published_posts=[
            ReportPostContext(
                post_id=post_id,
                platform="instagram",
                language="bn",
                published_at="2026-09-02T10:00:00Z",
                content_summary="রহস্যে ঘেরা নতুন পর্ব...",
            )
        ],
        metrics=[
            ReportMetricSnapshot(
                post_id=post_id,
                platform="instagram",
                snapshot_id=snapshot_id,
                captured_at="2026-09-03T10:00:00Z",
                metrics={
                    "reach": reach,
                    "impressions": impressions,
                    "likes": 1200,
                    "comments": 150,
                    "shares": 80,
                    "saves": 40,
                    "clicks": 300,
                    "engagement_rate": engagement_rate,
                },
            )
        ],
        insights=[
            ReportInsightContext(
                insight_id="ins-1",
                text="Night-time thriller hooks outperformed daytime posts.",
                evidence=[{"metric": "engagement_rate", "value": 0.0825}],
            )
        ],
        deterministic_aggregates={
            "total_published_posts": 1,
            "total_reach": reach,
            "total_impressions": impressions,
            "average_engagement_rate": engagement_rate,
            "snapshot_count": 1,
        },
    )


# =====================================================================
# 1. Deterministic Citation Validation Tests
# =====================================================================

def test_validate_citations_success():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", reach=15000)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Strong performance on Instagram.",
        sections=[
            ReportSection(
                heading="Reach and Impressions",
                summary="Reach surpassed targets.",
                claims=[
                    ReportClaim(
                        claim_id="claim_reach",
                        text="Post p-100 achieved a total reach of 15,000.",
                        value=15000.0,
                        unit="count",
                        metric_field="reach",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
        recommendations=[
            ReportRecommendation(
                recommendation_id="rec_1",
                text="Double down on high reach content formats.",
                based_on_claim_ids=["claim_reach"],
            )
        ],
    )

    # Should not raise
    service.validate_citations(report=report, context=context)


def test_validate_citations_engagement_rate_decimal_form():
    """engagement_rate in decimal form (0.0825) matches accurately."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", engagement_rate=0.0825)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Engagement",
                summary="Solid rate",
                claims=[
                    ReportClaim(
                        claim_id="claim_er",
                        text="Engagement rate was 0.0825.",
                        value=0.0825,
                        unit="ratio",
                        metric_field="engagement_rate",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="engagement_rate")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    service.validate_citations(report=report, context=context)


def test_validate_citations_engagement_rate_percentage_form():
    """engagement_rate in percentage form (8.25%) matches accurately via rate scaling tolerance."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", engagement_rate=0.0825)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Engagement",
                summary="High engagement rate",
                claims=[
                    ReportClaim(
                        claim_id="claim_er",
                        text="Post achieved an 8.25% engagement rate.",
                        value=8.25,
                        unit="percentage",
                        metric_field="engagement_rate",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="engagement_rate")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    service.validate_citations(report=report, context=context)


def test_validate_citations_engagement_rate_incorrect():
    """engagement_rate mismatch (e.g. 15.0% vs 8.25%) must fail."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", engagement_rate=0.0825)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Engagement",
                summary="Summary",
                claims=[
                    ReportClaim(
                        claim_id="claim_er",
                        text="Post achieved 15.0% engagement rate.",
                        value=15.0,
                        unit="percentage",
                        metric_field="engagement_rate",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="engagement_rate")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    with pytest.raises(CitationValidationError, match="does not match cited metric 'engagement_rate'"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_likes_100_vs_10000_fails():
    """Count metric 'likes' must NOT use percentage scaling: stored 100 vs claim 10000 must FAIL."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    context.metrics[0].metrics["likes"] = 100
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Likes",
                summary="Likes analysis",
                claims=[
                    ReportClaim(
                        claim_id="c_likes",
                        text="Post achieved 10,000 likes.",
                        value=10000.0,
                        metric_field="likes",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="likes")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    with pytest.raises(CitationValidationError, match="Claim value 10000.0 does not match cited metric 'likes' value 100"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_reach_5000_vs_500000_fails():
    """Count metric 'reach': stored 5000 vs claim 500000 must FAIL."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", reach=5000)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Reach",
                claims=[
                    ReportClaim(
                        claim_id="c_reach",
                        text="Post achieved 500,000 reach.",
                        value=500000.0,
                        metric_field="reach",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="reach")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    with pytest.raises(CitationValidationError, match="Claim value 500000.0 does not match cited metric 'reach' value 5000"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_impressions_10000_vs_1000000_fails():
    """Count metric 'impressions': stored 10000 vs claim 1000000 must FAIL."""
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", impressions=10000)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Impressions",
                summary="Impressions",
                claims=[
                    ReportClaim(
                        claim_id="c_imp",
                        text="Post achieved 1,000,000 impressions.",
                        value=1000000.0,
                        metric_field="impressions",
                        citations=[
                            Citation(post_id="p-100", snapshot_id="s-200", metric_field="impressions")
                        ],
                    )
                ],
            )
        ],
        recommendations=[],
    )
    with pytest.raises(CitationValidationError, match="Claim value 1000000.0 does not match cited metric 'impressions' value 10000"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_unknown_post_id():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Reach summary",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Unknown post reach",
                        citations=[
                            Citation(
                                post_id="p-999-hallucinated",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="unknown post_id 'p-999-hallucinated'"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_unknown_snapshot_id():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Reach summary",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Unknown snapshot",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-999-fake",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="unknown snapshot_id 's-999-fake'"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_snapshot_post_mismatch():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    context.published_posts.append(
        ReportPostContext(
            post_id="p-200",
            platform="instagram",
            language="bn",
            published_at="2026-09-02T10:00:00Z",
            content_summary="Second post",
        )
    )

    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Mismatch test",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Mismatched post and snapshot",
                        citations=[
                            Citation(
                                post_id="p-200",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="belongs to post 'p-100', not cited post 'p-200'"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_nonexistent_metric_field():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Invalid Metric",
                summary="Summary",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Hallucinated metric field",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-200",
                                metric_field="viral_coefficient",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="Metric field 'viral_coefficient' not found in snapshot"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_metric_field_none():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    context.metrics[0].metrics["reach"] = None
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Metric None",
                summary="Summary",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Reach is None",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="has no value"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_claim_without_citations():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200")
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Uncited Claim",
                summary="Summary",
                claims=[
                    ReportClaim(
                        claim_id="uncited_1",
                        text="Uncited claim without backing evidence.",
                        citations=[],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="Claim 'uncited_1' has no citations"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_numerical_mismatch():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", reach=15000)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Exaggerated reach",
                claims=[
                    ReportClaim(
                        claim_id="c_1",
                        text="Post achieved 45,000 reach.",
                        value=45000.0,
                        unit="count",
                        metric_field="reach",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="Claim value 45000.0 does not match cited metric 'reach' value 15000"):
        service.validate_citations(report=report, context=context)


def test_validate_citations_fails_unknown_recommendation_claim():
    context = build_sample_report_context(post_id="p-100", snapshot_id="s-200", reach=15000)
    service = ReportingService(provider=MockReportingLLMProvider())

    report = PerformanceReport(
        title="Weekly Performance",
        period_start="2026-09-01T00:00:00Z",
        period_end="2026-09-08T00:00:00Z",
        executive_summary="Summary",
        sections=[
            ReportSection(
                heading="Reach",
                summary="Reach summary",
                claims=[
                    ReportClaim(
                        claim_id="claim_reach",
                        text="Post p-100 achieved 15,000 reach.",
                        value=15000.0,
                        metric_field="reach",
                        citations=[
                            Citation(
                                post_id="p-100",
                                snapshot_id="s-200",
                                metric_field="reach",
                            )
                        ],
                    )
                ],
            )
        ],
        recommendations=[
            ReportRecommendation(
                recommendation_id="rec_1",
                text="Recommendation grounded in nonexistent claim.",
                based_on_claim_ids=["claim_nonexistent"],
            )
        ],
    )

    with pytest.raises(CitationValidationError, match="references unknown claim_id 'claim_nonexistent'"):
        service.validate_citations(report=report, context=context)


# =====================================================================
# 2. Reporting Service Logic & Period Filtering Tests
# =====================================================================

def test_reporting_system_instruction_narrative_contract():
    """Verify that system instruction explicitly enforces the narrative citation contract."""
    instruction = build_reporting_system_instruction()
    assert "ALL specific factual or quantitative assertions" in instruction
    assert "appear exclusively in the `claims[]` array" in instruction
    assert "DO NOT include specific numeric metrics, percentages" in instruction
    assert "`executive_summary` or `section.summary`" in instruction
    assert "never in summary prose" in instruction


@pytest.mark.asyncio
async def test_reporting_service_campaign_not_found():
    provider = MockReportingLLMProvider()
    service = ReportingService(provider=provider)

    async with async_session_maker() as db:
        with pytest.raises(ResourceNotFoundError):
            await service.generate_weekly_report(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_reporting_service_zero_published_posts():
    provider = MockReportingLLMProvider()
    service = ReportingService(provider=provider)

    async with async_session_maker() as db:
        camp = Campaign(name="Empty Campaign", objective="Testing zero data")
        db.add(camp)
        await db.commit()
        await db.refresh(camp)

        report = await service.generate_weekly_report(db, camp.id)

        assert report.title == f"Weekly Performance Report: {camp.name}"
        assert "Insufficient performance metrics" in report.executive_summary
        assert len(report.sections) == 1
        assert report.sections[0].heading == "Data Availability Status"
        assert len(report.recommendations) == 0
        assert provider.call_count == 0


@pytest.mark.asyncio
async def test_reporting_service_published_post_zero_snapshots():
    provider = MockReportingLLMProvider()
    service = ReportingService(provider=provider)

    async with async_session_maker() as db:
        camp = Campaign(name="Campaign Without Metrics")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Caption text",
            status=PostStatus.PUBLISHED.value,
            published_at=datetime.now(timezone.utc),
        )
        db.add(post)
        await db.commit()
        await db.refresh(camp)

        report = await service.generate_weekly_report(db, camp.id)

        assert "Insufficient performance metrics" in report.executive_summary
        assert len(report.recommendations) == 0
        assert provider.call_count == 0


@pytest.mark.asyncio
async def test_reporting_period_filtering_included_and_excluded_posts():
    """Verify published_at >= period_start and <= period_end filtering in SQL query."""
    provider = MockReportingLLMProvider()
    service = ReportingService(provider=provider)

    now = datetime.now(timezone.utc)
    t_start = now - timedelta(days=7)
    t_end = now

    async with async_session_maker() as db:
        camp = Campaign(name="Period Filter Campaign")
        db.add(camp)
        await db.flush()

        # Post 1: Before period_start -> EXCLUDED
        post_before = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Post before period",
            status=PostStatus.PUBLISHED.value,
            published_at=t_start - timedelta(days=2),
        )
        db.add(post_before)
        await db.flush()
        db.add(MetricSnapshot(platform_post_id=post_before.id, reach=1000, captured_at=t_start - timedelta(days=2)))

        # Post 2: Inside period -> INCLUDED
        post_inside = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Post inside period",
            status=PostStatus.PUBLISHED.value,
            published_at=t_start + timedelta(days=2),
        )
        db.add(post_inside)
        await db.flush()
        snap_inside = MetricSnapshot(platform_post_id=post_inside.id, reach=5000, captured_at=t_start + timedelta(days=3))
        db.add(snap_inside)

        # Post 3: After period_end -> EXCLUDED
        post_after = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Post after period",
            status=PostStatus.PUBLISHED.value,
            published_at=t_end + timedelta(days=2),
        )
        db.add(post_after)
        await db.flush()
        db.add(MetricSnapshot(platform_post_id=post_after.id, reach=2000, captured_at=t_end + timedelta(days=2)))

        await db.commit()

        # Build mock report citing only the valid post
        mock_report = PerformanceReport(
            title=f"Weekly Performance Report: {camp.name}",
            period_start=t_start.isoformat(),
            period_end=t_end.isoformat(),
            executive_summary="Summary",
            sections=[
                ReportSection(
                    heading="Performance",
                    summary="Summary",
                    claims=[
                        ReportClaim(
                            claim_id="c_reach",
                            text="Reach 5000",
                            value=5000.0,
                            metric_field="reach",
                            citations=[
                                Citation(post_id=str(post_inside.id), snapshot_id=str(snap_inside.id), metric_field="reach")
                            ],
                        )
                    ],
                )
            ],
            recommendations=[],
        )
        provider.report_to_return = mock_report

        report = await service.generate_weekly_report(db, camp.id, start=t_start, end=t_end)

        assert report.title == mock_report.title
        assert provider.call_count == 1
        # Context must contain only post_inside
        assert str(post_inside.id) in provider.last_prompt
        assert str(post_before.id) not in provider.last_prompt
        assert str(post_after.id) not in provider.last_prompt


@pytest.mark.asyncio
async def test_reporting_period_filtering_excludes_snapshots_outside_period():
    """Verify that snapshots captured outside the period window are excluded."""
    provider = MockReportingLLMProvider()
    service = ReportingService(provider=provider)

    now = datetime.now(timezone.utc)
    t_start = now - timedelta(days=7)
    t_end = now

    async with async_session_maker() as db:
        camp = Campaign(name="Snapshot Period Campaign")
        db.add(camp)
        await db.flush()

        # Post published inside period
        post = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Post with mixed snapshots",
            status=PostStatus.PUBLISHED.value,
            published_at=t_start + timedelta(days=1),
        )
        db.add(post)
        await db.flush()

        # Snapshot 1: captured before period_start -> EXCLUDED
        snap_old = MetricSnapshot(platform_post_id=post.id, reach=1000, captured_at=t_start - timedelta(days=1))
        # Snapshot 2: captured inside period -> INCLUDED
        snap_valid = MetricSnapshot(platform_post_id=post.id, reach=7000, captured_at=t_start + timedelta(days=2))
        # Snapshot 3: captured after period_end -> EXCLUDED
        snap_future = MetricSnapshot(platform_post_id=post.id, reach=9000, captured_at=t_end + timedelta(days=1))

        db.add_all([snap_old, snap_valid, snap_future])
        await db.commit()

        mock_report = PerformanceReport(
            title=f"Weekly Performance Report: {camp.name}",
            period_start=t_start.isoformat(),
            period_end=t_end.isoformat(),
            executive_summary="Summary",
            sections=[
                ReportSection(
                    heading="Performance",
                    summary="Summary",
                    claims=[
                        ReportClaim(
                            claim_id="c_reach",
                            text="Reach 7000",
                            value=7000.0,
                            metric_field="reach",
                            citations=[
                                Citation(post_id=str(post.id), snapshot_id=str(snap_valid.id), metric_field="reach")
                            ],
                        )
                    ],
                )
            ],
            recommendations=[],
        )
        provider.report_to_return = mock_report

        report = await service.generate_weekly_report(db, camp.id, start=t_start, end=t_end)

        assert report.title == mock_report.title
        assert str(snap_valid.id) in provider.last_prompt
        assert str(snap_old.id) not in provider.last_prompt
        assert str(snap_future.id) not in provider.last_prompt


@pytest.mark.asyncio
async def test_reporting_service_successful_generation_and_validation():
    now = datetime.now(timezone.utc)
    t_start = now - timedelta(days=7)
    t_end = now

    async with async_session_maker() as db:
        camp = Campaign(name="Nikhoj Launch Campaign", objective="Drive hype")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="রোমাঞ্চকর রাতের সত্য উদঘাটন",
            status=PostStatus.PUBLISHED.value,
            published_at=now - timedelta(days=2),
        )
        db.add(post)
        await db.flush()

        snap = MetricSnapshot(
            platform_post_id=post.id,
            reach=10000,
            impressions=15000,
            likes=800,
            comments=100,
            engagement_rate=0.06,
            captured_at=now - timedelta(days=1),
        )
        db.add(snap)

        ins = Insight(
            campaign_id=camp.id,
            summary="Strong audience engagement with thriller themes",
            evidence=[{"metric": "engagement_rate", "value": 0.06}],
        )
        db.add(ins)
        await db.commit()

        expected_report = PerformanceReport(
            title=f"Weekly Performance Report: {camp.name}",
            period_start=t_start.isoformat(),
            period_end=t_end.isoformat(),
            executive_summary="The campaign achieved 10,000 reach with 6% engagement.",
            sections=[
                ReportSection(
                    heading="Audience Reach",
                    summary="Detailed reach metrics",
                    claims=[
                        ReportClaim(
                            claim_id="claim_reach",
                            text="Post achieved 10,000 reach.",
                            value=10000.0,
                            metric_field="reach",
                            citations=[
                                Citation(
                                    post_id=str(post.id),
                                    snapshot_id=str(snap.id),
                                    metric_field="reach",
                                )
                            ],
                        )
                    ],
                )
            ],
            recommendations=[
                ReportRecommendation(
                    recommendation_id="rec_1",
                    text="Maintain current thriller aesthetic.",
                    based_on_claim_ids=["claim_reach"],
                )
            ],
        )

        provider = MockReportingLLMProvider(report_to_return=expected_report)
        service = ReportingService(provider=provider)

        report = await service.generate_weekly_report(db, camp.id, start=t_start, end=t_end)

        assert report.title == expected_report.title
        assert len(report.sections) == 1
        assert report.sections[0].claims[0].value == 10000.0
        assert provider.call_count == 1
        assert "total_reach" in provider.last_prompt
        assert "Nikhoj Launch Campaign" in provider.last_prompt


# =====================================================================
# 4. HTTP API Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_api_generate_weekly_report_success(client: AsyncClient):
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=5)
    end_dt = now + timedelta(days=1)

    async with async_session_maker() as db:
        camp = Campaign(
            name="API Campaign",
            objective="Testing API report",
            workspace_id=uuid.UUID(client.headers["X-Workspace-ID"]),
        )
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="হইচই অরিজিনাল",
            status=PostStatus.PUBLISHED.value,
            published_at=now - timedelta(days=2),
        )
        db.add(post)
        await db.flush()

        snap = MetricSnapshot(
            platform_post_id=post.id,
            reach=12000,
            impressions=18000,
            likes=950,
            comments=120,
            engagement_rate=0.0594,
            captured_at=now - timedelta(days=1),
        )
        db.add(snap)
        await db.commit()

        expected_report = PerformanceReport(
            title=f"Weekly Performance Report: {camp.name}",
            period_start=start_dt.isoformat(),
            period_end=end_dt.isoformat(),
            executive_summary="Solid weekly results.",
            sections=[
                ReportSection(
                    heading="Performance Overview",
                    summary="Reach reached 12,000",
                    claims=[
                        ReportClaim(
                            claim_id="c1",
                            text="Reach reached 12,000",
                            value=12000.0,
                            metric_field="reach",
                            citations=[
                                Citation(
                                    post_id=str(post.id),
                                    snapshot_id=str(snap.id),
                                    metric_field="reach",
                                )
                            ],
                        )
                    ],
                )
            ],
            recommendations=[
                ReportRecommendation(
                    recommendation_id="r1",
                    text="Scale content with similar reach.",
                    based_on_claim_ids=["c1"],
                )
            ],
        )

        mock_provider = MockReportingLLMProvider(report_to_return=expected_report)
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider

        try:
            resp = await client.post(
                f"/api/campaigns/{camp.id}/reports/weekly",
                json={
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["title"] == expected_report.title
            assert len(data["sections"]) == 1
            assert data["sections"][0]["claims"][0]["value"] == 12000.0
            assert data["sections"][0]["claims"][0]["citations"][0]["post_id"] == str(post.id)
            assert len(data["recommendations"]) == 1
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.asyncio
async def test_api_generate_weekly_report_graceful_insufficient_data(client: AsyncClient):
    async with async_session_maker() as db:
        camp = Campaign(name="No Metrics Campaign", workspace_id=uuid.UUID(client.headers["X-Workspace-ID"]))
        db.add(camp)
        await db.commit()

        resp = await client.post(f"/api/campaigns/{camp.id}/reports/weekly", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "Insufficient performance metrics" in data["executive_summary"]
        assert len(data["sections"]) == 1
        assert data["sections"][0]["heading"] == "Data Availability Status"
        assert len(data["recommendations"]) == 0


@pytest.mark.asyncio
async def test_api_generate_weekly_report_campaign_not_found(client: AsyncClient):
    random_id = uuid.uuid4()
    resp = await client.post(f"/api/campaigns/{random_id}/reports/weekly", json={})
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_api_generate_weekly_report_citation_validation_failure_returns_502(client: AsyncClient):
    now = datetime.now(timezone.utc)
    async with async_session_maker() as db:
        camp = Campaign(name="Hallucinating Campaign", workspace_id=uuid.UUID(client.headers["X-Workspace-ID"]))
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform="instagram",
            language="bn",
            caption="Post caption",
            status=PostStatus.PUBLISHED.value,
            published_at=now - timedelta(days=1),
        )
        db.add(post)
        await db.flush()

        snap = MetricSnapshot(
            platform_post_id=post.id,
            reach=5000,
            impressions=7000,
            captured_at=now,
        )
        db.add(snap)
        await db.commit()

        # LLM invents a completely fake post_id and claims 99,999 reach
        hallucinated_report = PerformanceReport(
            title="Weekly Performance",
            period_start=(now - timedelta(days=7)).isoformat(),
            period_end=now.isoformat(),
            executive_summary="Summary",
            sections=[
                ReportSection(
                    heading="Performance",
                    summary="Summary",
                    claims=[
                        ReportClaim(
                            claim_id="c1",
                            text="Massive hallucinated reach",
                            value=99999.0,
                            citations=[
                                Citation(
                                    post_id=str(uuid.uuid4()),  # Fake post ID!
                                    snapshot_id=str(snap.id),
                                    metric_field="reach",
                                )
                            ],
                        )
                    ],
                )
            ],
            recommendations=[],
        )

        mock_provider = MockReportingLLMProvider(report_to_return=hallucinated_report)
        app.dependency_overrides[get_llm_provider] = lambda: mock_provider

        try:
            resp = await client.post(f"/api/campaigns/{camp.id}/reports/weekly")
            assert resp.status_code == 502
            data = resp.json()
            assert "citation validation failed" in data["detail"].lower()
            assert "unknown post_id" in data["error"]
        finally:
            app.dependency_overrides.pop(get_llm_provider, None)
