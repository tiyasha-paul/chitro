"""Comprehensive tests for Milestone 6: Analytics & Evidence-Backed Cross-Platform Insights.

Covers:
1. Metric ingestion & validation (published post accepts, non-published rejects, bounds enforcement).
2. Derived metrics (deterministic engagement_rate calculation, missing metric tolerance).
3. Multiple snapshots persistence without overwriting.
4. Like-for-like campaign comparison without evaluative 'winner' fields.
5. Evidence-backed insight generation with traceable post IDs and metric values.
6. Feedback loop: storing insights on Campaign.previous_insights and passing into next generation.
7. Full HTTP API integration test.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import select

from app.adapters import MockInstagramAdapter
from app.ai.provider import LLMProvider
from app.api.deps import get_channel_adapter, get_llm_provider
from app.database import async_session_maker
from app.domain.enums import Language, Platform, PostStatus
from app.domain.exceptions import PostNotPublishedError, ResourceNotFoundError
from app.domain.models import Campaign, Insight, MetricSnapshot, PlatformPost
from app.main import app
from app.schemas.analytics import MetricSnapshotCreate
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.services.analytics import AnalyticsService

T = TypeVar("T", bound=BaseModel)


# --- Test Fakes & Fixtures ---

class SpyingLLMProvider(LLMProvider):
    """Spy LLM provider that captures the generated prompt for insight inspection."""

    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.last_system_instruction: str | None = None

    async def generate_structured(
        self,
        *,
        prompt: str,
        system_instruction: str,
        output_schema: type[T],
        temperature: float = 0.8,
    ) -> T:
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        return GeneratedInstagramPost(
            platform=Platform.INSTAGRAM,
            language=Language.BENGALI,
            hook="রহস্যে ঘেরা নতুন পর্ব—আপনি কি সত্য খুঁজছেন?",
            caption="একটি রোমাঞ্চকর রাতের সত্য উদঘাটনের গল্প। হইচই-এর অরিজিনাল নিখোঁজ দেখুন শুক্রবার।",
            hashtags=["#নিখোঁজ", "#হইচই", "#বাংলা", "#থ্রিলার", "#ড্রামা"],
            cta="এখনই হইচই অ্যাপে টিজারটি উপভোগ করুন।",
            media_direction=MediaDirection(
                description="একটি অন্ধকার ঘর এবং টেবিল ল্যাম্প।",
                style="Cinematic dark thriller",
                mood="Tense, suspenseful",
                aspect_ratio="4:5",
            ),
        )


@pytest.fixture
def spy_llm():
    provider = SpyingLLMProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_llm_provider, None)


@pytest.fixture
def mock_adapter():
    adapter = MockInstagramAdapter()
    app.dependency_overrides[get_channel_adapter] = lambda: adapter
    yield adapter
    app.dependency_overrides.pop(get_channel_adapter, None)


@pytest_asyncio.fixture
async def client(spy_llm, mock_adapter):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_brief() -> dict[str, Any]:
    return {
        "title": "নিখোঁজ (Nikhoj)",
        "genre": "Psychological Thriller",
        "language": "bn",
        "audience": "Bengali thriller fans aged 22-40",
        "objective": "Drive teaser hype",
        "key_themes": ["রহস্য", "সত্যের খোঁজ"],
        "tone": "Suspenseful",
        "cta": "হইচই অ্যাপে দেখুন",
        "release_date": "এই শুক্রবার",
    }


# =====================================================================
# 1. Metric Ingestion & Validation Tests
# =====================================================================

@pytest.mark.asyncio
async def test_published_post_accepts_metrics():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Metrics Ingestion Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
            caption="পাবলিশ করা পোস্ট",
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)

        data = MetricSnapshotCreate(
            impressions=12000,
            reach=9500,
            likes=740,
            comments=81,
            shares=120,
            saves=210,
            clicks=340,
        )
        snap = await analytics_service.record_snapshot(db, post.id, data)

        assert snap.id is not None
        assert snap.platform_post_id == post.id
        assert snap.impressions == 12000
        assert snap.reach == 9500
        assert snap.likes == 740
        assert snap.comments == 81
        assert snap.shares == 120
        assert snap.saves == 210
        assert snap.clicks == 340
        # Derived ER: (740 + 81 + 120 + 210) / 9500 = 1151 / 9500 = 0.1212
        assert snap.engagement_rate == pytest.approx(0.1212, abs=0.001)


@pytest.mark.asyncio
async def test_non_published_post_rejects_metrics():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Unpublished Camp")
        db.add(camp)
        await db.flush()

        # Post is only APPROVED, not PUBLISHED
        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.APPROVED.value,
            caption="অপ্রকাশিত পোস্ট",
        )
        db.add(post)
        await db.commit()

        data = MetricSnapshotCreate(impressions=5000, reach=4000, likes=100)
        with pytest.raises(PostNotPublishedError):
            await analytics_service.record_snapshot(db, post.id, data)


@pytest.mark.asyncio
async def test_negative_metrics_rejected_by_pydantic():
    with pytest.raises(Exception):
        MetricSnapshotCreate(impressions=-100)

    with pytest.raises(Exception):
        MetricSnapshotCreate(likes=-5)

    with pytest.raises(Exception):
        MetricSnapshotCreate(engagement_rate=1.5)  # must be <= 1.0


@pytest.mark.asyncio
async def test_multiple_snapshots_do_not_overwrite():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Multi Snapshot Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        db.add(post)
        await db.commit()

        t1 = datetime.now(timezone.utc) - timedelta(hours=24)
        t2 = datetime.now(timezone.utc)

        snap1 = await analytics_service.record_snapshot(
            db, post.id, MetricSnapshotCreate(reach=5000, likes=200, captured_at=t1)
        )
        snap2 = await analytics_service.record_snapshot(
            db, post.id, MetricSnapshotCreate(reach=8000, likes=450, captured_at=t2)
        )

        assert snap1.id != snap2.id

        snapshots = await analytics_service.get_snapshots(db, post.id)
        assert len(snapshots) == 2
        assert snapshots[0].id == snap1.id
        assert snapshots[0].reach == 5000
        assert snapshots[1].id == snap2.id
        assert snapshots[1].reach == 8000


# =====================================================================
# 2. Derived Metrics & Comparison Tests
# =====================================================================

@pytest.mark.asyncio
async def test_derived_engagement_rate_missing_metrics_tolerance():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Missing Metrics Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        db.add(post)
        await db.commit()

        # Only reach and likes provided; comments, shares, saves are None
        snap = await analytics_service.record_snapshot(
            db, post.id, MetricSnapshotCreate(reach=1000, likes=50)
        )
        # 50 / 1000 = 0.05
        assert snap.engagement_rate == pytest.approx(0.05, abs=0.001)
        assert snap.comments is None
        assert snap.shares is None


@pytest.mark.asyncio
async def test_like_for_like_comparison_no_evaluative_winner():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Cross Platform Comparison")
        db.add(camp)
        await db.flush()

        p_ig = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        p_yt = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.YOUTUBE.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        db.add_all([p_ig, p_yt])
        await db.commit()

        await analytics_service.record_snapshot(
            db, p_ig.id, MetricSnapshotCreate(reach=9500, likes=740, comments=81, shares=120, saves=210)
        )
        await analytics_service.record_snapshot(
            db, p_yt.id, MetricSnapshotCreate(reach=11200, likes=600, comments=150, shares=80, clicks=400)
        )

        comparison = await analytics_service.get_campaign_comparison(db, camp.id)

        assert comparison.campaign_id == camp.id
        assert len(comparison.posts) == 2

        posts_by_platform = {p.platform: p for p in comparison.posts}
        assert "instagram" in posts_by_platform
        assert "youtube" in posts_by_platform

        assert posts_by_platform["instagram"].reach == 9500
        assert posts_by_platform["instagram"].engagement_rate == pytest.approx(0.1212, abs=0.001)

        assert posts_by_platform["youtube"].reach == 11200
        # (600 + 150 + 80) / 11200 = 830 / 11200 = 0.0741
        assert posts_by_platform["youtube"].engagement_rate == pytest.approx(0.0741, abs=0.001)

        # Confirm NO "winner" field exists in the comparison schema
        dumped = comparison.model_dump()
        assert "winner" not in dumped
        for post_item in dumped["posts"]:
            assert "winner" not in post_item


@pytest.mark.asyncio
async def test_comparison_insufficient_data():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Empty Camp")
        db.add(camp)
        await db.commit()

        comparison = await analytics_service.get_campaign_comparison(db, camp.id)
        assert comparison.campaign_id == camp.id
        assert len(comparison.posts) == 0
        assert "Insufficient" in comparison.summary


# =====================================================================
# 3. Evidence-Backed Insights Tests
# =====================================================================

@pytest.mark.asyncio
async def test_deterministic_insights_have_traceable_evidence():
    analytics_service = AnalyticsService()
    async with async_session_maker() as db:
        camp = Campaign(name="Evidence Camp")
        db.add(camp)
        await db.flush()

        post1 = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        post2 = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.YOUTUBE.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
        )
        db.add_all([post1, post2])
        await db.commit()

        t_snap1 = datetime.now(timezone.utc) - timedelta(hours=10)
        t_snap2 = datetime.now(timezone.utc)

        # Post 1: two snapshots
        s1_1 = await analytics_service.record_snapshot(
            db, post1.id, MetricSnapshotCreate(reach=5000, likes=200, captured_at=t_snap1)
        )
        s1_2 = await analytics_service.record_snapshot(
            db, post1.id, MetricSnapshotCreate(reach=10000, likes=1200, saves=300, captured_at=t_snap2)
        )

        # Post 2: one snapshot
        s2 = await analytics_service.record_snapshot(
            db, post2.id, MetricSnapshotCreate(reach=4000, likes=150, captured_at=t_snap2)
        )

        insights = await analytics_service.generate_campaign_insights(db, camp.id)

        assert len(insights) > 0

        # Every insight must have non-empty evidence referencing valid post IDs
        for ins in insights:
            assert ins.summary is not None and len(ins.summary) > 0
            assert isinstance(ins.evidence, list)
            assert len(ins.evidence) > 0

            for ev in ins.evidence:
                assert "post_id" in ev
                assert ev["post_id"] in [str(post1.id), str(post2.id)]
                assert "metric_field" in ev
                assert "value" in ev
                assert ev["value"] is not None

        # Verify Campaign.previous_insights was populated with structured data
        await db.refresh(camp)
        assert isinstance(camp.previous_insights, list)
        assert len(camp.previous_insights) == len(insights)
        assert "insight_id" in camp.previous_insights[0]
        assert "summary" in camp.previous_insights[0]
        assert "evidence" in camp.previous_insights[0]


# =====================================================================
# 4. HTTP API & Next Brief Feedback Loop Tests
# =====================================================================

@pytest.mark.asyncio
async def test_api_metric_snapshot_workflow(client: AsyncClient, sample_brief: dict[str, Any]):
    # Step 1: Create campaign & generate post
    c_res = await client.post("/api/campaigns", json={"name": "Analytics E2E", "brief": sample_brief})
    camp_id = c_res.json()["id"]

    p_res = await client.post(f"/api/campaigns/{camp_id}/posts/generate", json={})
    post_id = p_res.json()["id"]

    # Step 2: Attempting to record metrics before publish -> 409
    pre_snap_res = await client.post(
        f"/api/posts/{post_id}/metrics",
        json={"reach": 1000, "likes": 50},
    )
    assert pre_snap_res.status_code == 409

    # Step 3: Approve & publish
    await client.post(f"/api/posts/{post_id}/approve")
    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 200

    # Step 4: Record snapshot via API -> 201
    snap_res = await client.post(
        f"/api/posts/{post_id}/metrics",
        json={
            "impressions": 15000,
            "reach": 12000,
            "likes": 950,
            "comments": 120,
            "shares": 80,
            "saves": 250,
            "clicks": 400,
        },
    )
    assert snap_res.status_code == 201
    data = snap_res.json()
    assert data["reach"] == 12000
    assert data["likes"] == 950
    # Derived ER: (950 + 120 + 80 + 250) / 12000 = 1400 / 12000 = 0.1167
    assert data["engagement_rate"] == pytest.approx(0.1167, abs=0.001)

    # Step 5: Retrieve snapshots
    list_res = await client.get(f"/api/posts/{post_id}/metrics")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


@pytest.mark.asyncio
async def test_feedback_into_next_generation_brief(
    client: AsyncClient,
    spy_llm: SpyingLLMProvider,
    sample_brief: dict[str, Any],
):
    """End-to-end feedback verification:

    Published Post
    → Metric Snapshot
    → Generate Insights
    → Stored on Campaign.previous_insights
    → Next generation call incorporates previous insights into LLM prompt
    """
    # 1. Create campaign
    c_res = await client.post("/api/campaigns", json={"name": "Insight Feedback Camp", "brief": sample_brief})
    camp_id = c_res.json()["id"]

    # 2. First post: generate -> approve -> publish
    p1_res = await client.post(f"/api/campaigns/{camp_id}/posts/generate", json={})
    p1_id = p1_res.json()["id"]
    await client.post(f"/api/posts/{p1_id}/approve")
    await client.post(f"/api/posts/{p1_id}/publish")

    # 3. Add metric snapshot
    await client.post(
        f"/api/posts/{p1_id}/metrics",
        json={
            "impressions": 20000,
            "reach": 16000,
            "likes": 1600,
            "comments": 200,
            "saves": 500,
        },
    )

    # 4. Generate campaign insights
    ins_res = await client.post(f"/api/campaigns/{camp_id}/insights/generate")
    assert ins_res.status_code == 200
    insights = ins_res.json()
    assert len(insights) > 0
    first_insight_summary = insights[0]["summary"]

    # 5. Retrieve campaign and verify previous_insights is populated
    camp_get = await client.get(f"/api/campaigns/{camp_id}")
    assert camp_get.status_code == 200
    assert camp_get.json()["previous_insights"] is not None
    assert len(camp_get.json()["previous_insights"]) > 0

    # 6. Generate SECOND post for the same campaign
    p2_res = await client.post(f"/api/campaigns/{camp_id}/posts/generate", json={})
    assert p2_res.status_code == 201

    # 7. Verify the prompt sent to LLM contains the previous insights
    assert spy_llm.last_prompt is not None
    assert "## Previous Campaign Insights" in spy_llm.last_prompt
    assert first_insight_summary in spy_llm.last_prompt
    # Verify the brief is also still present and authoritative
    assert "## Content Brief" in spy_llm.last_prompt
    assert sample_brief["title"] in spy_llm.last_prompt
