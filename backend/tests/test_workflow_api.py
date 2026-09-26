"""Comprehensive API and service workflow tests (Milestone 4).

Validates the full workflow:
ContentBrief -> Campaign -> Generate -> Validate -> PENDING_APPROVAL
-> Reject -> Regenerate -> Approve -> APPROVED
"""

import uuid
from typing import Any, TypeVar
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.ai.provider import AIProviderError, LLMProvider
from app.api.deps import get_llm_provider
from app.domain.enums import Language, Platform, PostStatus
from app.main import app
from app.schemas.briefs import ContentBrief
from app.schemas.content import GeneratedInstagramPost, MediaDirection

T = TypeVar("T", bound=BaseModel)


# --- Mock LLM Provider for Isolated Testing ---

class MockLLMProvider(LLMProvider):
    """Test fake LLM provider that simulates Gemini responses without network calls."""

    def __init__(self) -> None:
        self.last_prompt: str | None = None
        self.last_system_instruction: str | None = None
        self.custom_response: Any | None = None
        self.should_fail: bool = False
        self.failure_message: str = "Simulated upstream LLM failure"

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

        if self.should_fail:
            raise AIProviderError(self.failure_message)

        if self.custom_response is not None:
            return self.custom_response

        # Default valid Instagram post
        return GeneratedInstagramPost(
            platform=Platform.INSTAGRAM,
            language=Language.BENGALI,
            hook="একটি রোমাঞ্চকর নিখোঁজ সংবাদ—আপনি কি সত্য জানতে প্রস্তুত?",
            caption="একটি শান্ত রাতে হারিয়ে যাওয়া মানুষের গভীর সত্য সন্ধানের রুদ্ধশ্বাস গল্প। হইচই-এর অরিজিনাল সিরিজ নিখোঁজ আসছে এই শুক্রবার।",
            hashtags=["#নিখোঁজ", "#হইচই", "#বাংলাসিনেমা", "#থ্রিলার", "#ড্রামা"],
            cta="এখনই হইচই অ্যাপে টিজারটি দেখুন এবং মতামত জানান।",
            media_direction=MediaDirection(
                description="একটি অন্ধকার ঘর যেখানে পুরনো টেবিল ল্যাম্প জ্বলছে।",
                style="Cinematic dark thriller",
                mood="Tense, ominous",
                aspect_ratio="4:5",
            ),
        )


@pytest.fixture
def mock_provider() -> MockLLMProvider:
    provider = MockLLMProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_llm_provider, None)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_brief_payload() -> dict[str, Any]:
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


# --- Campaign Creation Tests ---

