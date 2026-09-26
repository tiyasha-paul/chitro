"""Comprehensive tests for deterministic platform validation (Milestone 3).

Validates that platform rules (Instagram) are enforced deterministically
without calling an LLM, touching a database, or performing I/O.
"""

from typing import Any
import pytest

from app.domain.enums import Language, Platform
from app.schemas.content import GeneratedInstagramPost, MediaDirection
from app.services.validation import ValidationService
from app.validation.engine import ValidationEngine, validate_post
from app.validation.instagram import InstagramSpec
from app.validation.platform_spec import ValidationResult


# --- Fixtures ---

@pytest.fixture
def valid_bengali_post() -> GeneratedInstagramPost:
    return GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.BENGALI,
        hook="একটি নিখোঁজ সংবাদ আর হাজারো অমীমাংসিত রহস্য—আপনি কি প্রস্তুত?",
        caption="শান্ত রাতে হারিয়ে যাওয়া এক ব্যক্তির সত্য সন্ধানের রোমাঞ্চকর কাহিনী। হইচই-এর নতুন অরিজিনাল সিরিজ 'নিখোঁজ'।",
        hashtags=["#নিখোঁজ", "#হইচই", "#বাংলাসিনেমা", "#থ্রিলার", "#ড্রামা"],
        cta="এখনই হইচই অ্যাপে টিজারটি দেখুন।",
        media_direction=MediaDirection(
            description="A dimly lit room with an old desk lamp and a torn photograph.",
            style="Cinematic dark noir photography",
            mood="Mysterious and suspenseful",
            aspect_ratio="4:5",
        ),
    )


@pytest.fixture
def valid_english_post() -> GeneratedInstagramPost:
    return GeneratedInstagramPost(
        platform=Platform.INSTAGRAM,
        language=Language.ENGLISH,
        hook="A missing person. A buried truth. Are you ready for the revelation?",
        caption="When the past comes knocking, no secret is safe. Watch the premiere of 'Nikhoj' only on hoichoi.",
        hashtags=["#Nikhoj", "#Hoichoi", "#BengaliCinema", "#Thriller", "#DramaSeries"],
        cta="Watch the teaser now on the hoichoi app.",
        media_direction=MediaDirection(
            description="Dramatic overhead silhouette with cinematic lighting.",
            style="Moody thriller poster style",
            mood="Tense, atmospheric",
            aspect_ratio="1:1",
        ),
    )


@pytest.fixture
def instagram_spec() -> InstagramSpec:
    return InstagramSpec()


@pytest.fixture
def engine() -> ValidationEngine:
    return ValidationEngine()


@pytest.fixture
def validation_service() -> ValidationService:
    return ValidationService()


# --- Valid Content Tests ---

def test_valid_bengali_post_passes(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    result = engine.validate(valid_bengali_post)
    assert result.valid is True
    assert len(result.errors) == 0


def test_valid_english_post_passes(engine: ValidationEngine, valid_english_post: GeneratedInstagramPost):
    result = engine.validate(valid_english_post)
    assert result.valid is True
    assert len(result.errors) == 0


def test_valid_dict_content_passes(engine: ValidationEngine):
    data: dict[str, Any] = {
        "platform": "instagram",
        "hook": "Valid hook line",
        "caption": "A valid caption with sufficient detail.",
        "hashtags": ["#one", "#two", "#three", "#four", "#five"],
        "cta": "Link in bio",
        "media_direction": {
            "description": "Visual visual",
            "style": "Photo",
            "mood": "Calm",
            "aspect_ratio": "1:1",
        },
    }
    result = engine.validate(data)
    assert result.valid is True
    assert result.errors == []


# --- Caption Tests ---

@pytest.mark.parametrize("bad_caption", ["", "   ", "\n\t  ", None])
def test_empty_caption_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, bad_caption: str | None):
    data = valid_bengali_post.model_dump()
    data["caption"] = bad_caption
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "CAPTION_EMPTY" in codes
    err = next(e for e in result.errors if e.code == "CAPTION_EMPTY")
    assert err.field == "caption"
    assert err.expected == "Non-empty string"


