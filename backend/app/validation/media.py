"""Deterministic validation for concrete media metadata at publishing boundaries."""

import uuid
from fractions import Fraction
from typing import Any

from pydantic import ValidationError

from app.domain.enums import Platform
from app.domain.exceptions import MediaValidationError
from app.schemas.media import MediaAssetSpec
from app.validation.engine import ValidationEngine
from app.validation.platform_spec import ValidationErrorDetail, ValidationResult

_MOCK_DIMENSIONS = {
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


def build_mock_media_asset(aspect_ratio: str | None, post_id: uuid.UUID) -> dict[str, Any]:
    """Create deterministic metadata for Chitro's no-storage mock publishing path."""
    width, height = _MOCK_DIMENSIONS.get(aspect_ratio or "", _MOCK_DIMENSIONS["1:1"])
    return MediaAssetSpec(
        media_type="image",
        mime_type="image/jpeg",
        width=width,
        height=height,
        size_bytes=1_048_576,
        asset_url=f"mock://generated/{post_id}.jpg",
    ).model_dump()


def validate_media_asset(media_spec: Any, platform: Platform) -> ValidationResult:
    """Validate a structured media asset using the registered platform specification."""
    spec = ValidationEngine().get_spec(platform)
    try:
        media = MediaAssetSpec.model_validate(media_spec)
    except ValidationError as exc:
        errors = [
            ValidationErrorDetail(
                field=f"media_spec.{'.'.join(str(part) for part in error['loc'])}",
                code="MEDIA_METADATA_INVALID",
                message=error["msg"],
                actual=error.get("input"),
                expected="Required structured media metadata",
            )
            for error in exc.errors()
        ]
        return ValidationResult.failure(errors)

    errors: list[ValidationErrorDetail] = []
    if media.media_type not in spec.allowed_media_types:
        errors.append(ValidationErrorDetail(field="media_spec.media_type", code="UNSUPPORTED_MEDIA_TYPE", message="Media type is not supported for this platform.", actual=media.media_type, expected=sorted(spec.allowed_media_types)))
    if media.mime_type not in spec.allowed_mime_types:
        errors.append(ValidationErrorDetail(field="media_spec.mime_type", code="UNSUPPORTED_MIME_TYPE", message="MIME type is not supported for this platform.", actual=media.mime_type, expected=sorted(spec.allowed_mime_types)))

    expected_mime_prefix = "video/" if media.media_type == "video" else "image/"
    if media.mime_type not in spec.allowed_mime_types or not media.mime_type.startswith(expected_mime_prefix):
        errors.append(ValidationErrorDetail(field="media_spec.mime_type", code="MEDIA_TYPE_MIME_MISMATCH", message="MIME type does not match the declared media type.", actual=media.mime_type, expected=expected_mime_prefix))

    actual_ratio = Fraction(media.width, media.height)
    allowed_ratios = {ratio: Fraction(*(int(part) for part in ratio.split(":"))) for ratio in spec.allowed_aspect_ratios}
    if actual_ratio not in allowed_ratios.values():
        errors.append(ValidationErrorDetail(field="media_spec.width", code="UNSUPPORTED_ASPECT_RATIO", message="Asset dimensions do not produce an allowed aspect ratio.", actual=f"{media.width}:{media.height}", expected=sorted(spec.allowed_aspect_ratios)))
    if media.size_bytes > spec.max_media_size_bytes:
        errors.append(ValidationErrorDetail(field="media_spec.size_bytes", code="MEDIA_SIZE_EXCEEDED", message="Asset size exceeds the platform limit.", actual=media.size_bytes, expected=f"<= {spec.max_media_size_bytes}"))

    return ValidationResult.failure(errors) if errors else ValidationResult.success()


def ensure_valid_media_asset(media_spec: Any, platform: Platform) -> MediaAssetSpec:
    """Return valid parsed metadata or raise a structured domain error."""
    result = validate_media_asset(media_spec, platform)
    if not result.valid:
        raise MediaValidationError([error.model_dump() for error in result.errors])
    return MediaAssetSpec.model_validate(media_spec)
