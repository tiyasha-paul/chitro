"""Media-asset validation at workflow and publishing boundaries."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.adapters import MockInstagramAdapter, PublishPayload
from app.ai.provider import LLMProvider
from app.api.deps import get_channel_adapter, get_llm_provider
from app.database import async_session_maker, init_db
from app.domain.enums import Language, Platform, PostStatus
from app.domain.exceptions import MediaValidationError
from app.domain.models import Campaign, PlatformPost
from app.main import app
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.services.auth import AuthService, create_access_token
from app.services.publishing import PublishingService
from app.validation.media import validate_media_asset


def valid_image() -> dict[str, object]:
    return {"media_type": "image", "mime_type": "image/jpeg", "width": 1080, "height": 1350, "size_bytes": 1_048_576, "asset_url": "mock://tests/image.jpg"}


def valid_video() -> dict[str, object]:
    return {"media_type": "video", "mime_type": "video/mp4", "width": 1080, "height": 1920, "size_bytes": 20_000_000, "asset_url": "mock://tests/video.mp4"}


@pytest.mark.parametrize("media", [valid_image(), valid_video()])
def test_valid_media_metadata_passes(media: dict[str, object]):
    assert validate_media_asset(media, Platform.INSTAGRAM).valid


@pytest.mark.parametrize(
    ("media", "error_code"),
    [
        ({**valid_image(), "media_type": "audio"}, "UNSUPPORTED_MEDIA_TYPE"),
        ({**valid_image(), "mime_type": "image/gif"}, "UNSUPPORTED_MIME_TYPE"),
        ({**valid_image(), "width": 0}, "MEDIA_METADATA_INVALID"),
        ({**valid_image(), "width": 1000, "height": 1200}, "UNSUPPORTED_ASPECT_RATIO"),
        ({**valid_image(), "size_bytes": 100 * 1024 * 1024 + 1}, "MEDIA_SIZE_EXCEEDED"),
        ({"media_type": "image"}, "MEDIA_METADATA_INVALID"),
    ],
)
def test_invalid_media_metadata_is_rejected(media: dict[str, object], error_code: str):
    result = validate_media_asset(media, Platform.INSTAGRAM)
    assert not result.valid
    assert any(error.code == error_code for error in result.errors)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "media",
    [
        {**valid_image(), "width": 1000, "height": 1200},
        {**valid_image(), "media_type": "audio", "mime_type": "audio/mpeg"},
        {**valid_image(), "size_bytes": 100 * 1024 * 1024 + 1},
    ],
)
async def test_mock_adapter_rejects_invalid_media_without_recording_publish(media: dict[str, object]):
    adapter = MockInstagramAdapter()
    with pytest.raises(MediaValidationError):
        await adapter.publish(PublishPayload(post_id=uuid.uuid4(), caption="Caption", media_spec=media))
    assert adapter.published_calls == []


@pytest_asyncio.fixture(autouse=True)
async def ensure_schema():
    await init_db()


@pytest.mark.asyncio
async def test_invalid_media_cannot_schedule_or_publish_and_leaves_state_unchanged():
    adapter = MockInstagramAdapter()
    service = PublishingService(default_adapter=adapter)
    invalid_media = {**valid_image(), "width": 1000, "height": 1200}
    async with async_session_maker() as db:
        campaign = Campaign(name="Media boundary campaign")
        db.add(campaign)
        await db.flush()
        approved = PlatformPost(campaign_id=campaign.id, platform="instagram", language="bn", status=PostStatus.APPROVED.value, media_spec=invalid_media)
        scheduled = PlatformPost(campaign_id=campaign.id, platform="instagram", language="bn", status=PostStatus.SCHEDULED.value, media_spec=invalid_media)
        db.add_all((approved, scheduled))
        await db.commit()

        with pytest.raises(MediaValidationError):
            await service.schedule_post(db, approved.id, datetime.now(timezone.utc) + timedelta(hours=1))
        await db.refresh(approved)
        assert approved.status == PostStatus.APPROVED.value
        assert approved.scheduled_at is None

        with pytest.raises(MediaValidationError):
            await service.publish_post(db, scheduled.id)
        await db.refresh(scheduled)
        assert scheduled.status == PostStatus.SCHEDULED.value
        assert scheduled.published_at is None
        assert scheduled.publish_result is None
        assert adapter.published_calls == []


class InvalidMediaProvider(LLMProvider):
    async def generate_structured(self, *, prompt: str, system_instruction: str, output_schema: type[BaseModel], temperature: float = 0.8) -> BaseModel:
        return GeneratedInstagramPost.model_construct(
            platform=Platform.INSTAGRAM,
            language=Language.BENGALI,
            hook="A valid hook",
            caption="A valid caption",
            hashtags=["#one", "#two", "#three", "#four", "#five"],
            cta="Watch now",
            media_direction=MediaDirection(description="Visual", style="Cinematic", mood="Tense", aspect_ratio="4:5"),
            media_asset={**valid_image(), "width": 1000, "height": 1200},
        )


@pytest.mark.asyncio
async def test_invalid_generated_media_is_validation_failed_and_cannot_publish():
    async with async_session_maker() as db:
        user, workspace = await AuthService().register_user(db, email=f"media-api-{uuid.uuid4().hex}@example.com", password="secure-password", display_name="Media API")
    adapter = MockInstagramAdapter()
    app.dependency_overrides[get_llm_provider] = InvalidMediaProvider
    app.dependency_overrides[get_channel_adapter] = lambda: adapter
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}", "X-Workspace-ID": str(workspace.id)}
    brief = {"title": "Media test", "genre": "Thriller", "language": "bn", "audience": "Viewers", "objective": "Awareness", "key_themes": ["mystery"], "tone": "Tense", "cta": "Watch", "release_date": "Friday"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            campaign = await client.post("/api/campaigns", headers=headers, json={"brief": brief})
            generated = await client.post(f"/api/campaigns/{campaign.json()['id']}/posts/generate", headers=headers, json={})
            assert generated.status_code == 201
            post = generated.json()
            assert post["status"] == "validation_failed"
            assert any(error["code"] == "UNSUPPORTED_ASPECT_RATIO" for error in post["validation_errors"])
            publish = await client.post(f"/api/posts/{post['id']}/publish", headers=headers)
            assert publish.status_code == 422
            assert adapter.published_calls == []
            assert (await client.get(f"/api/posts/{post['id']}", headers=headers)).json()["publish_result"] is None
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
        app.dependency_overrides.pop(get_channel_adapter, None)
