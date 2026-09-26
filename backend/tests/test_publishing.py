"""Tests for Milestone 5: Mock Publishing & Scheduling Boundary.

Verifies:
1. MockInstagramAdapter protocol compliance and deterministic output.
2. PublishingService scheduling and publishing state machine enforcement.
3. Idempotency on publishing.
4. Channel adapter failure isolation (no transition to PUBLISHED).
5. HTTP endpoints:
   - POST /api/posts/{id}/schedule
   - POST /api/posts/{id}/publish
6. Complete End-to-End workflow from Brief to Published.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import select

from app.adapters import (
    ChannelAdapter,
    ChannelAdapterError,
    MockInstagramAdapter,
    PublishPayload,
    PublishResult,
    get_channel_adapter,
)
from app.ai.provider import LLMProvider
from app.api.deps import get_channel_adapter as deps_get_channel_adapter
from app.api.deps import get_llm_provider
from app.database import async_session_maker
from app.domain.enums import Language, Platform, PostStatus
from app.domain.exceptions import InvalidStateTransitionError, ResourceNotFoundError
from app.domain.models import Campaign, PlatformPost
from app.domain.state_machine import transition_post
from app.main import app
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.services.publishing import PublishingService
from app.services.auth import AuthService, create_access_token

T = TypeVar("T", bound=BaseModel)


def valid_media_spec() -> dict[str, object]:
    return {
        "media_type": "image",
        "mime_type": "image/jpeg",
        "width": 1080,
        "height": 1350,
        "size_bytes": 1_048_576,
        "asset_url": "mock://tests/asset.jpg",
    }


# --- Test Fakes & Fixtures ---

class FakeLLMProvider(LLMProvider):
    """Predictable mock LLM provider for workflow tests."""

    async def generate_structured(
        self,
        *,
        prompt: str,
        system_instruction: str,
        output_schema: type[T],
        temperature: float = 0.8,
    ) -> T:
        return GeneratedInstagramPost(
            platform=Platform.INSTAGRAM,
            language=Language.BENGALI,
            hook="একটি রোমাঞ্চকর নিখোঁজ সংবাদ—আপনি কি প্রস্তুত?",
            caption="একটি শান্ত রাতে হারিয়ে যাওয়া মানুষের গভীর সত্য সন্ধানের গল্প। হইচই-এর অরিজিনাল সিরিজ নিখোঁজ আসছে এই শুক্রবার।",
            hashtags=["#নিখোঁজ", "#হইচই", "#বাংলাসিনেমা", "#থ্রিলার", "#ড্রামা"],
            cta="এখনই হইচই অ্যাপে টিজারটি দেখুন।",
            media_direction=MediaDirection(
                description="রহস্যজনক আলোছায়ার দৃশ্য।",
                style="Cinematic dark thriller",
                mood="Tense, ominous",
                aspect_ratio="4:5",
            ),
        )


@pytest.fixture
def mock_llm():
    provider = FakeLLMProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_llm_provider, None)


@pytest.fixture
def mock_adapter():
    adapter = MockInstagramAdapter()
    app.dependency_overrides[deps_get_channel_adapter] = lambda: adapter
    yield adapter
    app.dependency_overrides.pop(deps_get_channel_adapter, None)


@pytest_asyncio.fixture
async def client(mock_llm, mock_adapter):
    async with async_session_maker() as db:
        user, workspace = await AuthService().register_user(
            db,
            email=f"publishing-api-{uuid.uuid4().hex}@example.com",
            password="secure-password",
            display_name="Publishing API",
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
# 1. Adapter Unit Tests
# =====================================================================

@pytest.mark.asyncio
async def test_mock_instagram_adapter_success():
    adapter = MockInstagramAdapter()
    post_id = uuid.uuid4()
    payload = PublishPayload(
        post_id=post_id,
        caption="টেস্ট ক্যাপশন",
        media_spec={"media_type": "video", "mime_type": "video/mp4", "width": 1080, "height": 1920, "size_bytes": 1_048_576},
        hashtags=["#হইচই", "#বাংলা", "#সিনেমা", "#নতুন", "#সিরিজ"],
        cta="দেখুন",
        platform="instagram",
    )

    result = await adapter.publish(payload)

    assert isinstance(result, PublishResult)
    assert result.provider == "mock_instagram"
    assert result.external_post_id == f"mock_ig_{post_id.hex[:12]}"
    assert result.url == f"https://mock-instagram.chitro.local/p/{result.external_post_id}"
    assert result.status == "published"
    assert result.metadata["caption_length"] == len("টেস্ট ক্যাপশন")
    assert result.metadata["media_format"] == "video"
    assert len(adapter.published_calls) == 1


@pytest.mark.asyncio
async def test_mock_instagram_adapter_failure():
    adapter = MockInstagramAdapter(simulate_failure=True, failure_message="Network timeout")
    payload = PublishPayload(
        post_id=uuid.uuid4(),
        caption="টেস্ট",
        media_spec=valid_media_spec(),
        platform="instagram",
    )

    with pytest.raises(ChannelAdapterError) as exc_info:
        await adapter.publish(payload)

    assert "Network timeout" in str(exc_info.value)
    assert exc_info.value.provider == "mock_instagram"
    assert len(adapter.published_calls) == 0


def test_channel_adapter_registry():
    adapter = get_channel_adapter(Platform.INSTAGRAM)
    assert isinstance(adapter, MockInstagramAdapter)

    with pytest.raises(ValueError, match="No publishing adapter configured"):
        get_channel_adapter(Platform.YOUTUBE)


# =====================================================================
# 2. PublishingService Unit Tests
# =====================================================================

@pytest.mark.asyncio
async def test_service_schedule_approved_post():
    service = PublishingService()
    async with async_session_maker() as db:
        camp = Campaign(name="Schedule Test Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.APPROVED.value,
            caption="অনুমোদিত পোস্ট",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)

        future_time = datetime.now(timezone.utc) + timedelta(days=2)
        scheduled_post = await service.schedule_post(db, post.id, future_time)

        assert scheduled_post.status == PostStatus.SCHEDULED.value
        assert scheduled_post.scheduled_at == future_time


@pytest.mark.asyncio
async def test_service_schedule_past_time_rejected():
    service = PublishingService()
    async with async_session_maker() as db:
        camp = Campaign(name="Past Time Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.APPROVED.value,
            caption="অনুমোদিত",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(ValueError, match="scheduled_at must be in the future"):
            await service.schedule_post(db, post.id, past_time)


@pytest.mark.asyncio
async def test_service_schedule_unapproved_post_rejected():
    service = PublishingService()
    async with async_session_maker() as db:
        camp = Campaign(name="Unapproved Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PENDING_APPROVAL.value,
            caption="অপেক্ষারত",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        future_time = datetime.now(timezone.utc) + timedelta(days=1)
        with pytest.raises(InvalidStateTransitionError):
            await service.schedule_post(db, post.id, future_time)


@pytest.mark.asyncio
async def test_service_schedule_nonexistent_post_rejected():
    service = PublishingService()
    async with async_session_maker() as db:
        with pytest.raises(ResourceNotFoundError):
            await service.schedule_post(db, uuid.uuid4(), datetime.now(timezone.utc) + timedelta(days=1))


@pytest.mark.asyncio
async def test_service_publish_from_scheduled():
    adapter = MockInstagramAdapter()
    service = PublishingService(default_adapter=adapter)

    async with async_session_maker() as db:
        camp = Campaign(name="Publish Scheduled Camp")
        db.add(camp)
        await db.flush()

        future_time = datetime.now(timezone.utc) + timedelta(hours=5)
        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.SCHEDULED.value,
            scheduled_at=future_time,
            caption="শিডিউল করা পোস্ট",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        pub_post = await service.publish_post(db, post.id)

        assert pub_post.status == PostStatus.PUBLISHED.value
        assert pub_post.published_at is not None
        assert pub_post.published_post_id == f"mock_ig_{post.id.hex[:12]}"
        assert pub_post.publish_result["status"] == "published"
        assert pub_post.publish_result["url"] == f"https://mock-instagram.chitro.local/p/{pub_post.published_post_id}"
        assert len(adapter.published_calls) == 1


@pytest.mark.asyncio
async def test_service_direct_publish_from_approved():
    adapter = MockInstagramAdapter()
    service = PublishingService(default_adapter=adapter)

    async with async_session_maker() as db:
        camp = Campaign(name="Direct Publish Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.APPROVED.value,
            caption="সরাসরি পাবলিশ হবে",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        pub_post = await service.publish_post(db, post.id)

        assert pub_post.status == PostStatus.PUBLISHED.value
        assert pub_post.scheduled_at is not None
        assert pub_post.published_at is not None
        assert pub_post.published_post_id is not None
        assert pub_post.publish_result["url"] == f"https://mock-instagram.chitro.local/p/{pub_post.published_post_id}"
        assert len(adapter.published_calls) == 1


@pytest.mark.asyncio
async def test_service_publish_idempotency():
    adapter = MockInstagramAdapter()
    service = PublishingService(default_adapter=adapter)

    async with async_session_maker() as db:
        camp = Campaign(name="Idempotent Camp")
        db.add(camp)
        await db.flush()

        now = datetime.now(timezone.utc)
        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.PUBLISHED.value,
            published_at=now,
            published_post_id="mock_ig_existing123",
            publish_result={"provider": "mock_instagram", "external_post_id": "mock_ig_existing123", "url": "https://mock-instagram.chitro.local/p/mock_ig_existing123"},
        )
        db.add(post)
        await db.commit()

        # Call publish again
        result = await service.publish_post(db, post.id)

        assert result.status == PostStatus.PUBLISHED.value
        assert result.published_post_id == "mock_ig_existing123"
        # Adapter was NEVER called
        assert len(adapter.published_calls) == 0


@pytest.mark.asyncio
async def test_service_publish_unapproved_post_rejected():
    service = PublishingService()
    async with async_session_maker() as db:
        camp = Campaign(name="Invalid State Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.DRAFT.value,
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        with pytest.raises(InvalidStateTransitionError):
            await service.publish_post(db, post.id)


@pytest.mark.asyncio
async def test_service_adapter_failure_leaves_post_unmodified():
    failing_adapter = MockInstagramAdapter(simulate_failure=True, failure_message="Downstream error")
    service = PublishingService(default_adapter=failing_adapter)

    async with async_session_maker() as db:
        camp = Campaign(name="Failure Isolation Camp")
        db.add(camp)
        await db.flush()

        post = PlatformPost(
            campaign_id=camp.id,
            platform=Platform.INSTAGRAM.value,
            language=Language.BENGALI.value,
            status=PostStatus.SCHEDULED.value,
            caption="ব্যর্থ হবে না নিশ্চিত করুন",
            media_spec=valid_media_spec(),
        )
        db.add(post)
        await db.commit()

        with pytest.raises(ChannelAdapterError):
            await service.publish_post(db, post.id)

        # Refresh from database and verify state is NOT published
        await db.refresh(post)
        assert post.status == PostStatus.SCHEDULED.value
        assert post.published_at is None
        assert post.published_post_id is None


# =====================================================================
# 3. HTTP API Integration Tests
# =====================================================================

@pytest.mark.asyncio
async def test_api_schedule_post_success(client: AsyncClient, sample_brief: dict[str, Any]):
    # Setup approved post
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    camp_id = c_res.json()["id"]

    p_res = await client.post(f"/api/campaigns/{camp_id}/posts/generate", json={})
    post_id = p_res.json()["id"]

    await client.post(f"/api/posts/{post_id}/approve")

    # Schedule post
    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    s_res = await client.post(
        f"/api/posts/{post_id}/schedule",
        json={"scheduled_at": future_time},
    )

    assert s_res.status_code == 200
    data = s_res.json()
    assert data["status"] == "scheduled"
    assert data["scheduled_at"] is not None


@pytest.mark.asyncio
async def test_api_schedule_past_time_returns_422(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    await client.post(f"/api/posts/{post_id}/approve")

    past_time = "2020-01-01T00:00:00Z"
    s_res = await client.post(
        f"/api/posts/{post_id}/schedule",
        json={"scheduled_at": past_time},
    )
    assert s_res.status_code == 422


@pytest.mark.asyncio
async def test_api_schedule_unapproved_returns_409(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    # Post is in PENDING_APPROVAL

    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    s_res = await client.post(
        f"/api/posts/{post_id}/schedule",
        json={"scheduled_at": future_time},
    )
    assert s_res.status_code == 409
    assert s_res.json()["current_status"] == "pending_approval"
    assert s_res.json()["target_status"] == "scheduled"


@pytest.mark.asyncio
async def test_api_schedule_nonexistent_returns_404(client: AsyncClient):
    fake_id = uuid.uuid4()
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    res = await client.post(
        f"/api/posts/{fake_id}/schedule",
        json={"scheduled_at": future_time},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_publish_scheduled_post(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    await client.post(f"/api/posts/{post_id}/approve")

    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    await client.post(f"/api/posts/{post_id}/schedule", json={"scheduled_at": future_time})

    # Publish
    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["status"] == "published"
    assert data["published_post_id"].startswith("mock_ig_")
    assert data["published_at"] is not None
    assert data["publish_result"]["provider"] == "mock_instagram"
    assert data["publish_result"]["url"] == f"https://mock-instagram.chitro.local/p/{data['published_post_id']}"


@pytest.mark.asyncio
async def test_api_direct_publish_approved_post(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    await client.post(f"/api/posts/{post_id}/approve")

    # Direct publish from APPROVED
    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["status"] == "published"
    assert data["published_post_id"] is not None
    assert data["scheduled_at"] is not None
    assert data["publish_result"]["url"] == f"https://mock-instagram.chitro.local/p/{data['published_post_id']}"


@pytest.mark.asyncio
async def test_api_publish_idempotency(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    await client.post(f"/api/posts/{post_id}/approve")

    # First publish
    res_1 = await client.post(f"/api/posts/{post_id}/publish")
    assert res_1.status_code == 200
    pub_id_1 = res_1.json()["published_post_id"]

    # Second publish
    res_2 = await client.post(f"/api/posts/{post_id}/publish")
    assert res_2.status_code == 200
    pub_id_2 = res_2.json()["published_post_id"]

    assert pub_id_1 == pub_id_2
    assert res_1.json()["publish_result"] == res_2.json()["publish_result"]


@pytest.mark.asyncio
async def test_api_publish_unapproved_returns_409(client: AsyncClient, sample_brief: dict[str, Any]):
    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    # Post is in PENDING_APPROVAL

    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 409


@pytest.mark.asyncio
async def test_api_publish_adapter_failure_returns_502(client: AsyncClient, sample_brief: dict[str, Any]):
    failing_adapter = MockInstagramAdapter(simulate_failure=True, failure_message="Downstream Instagram API error")
    app.dependency_overrides[deps_get_channel_adapter] = lambda: failing_adapter

    c_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief})
    p_res = await client.post(f"/api/campaigns/{c_res.json()['id']}/posts/generate", json={})
    post_id = p_res.json()["id"]
    await client.post(f"/api/posts/{post_id}/approve")

    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 502
    assert "Publishing channel adapter error" in pub_res.json()["detail"]

    # Verify post was not marked published
    get_res = await client.get(f"/api/posts/{post_id}")
    assert get_res.json()["status"] != "published"


# =====================================================================
# 4. Full End-to-End Workflow Test (Milestone 1 through 5)
# =====================================================================

@pytest.mark.asyncio
async def test_complete_end_to_end_journey(client: AsyncClient, sample_brief: dict[str, Any]):
    """Comprehensive test validating the complete Chitro V2 core content pipeline:

    Brief Context
         ↓
    Campaign Creation
         ↓
    Generate Instagram Bengali Post
         ↓
    Deterministic Validation (Passes)
         ↓
    Status: PENDING_APPROVAL
         ↓
    Human Review: Reject with feedback
         ↓
    Status: REJECTED
         ↓
    Regenerate Post (Feedback incorporated, history preserved)
         ↓
    Status: PENDING_APPROVAL
         ↓
    Human Review: Approve
         ↓
    Status: APPROVED
         ↓
    Schedule for tomorrow
         ↓
    Status: SCHEDULED
         ↓
    Publish to Mock Instagram
         ↓
    Status: PUBLISHED
         ↓
    Idempotent Republish
         ↓
    Status: PUBLISHED (No duplicates)
    """
    # 1. Create Campaign
    c_res = await client.post(
        "/api/campaigns",
        json={"name": "Nikhoj Complete Workflow", "brief": sample_brief},
    )
    assert c_res.status_code == 201
    camp_id = c_res.json()["id"]

    # 2. Generate Content
    gen_res = await client.post(
        f"/api/campaigns/{camp_id}/posts/generate",
        json={"platform": "instagram", "language": "bn"},
    )
    assert gen_res.status_code == 201
    post_data = gen_res.json()
    post_id = post_data["id"]
    assert post_data["status"] == "pending_approval"
    assert post_data["generation_attempt"] == 1

    # 3. Reject Post
    rej_res = await client.post(
        f"/api/posts/{post_id}/reject",
        json={"reason": "হুকাংশটি আরও বেশি রহস্যজনক করুন।"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    # 4. Regenerate Post
    regen_res = await client.post(f"/api/posts/{post_id}/regenerate")
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["status"] == "pending_approval"
    assert regen_data["generation_attempt"] == 2
    assert len(regen_data["generation_history"]) == 1

    # 5. Approve Post
    app_res = await client.post(f"/api/posts/{post_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # 6. Schedule Post
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    sched_res = await client.post(
        f"/api/posts/{post_id}/schedule",
        json={"scheduled_at": future_time},
    )
    assert sched_res.status_code == 200
    sched_data = sched_res.json()
    assert sched_data["status"] == "scheduled"
    assert sched_data["scheduled_at"] is not None

    # 7. Publish Post
    pub_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()
    assert pub_data["status"] == "published"
    assert pub_data["published_post_id"].startswith("mock_ig_")
    assert pub_data["published_at"] is not None
    assert pub_data["publish_result"]["provider"] == "mock_instagram"
    assert pub_data["publish_result"]["url"] == f"https://mock-instagram.chitro.local/p/{pub_data['published_post_id']}"

    # 8. Idempotent Republish
    pub2_res = await client.post(f"/api/posts/{post_id}/publish")
    assert pub2_res.status_code == 200
    assert pub2_res.json()["published_post_id"] == pub_data["published_post_id"]
    assert pub2_res.json()["publish_result"] == pub_data["publish_result"]

    # 9. Verify full final state via GET
    get_res = await client.get(f"/api/posts/{post_id}")
    assert get_res.status_code == 200
    final_post = get_res.json()
    assert final_post["status"] == "published"
    assert final_post["generation_attempt"] == 2
    assert len(final_post["generation_history"]) == 1
    assert final_post["published_post_id"] == pub_data["published_post_id"]
    assert final_post["publish_result"]["url"] == f"https://mock-instagram.chitro.local/p/{pub_data['published_post_id']}"
