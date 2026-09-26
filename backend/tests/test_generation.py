"""Tests for the AI generation layer (Milestone 2).

These tests use mocks — no live LLM calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ai.platform_strategy import InstagramStrategy, PlatformStrategy, XStrategy
from app.ai.prompts import build_generation_prompt, build_system_instruction
from app.ai.provider import AIProviderError, AIStructuredOutputError, LLMProvider
from app.domain.enums import Language, Platform
from app.schemas.briefs import ContentBrief
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.services.generation import GenerationService


# --- Fixtures ---

@pytest.fixture
def sample_brief() -> ContentBrief:
    return ContentBrief(
        title="Test Show",
        genre="Drama",
        language=Language.BENGALI,
        audience="Bengali drama fans aged 25-40",
        objective="Drive trailer views",
        key_themes=["family", "betrayal"],
        tone="emotional, gripping",
        cta="Watch now on hoichoi",
        release_date="This Friday",
    )


@pytest.fixture
def sample_instagram_result() -> GeneratedInstagramPost:
    return GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.BENGALI,
        hook="একটি মনকাড়া হুক লাইন",
        caption="একটি সম্পূর্ণ ক্যাপশন যা দর্শকদের আকৃষ্ট করবে।",
        hashtags=["#হইচই", "#বাংলাসিনেমা", "#ড্রামা"],
        cta="এখনই হইচই অ্যাপে দেখুন",
        media_direction=MediaDirection(
            description="A dramatic portrait shot",
            style="Cinematic",
            mood="Tense and emotional",
            aspect_ratio="4:5",
        ),
    )


# --- Provider contract tests ---

def test_llm_provider_is_abstract():
    """LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore


def test_ai_provider_error_hierarchy():
    """AIStructuredOutputError is a subclass of AIProviderError."""
    assert issubclass(AIStructuredOutputError, AIProviderError)


# --- Platform strategy tests ---

def test_instagram_strategy_platform():
    strategy = InstagramStrategy()
    assert strategy.platform() == Platform.INSTAGRAM


def test_instagram_strategy_content_rules():
    strategy = InstagramStrategy()
    rules = strategy.content_rules()
    assert rules["platform"] == "Instagram"
    assert "hashtag_range" in rules
    assert "caption_length" in rules


def test_instagram_strategy_output_schema():
    strategy = InstagramStrategy()
    schema = strategy.output_schema()
    assert schema is GeneratedInstagramPost


def test_instagram_strategy_system_prompt():
    strategy = InstagramStrategy()
    fragment = strategy.system_prompt_fragment()
    assert "Instagram" in fragment
    assert len(fragment) > 20


def test_x_strategy_is_concise_and_distinct_from_instagram():
    strategy = XStrategy()
    assert strategy.platform() == Platform.X
    assert strategy.content_rules()["caption_length"] == "1–280 characters"
    assert strategy.content_rules()["hashtag_range"] == "0–2 relevant hashtags"
    assert "X" in strategy.system_prompt_fragment()


def test_platform_strategy_is_abstract():
    with pytest.raises(TypeError):
        PlatformStrategy()  # type: ignore


# --- Prompt building tests ---

def test_build_system_instruction_bengali():
    strategy = InstagramStrategy()
    instruction = build_system_instruction(strategy, Language.BENGALI)
    assert "বাংলা" in instruction
    assert "Bengali" in instruction
    assert "Instagram" in instruction


def test_build_system_instruction_english():
    strategy = InstagramStrategy()
    instruction = build_system_instruction(strategy, Language.ENGLISH)
    assert "English" in instruction
    assert "বাংলা" not in instruction


def test_build_generation_prompt_includes_brief(sample_brief: ContentBrief):
    strategy = InstagramStrategy()
    prompt = build_generation_prompt(sample_brief, strategy)
    assert sample_brief.title in prompt
    assert sample_brief.genre in prompt
    assert sample_brief.audience in prompt
    assert sample_brief.objective in prompt


