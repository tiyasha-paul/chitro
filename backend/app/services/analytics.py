"""Analytics service for recording metric snapshots, cross-platform comparisons, and evidence-backed insights."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import PostStatus
from app.domain.exceptions import PostNotPublishedError, ResourceNotFoundError
from app.domain.models import Campaign, Insight, MetricSnapshot, PlatformPost
from app.schemas.analytics import (
    AnalyticsComparisonResponse,
    ComparisonPost,
    MetricSnapshotCreate,
)


class AnalyticsService:
    """Service providing deterministic metric ingestion, normalized comparisons, and traceable insights."""

    async def record_snapshot(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
        data: MetricSnapshotCreate,
    ) -> MetricSnapshot:
        """Record a structured metric snapshot for a published post.

        Enforces:
        - Post existence (ResourceNotFoundError if not found)
        - Post must be in PUBLISHED status (PostNotPublishedError if unapproved/draft/scheduled)
        - Normalization of engagement_rate if omitted and reach > 0
        - Persistence of raw metrics and timestamp
        """
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        if post.status != PostStatus.PUBLISHED.value:
            raise PostNotPublishedError(str(post_id), post.status)

        # Calculate normalized engagement rate if not explicitly supplied
        er = data.engagement_rate
        if er is None and data.reach is not None and data.reach > 0:
            interactions = (data.likes or 0) + (data.comments or 0) + (data.shares or 0) + (data.saves or 0)
            er = round(interactions / data.reach, 4)

        captured_at = data.captured_at or datetime.now(timezone.utc)
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)

        snapshot = MetricSnapshot(
            platform_post_id=post.id,
            impressions=data.impressions,
            reach=data.reach,
            likes=data.likes,
            comments=data.comments,
            shares=data.shares,
            saves=data.saves,
            clicks=data.clicks,
            engagement_rate=er,
            captured_at=captured_at,
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)
        return snapshot

    async def get_snapshots(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
    ) -> list[MetricSnapshot]:
        """Retrieve all recorded metric snapshots for a specific post in chronological order."""
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        snap_stmt = (
            select(MetricSnapshot)
            .where(MetricSnapshot.platform_post_id == post_id)
            .order_by(MetricSnapshot.captured_at.asc())
        )
        snap_res = await db.execute(snap_stmt)
        return list(snap_res.scalars().all())

    async def get_campaign_comparison(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
        window: Optional[str] = "latest",
    ) -> AnalyticsComparisonResponse:
        """Perform like-for-like comparison across published posts within a campaign.

        Normalizes derived engagement metrics while preserving raw platform counts.
        Does not produce evaluative 'winner' judgments.
        """
        c_stmt = select(Campaign).where(Campaign.id == campaign_id)
        c_res = await db.execute(c_stmt)
        campaign = c_res.scalar_one_or_none()

        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))

        posts_stmt = (
            select(PlatformPost)
            .where(
                PlatformPost.campaign_id == campaign_id,
                PlatformPost.status == PostStatus.PUBLISHED.value,
            )
            .options(selectinload(PlatformPost.metrics))
        )
        posts_res = await db.execute(posts_stmt)
        published_posts = list(posts_res.scalars().all())

        if not published_posts:
            return AnalyticsComparisonResponse(
                campaign_id=campaign_id,
                comparison_window=window or "latest",
                posts=[],
                summary="Insufficient published post metrics for comparison.",
            )

        comparison_items: list[ComparisonPost] = []
        for p in published_posts:
            snaps = sorted(p.metrics, key=lambda s: s.captured_at)
            if not snaps:
                comparison_items.append(
                    ComparisonPost(
                        post_id=p.id,
                        platform=p.platform,
                    )
                )
                continue

            # Select target snapshot based on comparison window
            if window == "24h" and p.published_at:
                target_time = p.published_at.timestamp() + 86400
                chosen = min(snaps, key=lambda s: abs(s.captured_at.timestamp() - target_time))
            else:
                chosen = snaps[-1]

            comparison_items.append(
                ComparisonPost(
                    post_id=p.id,
                    platform=p.platform,
                    reach=chosen.reach,
                    impressions=chosen.impressions,
                    likes=chosen.likes,
                    comments=chosen.comments,
                    shares=chosen.shares,
                    saves=chosen.saves,
                    clicks=chosen.clicks,
                    engagement_rate=chosen.engagement_rate,
                    snapshot_id=chosen.id,
                    captured_at=chosen.captured_at,
                )
            )

        return AnalyticsComparisonResponse(
            campaign_id=campaign_id,
            comparison_window=window or "latest",
            posts=comparison_items,
            summary=f"Compared {len(comparison_items)} published post(s) for campaign '{campaign.name}'.",
        )

    async def generate_campaign_insights(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
    ) -> list[Insight]:
        """Generate deterministic, evidence-backed insights from published post metrics.

        Enforces:
        - Traceability: every quantitative claim contains exact post ID, metric field, and snapshot ID.
        - No unsupported or speculative causal claims.
        - Persists Insight entities to database.
        - Updates Campaign.previous_insights to feed into future generation prompts.
        """
        c_stmt = select(Campaign).where(Campaign.id == campaign_id)
        c_res = await db.execute(c_stmt)
        campaign = c_res.scalar_one_or_none()

        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))

        posts_stmt = (
            select(PlatformPost)
            .where(
                PlatformPost.campaign_id == campaign_id,
                PlatformPost.status == PostStatus.PUBLISHED.value,
            )
            .options(selectinload(PlatformPost.metrics))
        )
        posts_res = await db.execute(posts_stmt)
        published_posts = list(posts_res.scalars().all())

        created_insights: list[Insight] = []

        # 1. Single Post & Snapshot Evolution Insights
        posts_with_snapshots = []
        for post in published_posts:
            snaps = sorted(post.metrics, key=lambda s: s.captured_at)
            if not snaps:
                continue
            posts_with_snapshots.append((post, snaps))

            latest = snaps[-1]
            post_short_id = post.id.hex[:8]

            # Insight Type 1: Standalone post performance snapshot
            if latest.engagement_rate is not None:
                er_pct = round(latest.engagement_rate * 100, 2)
                reach_val = latest.reach or 0
                summary = (
                    f"Post '{post_short_id}' on {post.platform} recorded an engagement rate of "
                    f"{er_pct}% across {reach_val:,} reach."
                )
                evidence = [
                    {
                        "post_id": str(post.id),
                        "metric_field": "engagement_rate",
                        "value": latest.engagement_rate,
                        "snapshot_id": str(latest.id),
                    },
                    {
                        "post_id": str(post.id),
                        "metric_field": "reach",
                        "value": latest.reach,
                        "snapshot_id": str(latest.id),
                    },
                ]
                created_insights.append(
                    Insight(campaign_id=campaign_id, summary=summary, evidence=evidence)
                )

            # Insight Type 2: Multi-snapshot metric evolution over time
            if len(snaps) >= 2:
                first = snaps[0]
                er_first = round((first.engagement_rate or 0.0) * 100, 2)
                er_latest = round((latest.engagement_rate or 0.0) * 100, 2)
                summary = (
                    f"Post '{post_short_id}' on {post.platform} engagement rate shifted from "
                    f"{er_first}% at snapshot {first.id.hex[:6]} to {er_latest}% at snapshot {latest.id.hex[:6]}."
                )
                evidence = [
                    {
                        "post_id": str(post.id),
                        "metric_field": "engagement_rate",
                        "value": first.engagement_rate,
                        "snapshot_id": str(first.id),
                    },
                    {
                        "post_id": str(post.id),
                        "metric_field": "engagement_rate",
                        "value": latest.engagement_rate,
                        "snapshot_id": str(latest.id),
                    },
                ]
                created_insights.append(
                    Insight(campaign_id=campaign_id, summary=summary, evidence=evidence)
                )

            # Insight Type 3: High save intent
            if latest.saves is not None and latest.saves > 0:
                summary = (
                    f"Post '{post_short_id}' on {post.platform} demonstrated high content save intent "
                    f"with {latest.saves:,} saves recorded."
                )
                evidence = [
                    {
                        "post_id": str(post.id),
                        "metric_field": "saves",
                        "value": latest.saves,
                        "snapshot_id": str(latest.id),
                    }
                ]
                created_insights.append(
                    Insight(campaign_id=campaign_id, summary=summary, evidence=evidence)
                )

        # Insight Type 4: Cross-Post / Cross-Platform comparative insight
        if len(posts_with_snapshots) >= 2:
            # Sort by reach
            posts_by_reach = sorted(
                posts_with_snapshots,
                key=lambda item: item[1][-1].reach or 0,
                reverse=True,
            )
            top_post, top_snaps = posts_by_reach[0]
            bottom_post, bottom_snaps = posts_by_reach[-1]

            top_reach = top_snaps[-1].reach or 0
            bottom_reach = bottom_snaps[-1].reach or 0

            if top_reach != bottom_reach:
                diff = top_reach - bottom_reach
                summary = (
                    f"Post '{top_post.id.hex[:8]}' on {top_post.platform} achieved {top_reach:,} reach, "
                    f"exceeding post '{bottom_post.id.hex[:8]}' on {bottom_post.platform} by {diff:,} accounts."
                )
                evidence = [
                    {
                        "post_id": str(top_post.id),
                        "metric_field": "reach",
                        "value": top_reach,
                        "snapshot_id": str(top_snaps[-1].id),
                    },
                    {
                        "post_id": str(bottom_post.id),
                        "metric_field": "reach",
                        "value": bottom_reach,
                        "snapshot_id": str(bottom_snaps[-1].id),
                    },
                ]
                created_insights.append(
                    Insight(campaign_id=campaign_id, summary=summary, evidence=evidence)
                )

        # Persist generated insights
        for ins in created_insights:
            db.add(ins)

        # Update Campaign.previous_insights with structured JSON for future generation
        now_iso = datetime.now(timezone.utc).isoformat()
        campaign.previous_insights = [
            {
                "insight_id": str(ins.id),
                "summary": ins.summary,
                "text": ins.summary,
                "evidence": ins.evidence,
                "created_at": ins.created_at.isoformat() if ins.created_at else now_iso,
            }
            for ins in created_insights
        ]

        await db.commit()
        for ins in created_insights:
            await db.refresh(ins)

        return created_insights

    async def get_campaign_insights(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
    ) -> list[Insight]:
        """Retrieve all persisted insights for a campaign."""
        c_stmt = select(Campaign).where(Campaign.id == campaign_id)
        c_res = await db.execute(c_stmt)
        campaign = c_res.scalar_one_or_none()

        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))

        stmt = (
            select(Insight)
            .where(Insight.campaign_id == campaign_id)
            .order_by(Insight.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