@pytest.mark.asyncio
async def test_create_campaign_success(client: AsyncClient, sample_brief_payload: dict[str, Any]):
    response = await client.post(
        "/api/campaigns",
        json={"name": "Nikhoj Launch Campaign", "brief": sample_brief_payload},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nikhoj Launch Campaign"
    assert data["objective"] == "Drive teaser hype"
    assert data["target_audience"] == "Bengali thriller fans aged 22-40"
    assert data["brief_payload"]["title"] == "নিখোঁজ (Nikhoj)"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_campaign_missing_fields_returns_422(client: AsyncClient):
    # Missing required brief fields
    response = await client.post(
        "/api/campaigns",
        json={"name": "Incomplete", "brief": {"title": "Only Title"}},
    )
    assert response.status_code == 422


# --- Post Generation Tests ---

@pytest.mark.asyncio
async def test_generate_post_reaches_pending_approval(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    # 1. Create campaign
    camp_res = await client.post(
        "/api/campaigns",
        json={"name": "Nikhoj", "brief": sample_brief_payload},
    )
    campaign_id = camp_res.json()["id"]

    # 2. Request generation
    gen_res = await client.post(
        f"/api/campaigns/{campaign_id}/posts/generate",
        json={"platform": "instagram", "language": "bn"},
    )
    assert gen_res.status_code == 201
    data = gen_res.json()

    assert data["campaign_id"] == campaign_id
    assert data["platform"] == "instagram"
    assert data["language"] == "bn"
    assert data["status"] == "pending_approval"
    assert data["generation_attempt"] == 1
    assert data["validation_errors"] is None
    assert len(data["hashtags"]) >= 5
    assert data["hook"] is not None
    assert data["cta"] is not None
    assert data["media_spec"]["aspect_ratio"] == "4:5"


@pytest.mark.asyncio
async def test_generate_post_validation_failure_reaches_validation_failed(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    # Configure mock to return an invalid post (caption exceeds 2200 chars)
    mock_provider.custom_response = GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.BENGALI,
        hook="হুক লাইন",
        caption="ক" * 2500,  # Violates 2200 char max
        hashtags=["#এক", "#দুই", "#তিন", "#চার", "#পাঁচ"],
        cta="দেখুন",
        media_direction=MediaDirection(
            description="ছবি",
            style="ফটো",
            mood="ডার্ক",
            aspect_ratio="1:1",
        ),
    )

    camp_res = await client.post(
        "/api/campaigns",
        json={"name": "Bad Gen Campaign", "brief": sample_brief_payload},
    )
    campaign_id = camp_res.json()["id"]

    gen_res = await client.post(
        f"/api/campaigns/{campaign_id}/posts/generate",
        json={"platform": "instagram", "language": "bn"},
    )
    assert gen_res.status_code == 201
    data = gen_res.json()

    assert data["status"] == "validation_failed"
    assert data["validation_errors"] is not None
    error_codes = [e["code"] for e in data["validation_errors"]]
    assert "CAPTION_TOO_LONG" in error_codes


@pytest.mark.asyncio
async def test_generate_post_provider_error_returns_502(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    mock_provider.should_fail = True
    mock_provider.failure_message = "Gemini quota exceeded"

    camp_res = await client.post(
        "/api/campaigns",
        json={"name": "Fail Campaign", "brief": sample_brief_payload},
    )
    campaign_id = camp_res.json()["id"]

    gen_res = await client.post(
        f"/api/campaigns/{campaign_id}/posts/generate",
        json={"platform": "instagram", "language": "bn"},
    )
    assert gen_res.status_code == 502
    assert "AI generation provider encountered an error" in gen_res.json()["detail"]


@pytest.mark.asyncio
async def test_generate_post_campaign_not_found(client: AsyncClient):
    random_id = str(uuid.uuid4())
    res = await client.post(f"/api/campaigns/{random_id}/posts/generate", json={})
    assert res.status_code == 404


# --- Approval and Rejection Tests ---

@pytest.mark.asyncio
async def test_approve_post_success(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    camp_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief_payload})
    post_res = await client.post(f"/api/campaigns/{camp_res.json()['id']}/posts/generate", json={})
    post_id = post_res.json()["id"]

    # Approve
    app_res = await client.post(f"/api/posts/{post_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Cannot approve again (Invalid transition APPROVED -> APPROVED)
    app_res_2 = await client.post(f"/api/posts/{post_id}/approve")
    assert app_res_2.status_code == 409


@pytest.mark.asyncio
async def test_reject_post_success(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    camp_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief_payload})
    post_res = await client.post(f"/api/campaigns/{camp_res.json()['id']}/posts/generate", json={})
    post_id = post_res.json()["id"]

    # Reject with human reason
    rej_res = await client.post(
        f"/api/posts/{post_id}/reject",
        json={"reason": "ক্যাপশন আরও টানটান হতে হবে এবং হইচই লিংক দিতে হবে।"},
    )
    assert rej_res.status_code == 200
    data = rej_res.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "ক্যাপশন আরও টানটান হতে হবে এবং হইচই লিংক দিতে হবে।"

    # Cannot reject again
    rej_res_2 = await client.post(
        f"/api/posts/{post_id}/reject",
        json={"reason": "Again"},
    )
    assert rej_res_2.status_code == 409


# --- Regeneration Tests ---

@pytest.mark.asyncio
async def test_regeneration_flow_with_audit_trail(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    # 1. Create and generate post
    camp_res = await client.post("/api/campaigns", json={"name": "C", "brief": sample_brief_payload})
    post_res = await client.post(f"/api/campaigns/{camp_res.json()['id']}/posts/generate", json={})
    post_id = post_res.json()["id"]
    original_caption = post_res.json()["caption"]

    # 2. Reject
    rejection_feedback = "Less formal tone, focus on thriller element"
    await client.post(f"/api/posts/{post_id}/reject", json={"reason": rejection_feedback})

    # 3. Configure mock for second generation
    mock_provider.custom_response = GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.BENGALI,
        hook="দ্বিতীয় চেষ্টা: সত্য কখনো গোপন থাকে না!",
        caption="দ্বিতীয় সংস্করণের উন্নত ক্যাপশন যা দর্শকের মনে রোমাঞ্চ জাগিয়ে তোলে।",
        hashtags=["#নিখোঁজ", "#হইচই", "#নতুনসিরিজ", "#ড্রামা", "#থ্রিলার"],
        cta="হইচই অ্যাপে দেখতে ভুলবেন না!",
        media_direction=MediaDirection(
            description="নতুন ভিজ্যুয়াল ডিরেকশন",
            style="Dark thriller",
            mood="Dramatic",
            aspect_ratio="1:1",
        ),
    )

    # 4. Regenerate
    regen_res = await client.post(f"/api/posts/{post_id}/regenerate")
    assert regen_res.status_code == 200
    regen_data = regen_res.json()

    assert regen_data["status"] == "pending_approval"
    assert regen_data["generation_attempt"] == 2
    assert regen_data["caption"] != original_caption

    # 5. Check audit trail preservation
    assert regen_data["generation_history"] is not None
    assert len(regen_data["generation_history"]) == 1
    prior_attempt = regen_data["generation_history"][0]
    assert prior_attempt["attempt"] == 1
    assert prior_attempt["status"] == "rejected"
    assert prior_attempt["rejection_reason"] == rejection_feedback
    assert prior_attempt["caption"] == original_caption

    # 6. Verify rejection reason reached the prompt builder
    assert rejection_feedback in mock_provider.last_prompt


# --- Retrieval Tests ---

@pytest.mark.asyncio
async def test_get_campaign_and_post_retrieval(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    camp_res = await client.post("/api/campaigns", json={"name": "Fetch Test", "brief": sample_brief_payload})
    campaign_id = camp_res.json()["id"]

    post_res = await client.post(f"/api/campaigns/{campaign_id}/posts/generate", json={})
    post_id = post_res.json()["id"]

    # Retrieve campaign
    get_camp = await client.get(f"/api/campaigns/{campaign_id}")
    assert get_camp.status_code == 200
    assert len(get_camp.json()["posts"]) == 1

    # Retrieve post
    get_post = await client.get(f"/api/posts/{post_id}")
    assert get_post.status_code == 200
    assert get_post.json()["id"] == post_id


@pytest.mark.asyncio
async def test_get_nonexistent_returns_404(client: AsyncClient):
    random_id = str(uuid.uuid4())
    assert (await client.get(f"/api/campaigns/{random_id}")).status_code == 404
    assert (await client.get(f"/api/posts/{random_id}")).status_code == 404


# --- Full End-to-End Workflow Test ---

@pytest.mark.asyncio
async def test_complete_stateful_workflow(
    client: AsyncClient,
    mock_provider: MockLLMProvider,
    sample_brief_payload: dict[str, Any],
):
    """End-to-End integration test covering the entire Milestone 4 workflow:

    Brief -> Campaign -> Generate -> Validate -> PENDING_APPROVAL
    -> Reject -> Regenerate -> PENDING_APPROVAL -> Approve -> APPROVED
    """
    # Step 1: Create Campaign
    c_res = await client.post(
        "/api/campaigns",
        json={"name": "Complete E2E Campaign", "brief": sample_brief_payload},
    )
    assert c_res.status_code == 201
    campaign_id = c_res.json()["id"]

    # Step 2: Generate Post
    g_res = await client.post(f"/api/campaigns/{campaign_id}/posts/generate", json={})
    assert g_res.status_code == 201
    post_id = g_res.json()["id"]
    assert g_res.json()["status"] == "pending_approval"
    assert g_res.json()["generation_attempt"] == 1

    # Step 3: Reject Post
    r_res = await client.post(
        f"/api/posts/{post_id}/reject",
        json={"reason": "Make the hook punchier and more suspenseful."},
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "rejected"
    assert r_res.json()["rejection_reason"] == "Make the hook punchier and more suspenseful."

    # Step 4: Regenerate Post
    mock_provider.custom_response = GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.BENGALI,
        hook="সত্য সামনে এলে পায়ের তলার মাটি সরে যাবে—আপনি তৈরি তো?",
        caption="নিখোঁজ হওয়ার আসল কারণ খুঁজতে গিয়ে যা জানা গেল, তা কল্পনারও অতীত। হইচই-এ দেখুন এই শুক্রবার।",
        hashtags=["#নিখোঁজ", "#হইচই", "#বাংলাথ্রিলার", "#রহস্য", "#নতুনসিরিজ"],
        cta="এখনই অ্যাপে গিয়ে প্রিমিয়ার রিমাইন্ডার সেট করুন।",
        media_direction=MediaDirection(
            description="রহস্যজনক আবছায়া মুখ",
            style="Suspense photography",
            mood="Ominous",
            aspect_ratio="4:5",
        ),
    )

    regen_res = await client.post(f"/api/posts/{post_id}/regenerate")
    assert regen_res.status_code == 200
    assert regen_res.json()["status"] == "pending_approval"
    assert regen_res.json()["generation_attempt"] == 2
    assert len(regen_res.json()["generation_history"]) == 1

    # Step 5: Approve Post
    app_res = await client.post(f"/api/posts/{post_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Step 6: Verify Persistence and Status
    final_post = await client.get(f"/api/posts/{post_id}")
    assert final_post.status_code == 200
    assert final_post.json()["status"] == "approved"
    assert final_post.json()["generation_attempt"] == 2
    assert len(final_post.json()["generation_history"]) == 1