def test_caption_exceeding_max_length_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["caption"] = "ক" * 2201  # Exceeds 2200 char limit
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "CAPTION_TOO_LONG" in codes
    err = next(e for e in result.errors if e.code == "CAPTION_TOO_LONG")
    assert err.field == "caption"
    assert err.actual == 2201
    assert err.expected == "<= 2200"


def test_caption_at_exact_max_length_passes(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["caption"] = "A" * 2200  # Exactly at the 2200 char limit
    result = engine.validate(data, platform=Platform.INSTAGRAM)
    assert result.valid is True


# --- Hook Tests ---

@pytest.mark.parametrize("bad_hook", ["", "   ", None])
def test_missing_hook_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, bad_hook: str | None):
    data = valid_bengali_post.model_dump()
    data["hook"] = bad_hook
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    assert any(e.code == "HOOK_EMPTY" and e.field == "hook" for e in result.errors)


# --- CTA Tests ---

@pytest.mark.parametrize("bad_cta", ["", "   ", None])
def test_missing_cta_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, bad_cta: str | None):
    data = valid_bengali_post.model_dump()
    data["cta"] = bad_cta
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    assert any(e.code == "CTA_MISSING" and e.field == "cta" for e in result.errors)


# --- Hashtags Tests ---

def test_too_few_hashtags_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = ["#one", "#two", "#three", "#four"]  # 4 tags, min is 5
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "HASHTAGS_TOO_FEW"), None)
    assert err is not None
    assert err.field == "hashtags"
    assert err.actual == 4
    assert err.expected == ">= 5"


def test_too_many_hashtags_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = [f"#tag{i}" for i in range(31)]  # 31 tags, max is 30
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "HASHTAGS_TOO_MANY"), None)
    assert err is not None
    assert err.field == "hashtags"
    assert err.actual == 31
    assert err.expected == "<= 30"


@pytest.mark.parametrize("count", [5, 15, 30])
def test_valid_hashtag_counts_pass(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, count: int):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = [f"#tag{i}" for i in range(count)]
    result = engine.validate(data, platform=Platform.INSTAGRAM)
    assert result.valid is True


def test_hashtag_missing_hash_prefix_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = ["#valid1", "nohash", "#valid3", "#valid4", "#valid5"]
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "HASHTAG_INVALID_FORMAT"), None)
    assert err is not None
    assert err.field == "hashtags[1]"
    assert err.actual == "nohash"


def test_hashtag_containing_whitespace_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = ["#valid1", "#tag with space", "#valid3", "#valid4", "#valid5"]
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "HASHTAG_INVALID_FORMAT"), None)
    assert err is not None
    assert err.field == "hashtags[1]"


def test_bare_hash_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = ["#valid1", "#", "#valid3", "#valid4", "#valid5"]
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    assert any(e.code == "HASHTAG_INVALID_FORMAT" for e in result.errors)


def test_missing_hashtags_field_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["hashtags"] = None
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    assert any(e.code == "HASHTAGS_MISSING" for e in result.errors)


# --- Media Tests ---

def test_missing_media_direction_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["media_direction"] = None
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    assert any(e.code == "MEDIA_DIRECTION_MISSING" and e.field == "media_direction" for e in result.errors)


@pytest.mark.parametrize("bad_ratio", ["3:1", "2:3", "9:9", "unknown"])
def test_unsupported_aspect_ratio_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, bad_ratio: str):
    data = valid_bengali_post.model_dump()
    data["media_direction"]["aspect_ratio"] = bad_ratio
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "UNSUPPORTED_ASPECT_RATIO"), None)
    assert err is not None
    assert err.field == "media_direction.aspect_ratio"
    assert err.actual == bad_ratio


@pytest.mark.parametrize("good_ratio", ["1:1", "4:5", "9:16", "16:9"])
def test_supported_aspect_ratios_pass(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, good_ratio: str):
    data = valid_bengali_post.model_dump()
    data["media_direction"]["aspect_ratio"] = good_ratio
    result = engine.validate(data, platform=Platform.INSTAGRAM)
    assert result.valid is True