def test_build_generation_prompt_includes_themes(sample_brief: ContentBrief):
    strategy = InstagramStrategy()
    prompt = build_generation_prompt(sample_brief, strategy)
    for theme in sample_brief.key_themes:
        assert theme in prompt


def test_build_generation_prompt_includes_platform_rules(sample_brief: ContentBrief):
    strategy = InstagramStrategy()
    prompt = build_generation_prompt(sample_brief, strategy)
    assert "Instagram" in prompt
    assert "hashtag" in prompt.lower()


def test_build_generation_prompt_with_insights(sample_brief: ContentBrief):
    strategy = InstagramStrategy()
    insights = [{"summary": "Posts with questions get 2x engagement"}]
    prompt = build_generation_prompt(
        sample_brief, strategy, previous_insights=insights
    )
    assert "Previous Campaign Insights" in prompt
    assert "questions get 2x engagement" in prompt


def test_build_generation_prompt_with_rejection(sample_brief: ContentBrief):
    strategy = InstagramStrategy()
    reason = "Caption too long, reduce to under 500 chars"
    prompt = build_generation_prompt(
        sample_brief, strategy, rejection_reason=reason
    )
    assert "Rejection Feedback" in prompt
    assert reason in prompt


# --- GenerationService tests ---

@pytest.mark.asyncio
async def test_generation_service_calls_provider(
    sample_brief: ContentBrief,
    sample_instagram_result: GeneratedInstagramPost,
):
    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.generate_structured.return_value = sample_instagram_result

    service = GenerationService(provider=mock_provider)
    result = await service.generate_post(
        brief=sample_brief, platform=Platform.INSTAGRAM
    )

    assert result == sample_instagram_result
    mock_provider.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_generation_service_unsupported_platform(sample_brief: ContentBrief):
    mock_provider = AsyncMock(spec=LLMProvider)
    service = GenerationService(provider=mock_provider)

    with pytest.raises(ValueError, match="No generation strategy"):
        await service.generate_post(
            brief=sample_brief, platform=Platform.YOUTUBE
        )


@pytest.mark.asyncio
async def test_generation_service_selects_x_strategy_and_english_mandate(sample_instagram_result: GeneratedInstagramPost):
    mock_provider = AsyncMock(spec=LLMProvider)
    x_result = sample_instagram_result.model_copy(update={"platform": Platform.X, "language": Language.ENGLISH})
    mock_provider.generate_structured.return_value = x_result
    brief = ContentBrief(title="Test", genre="Drama", language=Language.ENGLISH, audience="Fans", objective="Awareness")

    result = await GenerationService(provider=mock_provider).generate_post(brief=brief, platform=Platform.X)

    assert result == x_result
    kwargs = mock_provider.generate_structured.await_args.kwargs
    assert "X" in kwargs["system_instruction"]
    assert "English" in kwargs["system_instruction"]
    assert "X" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_generation_service_propagates_provider_error(
    sample_brief: ContentBrief,
):
    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.generate_structured.side_effect = AIProviderError("API down")

    service = GenerationService(provider=mock_provider)

    with pytest.raises(AIProviderError, match="API down"):
        await service.generate_post(
            brief=sample_brief, platform=Platform.INSTAGRAM
        )


# --- Schema tests ---

def test_content_brief_validation():
    brief = ContentBrief(
        title="Test",
        genre="Action",
        language=Language.ENGLISH,
        audience="Everyone",
        objective="Awareness",
    )
    assert brief.title == "Test"
    assert brief.key_themes == []
    assert brief.tone is None


def test_generated_instagram_post_schema(sample_instagram_result: GeneratedInstagramPost):
    assert sample_instagram_result.platform == Platform.INSTAGRAM
    assert sample_instagram_result.language == Language.BENGALI
    assert len(sample_instagram_result.hashtags) > 0
    assert sample_instagram_result.media_direction.aspect_ratio == "4:5"
