"""Deterministic X validation tests; no AI, HTTP, or database dependencies."""

from app.domain.enums import Language, Platform
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.validation.engine import ValidationEngine


def valid_x_post() -> GeneratedInstagramPost:
    return GeneratedInstagramPost(
        platform=Platform.X,
        language=Language.BENGALI,
        hook="রহস্যের শুরু আজ।",
        caption="একটি হারানো সত্যের খোঁজে নতুন গল্প।",
        hashtags=["#হইচই"],
        cta="টিজার দেখুন",
        media_direction=MediaDirection(description="Dark portrait", style="Cinematic", mood="Tense", aspect_ratio="1:1"),
    )


def test_valid_x_content_passes_without_external_dependencies():
    result = ValidationEngine().validate(valid_x_post(), platform=Platform.X)
    assert result.valid


def test_x_over_limit_caption_is_rejected():
    content = valid_x_post().model_dump()
    content["caption"] = "x" * 281
    result = ValidationEngine().validate(content, platform=Platform.X)
    assert any(error.code == "CAPTION_TOO_LONG" for error in result.errors)


def test_x_missing_required_fields_are_rejected():
    result = ValidationEngine().validate({"platform": "x", "caption": ""}, platform=Platform.X)
    codes = {error.code for error in result.errors}
    assert {"CAPTION_EMPTY", "HOOK_EMPTY", "CTA_MISSING", "HASHTAGS_MISSING", "MEDIA_DIRECTION_MISSING"} <= codes


def test_x_allows_no_hashtags_but_rejects_more_than_two():
    no_tags = valid_x_post().model_dump()
    no_tags["hashtags"] = []
    assert ValidationEngine().validate(no_tags, platform=Platform.X).valid
    too_many = valid_x_post().model_dump()
    too_many["hashtags"] = ["#one", "#two", "#three"]
    assert any(error.code == "HASHTAGS_TOO_MANY" for error in ValidationEngine().validate(too_many, platform=Platform.X).errors)