@pytest.mark.parametrize("missing_field", ["description", "style", "mood"])
def test_missing_media_direction_field_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, missing_field: str):
    data = valid_bengali_post.model_dump()
    data["media_direction"][missing_field] = ""
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "MEDIA_FIELD_MISSING"), None)
    assert err is not None
    assert err.field == f"media_direction.{missing_field}"


def test_unsupported_media_type_fails(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["media_direction"]["media_type"] = "audio_podcast"
    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    err = next((e for e in result.errors if e.code == "UNSUPPORTED_MEDIA_TYPE"), None)
    assert err is not None
    assert err.actual == "audio_podcast"


@pytest.mark.parametrize("valid_type", ["image", "video", "carousel", "photo"])
def test_supported_media_types_pass(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost, valid_type: str):
    data = valid_bengali_post.model_dump()
    data["media_direction"]["media_type"] = valid_type
    result = engine.validate(data, platform=Platform.INSTAGRAM)
    assert result.valid is True


# --- Multiple Simultaneous Failures ---

def test_multiple_independent_failures_returned_together(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["caption"] = ""  # Error 1: CAPTION_EMPTY
    data["hashtags"] = ["#one", "badtag"]  # Errors: HASHTAGS_TOO_FEW, HASHTAG_INVALID_FORMAT
    data["cta"] = ""  # Error: CTA_MISSING
    data["media_direction"]["aspect_ratio"] = "invalid_ratio"  # Error: UNSUPPORTED_ASPECT_RATIO

    result = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result.valid is False
    error_codes = {e.code for e in result.errors}
    assert "CAPTION_EMPTY" in error_codes
    assert "HASHTAGS_TOO_FEW" in error_codes
    assert "HASHTAG_INVALID_FORMAT" in error_codes
    assert "CTA_MISSING" in error_codes
    assert "UNSUPPORTED_ASPECT_RATIO" in error_codes
    assert len(result.errors) >= 5


# --- Determinism and Consistency ---

def test_validation_is_deterministic(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    data = valid_bengali_post.model_dump()
    data["caption"] = "Short"
    data["hashtags"] = ["#one", "#two"]

    result_1 = engine.validate(data, platform=Platform.INSTAGRAM)
    result_2 = engine.validate(data, platform=Platform.INSTAGRAM)

    assert result_1.valid == result_2.valid
    assert len(result_1.errors) == len(result_2.errors)
    assert result_1.model_dump() == result_2.model_dump()


# --- Platform Specification and Engine Registry Tests ---

def test_unregistered_platform_raises_value_error(engine: ValidationEngine, valid_bengali_post: GeneratedInstagramPost):
    with pytest.raises(ValueError, match="No validation specification registered"):
        engine.validate(valid_bengali_post, platform=Platform.YOUTUBE)


def test_convenience_validate_post_function(valid_bengali_post: GeneratedInstagramPost):
    result = validate_post(valid_bengali_post, platform=Platform.INSTAGRAM)
    assert result.valid is True
    assert isinstance(result, ValidationResult)


# --- Service Boundary Integration Test (Mocked AI Output -> Validator -> Result) ---

def test_service_boundary_structured_output_to_validation_result(
    validation_service: ValidationService,
    valid_bengali_post: GeneratedInstagramPost,
):
    """Proves the boundary: structured output -> validation service -> deterministic result.

    This test confirms that the validation layer operates purely on structured data
    without any Gemini SDK, network, or database coupling.
    """
    result = validation_service.validate_post(valid_bengali_post, platform=Platform.INSTAGRAM)

    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.errors == []

    # Inject a violation
    invalid_post = valid_bengali_post.model_copy(update={"caption": ""})
    fail_result = validation_service.validate_post(invalid_post, platform=Platform.INSTAGRAM)

    assert isinstance(fail_result, ValidationResult)
    assert fail_result.valid is False
    assert len(fail_result.errors) == 1
    assert fail_result.errors[0].code == "CAPTION_EMPTY"
    assert fail_result.errors[0].field == "caption"
