"""Regression coverage for carrying workspace-scoped campaign learning into a new brief."""

import uuid
from typing import TypeVar

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.ai.provider import LLMProvider
from app.api.deps import get_llm_provider
from app.database import async_session_maker, init_db
from app.domain.enums import Language, Platform
from app.domain.models import Campaign
from app.main import app
from app.schemas.content import GeneratedInstagramPost, MediaDirection

T = TypeVar("T", bound=BaseModel)


class PromptCapturingProvider(LLMProvider):
    """Deterministic provider that records the generation prompt."""

    def __init__(self) -> None:
        self.prompt = ""

    async def generate_structured(self, *, prompt: str, system_instruction: str, output_schema: type[T], temperature: float = 0.8) -> T:
        self.prompt = prompt
        return GeneratedInstagramPost(platform=Platform.INSTAGRAM, language=Language.BENGALI, hook="রহস্যের নতুন অধ্যায়", caption="নতুন এক রহস্যের গল্প দেখতে এখনই হইচই-এ আসুন।", hashtags=["#হইচই", "#রহস্য", "#বাংলা", "#থ্রিলার", "#নতুন"], cta="এখনই দেখুন", media_direction=MediaDirection(description="অন্ধকার রহস্যময় ঘর", style="Cinematic", mood="Tense", aspect_ratio="4:5"))


@pytest_asyncio.fixture(autouse=True)
async def ensure_schema():
    await init_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def brief() -> dict[str, object]:
    return {"title": "New learning brief", "genre": "Thriller", "language": "bn", "audience": "Bengali viewers", "objective": "Build anticipation", "key_themes": ["mystery"], "tone": "Suspenseful", "cta": "Watch now", "release_date": "Friday"}


async def _register(client: AsyncClient, label: str) -> dict[str, object]:
    response = await client.post("/api/auth/register", json={"email": f"campaign-learning-{label}-{uuid.uuid4().hex}@example.com", "password": "secure-password"})
    assert response.status_code == 201
    return response.json()


def _headers(identity: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {identity['access_token']}", "X-Workspace-ID": identity["workspace"]["id"]}


async def _source_campaign(workspace_id: str, insight_summary: str) -> uuid.UUID:
    async with async_session_maker() as db:
        campaign = Campaign(name="Source campaign", workspace_id=uuid.UUID(workspace_id), previous_insights=[{"insight_id": str(uuid.uuid4()), "summary": insight_summary, "evidence": []}])
        db.add(campaign)
        await db.commit()
        return campaign.id


@pytest.mark.asyncio
async def test_campaign_creation_without_previous_insights_preserves_existing_behavior(client: AsyncClient, brief: dict[str, object]):
    identity = await _register(client, "without")
    response = await client.post("/api/campaigns", headers=_headers(identity), json={"brief": brief})
    assert response.status_code == 201
    assert response.json()["previous_insights"] == {}


@pytest.mark.asyncio
async def test_new_campaign_persists_selected_campaign_insights_and_generation_uses_them(client: AsyncClient, brief: dict[str, object]):
    identity = await _register(client, "with")
    insight_summary = "Question-led hooks increased saves with thriller audiences."
    source_id = await _source_campaign(identity["workspace"]["id"], insight_summary)
    response = await client.post("/api/campaigns", headers=_headers(identity), json={"brief": brief, "previous_insights": str(source_id)})
    assert response.status_code == 201
    campaign = response.json()
    assert campaign["previous_insights"][0]["summary"] == insight_summary
    async with async_session_maker() as db:
        persisted_campaign = await db.get(Campaign, uuid.UUID(campaign["id"]))
        assert persisted_campaign is not None
        assert persisted_campaign.previous_insights == campaign["previous_insights"]
    provider = PromptCapturingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        generated = await client.post(f"/api/campaigns/{campaign['id']}/posts/generate", headers=_headers(identity), json={})
        assert generated.status_code == 201
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
    assert insight_summary in provider.prompt


@pytest.mark.asyncio
async def test_cross_workspace_campaign_insights_cannot_be_attached(client: AsyncClient, brief: dict[str, object]):
    current_workspace_user = await _register(client, "current")
    other_workspace_user = await _register(client, "other")
    source_id = await _source_campaign(other_workspace_user["workspace"]["id"], "Private workspace learning")
    response = await client.post("/api/campaigns", headers=_headers(current_workspace_user), json={"brief": brief, "previous_insights": str(source_id)})
    assert response.status_code == 404
