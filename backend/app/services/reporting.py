"""Reporting service orchestrating context construction, AI synthesis, and deterministic citation validation."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import build_reporting_prompt, build_reporting_system_instruction
from app.ai.provider import LLMProvider
from app.domain.enums import PostStatus
from app.domain.exceptions import CitationValidationError, ResourceNotFoundError
from app.domain.models import Campaign, Insight, MetricSnapshot, PlatformPost
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
)

RATE_OR_RATIO_METRICS: set[str] = {"engagement_rate"}


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ReportingService:
    """Service producing evidence-backed weekly performance reports with deterministic citation verification."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate_weekly_report(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> PerformanceReport:
        """Construct structured report context, invoke LLM synthesis, and validate citations."""
        # 1. Retrieve campaign
        c_stmt = select(Campaign).where(Campaign.id == campaign_id)
        c_res = await db.execute(c_stmt)
        campaign = c_res.scalar_one_or_none()

        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))

        # 2. Establish reporting window with timezone awareness
        now = datetime.now(timezone.utc)
        period_end = ensure_utc(end or now)
        period_start = ensure_utc(start or (period_end - timedelta(days=7)))

        # 3. Retrieve published posts within the reporting period
        posts_stmt = (
            select(PlatformPost)
            .where(
                PlatformPost.campaign_id == campaign_id,
                PlatformPost.status == PostStatus.PUBLISHED.value,
                PlatformPost.published_at.is_not(None),
                PlatformPost.published_at >= period_start,
                PlatformPost.published_at <= period_end,
            )
            .options(selectinload(PlatformPost.metrics))
        )
        posts_res = await db.execute(posts_stmt)
        published_posts = list(posts_res.scalars().all())

        # Filter snapshots to only those within the requested period
        period_snapshots: list[MetricSnapshot] = []
        filtered_snapshots_by_post: dict[uuid.UUID, list[MetricSnapshot]] = {}
        for p in published_posts:
            post_snaps = [
                s
                for s in p.metrics
                if s.captured_at is not None
                and period_start <= ensure_utc(s.captured_at) <= period_end
            ]
            filtered_snapshots_by_post[p.id] = post_snaps
            period_snapshots.extend(post_snaps)

        # 4. Retrieve stored insights
        ins_stmt = (
            select(Insight)
            .where(Insight.campaign_id == campaign_id)
            .order_by(Insight.created_at.asc())
        )
        ins_res = await db.execute(ins_stmt)
        insights = list(ins_res.scalars().all())

        # 5. Handle insufficient evidence gracefully without LLM call
        if not published_posts or not period_snapshots:
            return PerformanceReport(
                title=f"Weekly Performance Report: {campaign.name}",
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                executive_summary=(
                    f"Insufficient performance metrics recorded for campaign '{campaign.name}' during the selected period. "
                    f"Published posts: {len(published_posts)}, Recorded metric snapshots: {len(period_snapshots)}. "
                    "No evidence-backed claims or recommendations can be formulated at this time."
                ),
                sections=[
                    ReportSection(
                        heading="Data Availability Status",
                        summary="No performance metric snapshots are currently recorded for published posts in this campaign.",
                        claims=[],
                    )
                ],
                recommendations=[],
            )

        # 6. Compute deterministic aggregates from filtered snapshots
        latest_snaps = []
        for p in published_posts:
            p_snaps = filtered_snapshots_by_post.get(p.id, [])
            if p_snaps:
                latest_snaps.append(max(p_snaps, key=lambda s: ensure_utc(s.captured_at)))

        total_reach = sum((s.reach or 0) for s in latest_snaps)
        total_impressions = sum((s.impressions or 0) for s in latest_snaps)
        er_rates = [s.engagement_rate for s in latest_snaps if s.engagement_rate is not None]
        avg_er = round(sum(er_rates) / len(er_rates), 4) if er_rates else None

        # 7. Construct ReportContext
        post_contexts = [
            ReportPostContext(
                post_id=str(p.id),
                platform=p.platform,
                language=p.language,
                published_at=ensure_utc(p.published_at).isoformat() if p.published_at else "",
                content_summary=p.caption[:120] if p.caption else "",
            )
            for p in published_posts
        ]

        metric_contexts = [
            ReportMetricSnapshot(
                post_id=str(p.id),
                platform=p.platform,
                snapshot_id=str(s.id),
                captured_at=ensure_utc(s.captured_at).isoformat(),
                metrics={
                    "reach": s.reach,
                    "impressions": s.impressions,
                    "likes": s.likes,
                    "comments": s.comments,
                    "shares": s.shares,
                    "saves": s.saves,
                    "clicks": s.clicks,
                    "engagement_rate": s.engagement_rate,
                },
            )
            for p in published_posts
            for s in filtered_snapshots_by_post.get(p.id, [])
        ]

        insight_contexts = [
            ReportInsightContext(
                insight_id=str(ins.id),
                text=ins.summary,
                evidence=ins.evidence if isinstance(ins.evidence, list) else [ins.evidence],
            )
            for ins in insights
        ]

        report_context = ReportContext(
            campaign=CampaignContext(
                campaign_id=str(campaign.id),
                title=campaign.name,
                objective=campaign.objective,
                language="bn",
            ),
            period=ReportPeriod(
                start=period_start.isoformat(),
                end=period_end.isoformat(),
            ),
            published_posts=post_contexts,
            metrics=metric_contexts,
            insights=insight_contexts,
            deterministic_aggregates={
                "total_published_posts": len(published_posts),
                "total_reach": total_reach,
                "total_impressions": total_impressions,
                "average_engagement_rate": avg_er,
                "snapshot_count": len(period_snapshots),
            },
        )

        # 8. Invoke LLM via provider abstraction
        prompt = build_reporting_prompt(report_context)
        system_instruction = build_reporting_system_instruction()

        raw_report = await self._provider.generate_structured(
            prompt=prompt,
            system_instruction=system_instruction,
            output_schema=PerformanceReport,
        )

        # 9. Deterministic Citation Validation
        self.validate_citations(report=raw_report, context=report_context)

        return raw_report

    def validate_citations(
        self,
        report: PerformanceReport,
        context: ReportContext,
    ) -> None:
        """Deterministically verify that every factual claim cites real, matching data.

        Enforces:
        1. post_id must exist in context.
        2. snapshot_id must exist in context.
        3. snapshot_id must belong to post_id.
        4. metric_field must exist in the cited snapshot.
        5. Quantitative claim value must match the cited metric value.
           Count metrics require direct equality subject to floating point precision.
           Rate/ratio metrics (e.g. engagement_rate) permit direct ratio or percentage form.
        6. Recommendations must be grounded in valid claim IDs.

        Raises:
            CitationValidationError: if any validation rule is violated.
        """
        valid_post_ids = {p.post_id for p in context.published_posts}
        snapshots_by_id = {m.snapshot_id: m for m in context.metrics}

        known_claim_ids = set()

        for section in report.sections:
            for claim in section.claims:
                known_claim_ids.add(claim.claim_id)

                if not claim.citations:
                    raise CitationValidationError(
                        f"Claim '{claim.claim_id}' has no citations. All factual performance claims must be cited."
                    )

                for citation in claim.citations:
                    # 1. Post existence
                    if citation.post_id not in valid_post_ids:
                        raise CitationValidationError(
                            f"Citation references unknown post_id '{citation.post_id}'."
                        )

                    # 2. Snapshot existence
                    if citation.snapshot_id:
                        snap_record = snapshots_by_id.get(citation.snapshot_id)
                        if snap_record is None:
                            raise CitationValidationError(
                                f"Citation references unknown snapshot_id '{citation.snapshot_id}'."
                            )

                        # 3. Snapshot/post relationship
                        if snap_record.post_id != citation.post_id:
                            raise CitationValidationError(
                                f"Snapshot '{citation.snapshot_id}' belongs to post '{snap_record.post_id}', not cited post '{citation.post_id}'."
                            )

                        # 4. Metric field existence
                        if citation.metric_field not in snap_record.metrics:
                            raise CitationValidationError(
                                f"Metric field '{citation.metric_field}' not found in snapshot '{citation.snapshot_id}'."
                            )

                        actual_val = snap_record.metrics[citation.metric_field]
                        if actual_val is None:
                            raise CitationValidationError(
                                f"Metric field '{citation.metric_field}' in snapshot '{citation.snapshot_id}' has no value (None)."
                            )

                        # 5. Numerical Claim Value Match
                        if claim.value is not None:
                            val_float = float(claim.value)
                            metric_float = float(actual_val)

                            diff_direct = abs(val_float - metric_float)

                            if citation.metric_field in RATE_OR_RATIO_METRICS:
                                diff_pct1 = abs(val_float / 100.0 - metric_float)
                                diff_pct2 = abs(val_float - metric_float * 100.0)
                                min_diff = min(diff_direct, diff_pct1, diff_pct2)
                            else:
                                min_diff = diff_direct

                            if min_diff > 0.01:
                                raise CitationValidationError(
                                    f"Claim value {claim.value} does not match cited metric '{citation.metric_field}' value {actual_val} in snapshot '{citation.snapshot_id}'."
                                )

        # 6. Recommendation grounding validation
        for rec in report.recommendations:
            for claim_ref in rec.based_on_claim_ids:
                if claim_ref not in known_claim_ids:
                    raise CitationValidationError(
                        f"Recommendation '{rec.recommendation_id}' references unknown claim_id '{claim_ref}'."
                    )
