"""Instagram-specific platform specification and validation rules."""

from typing import Any

from app.domain.enums import Platform
from app.validation.platform_spec import PlatformSpec, ValidationErrorDetail


def _get_field(obj: Any, field_name: str, default: Any = None) -> Any:
    """Safely extract a field from a Pydantic model, dictionary, or generic object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


class InstagramSpec(PlatformSpec):
    """Deterministic validation specification for Instagram content.

    Encodes standard Instagram constraints and Chitro campaign rules:
    - Caption: max 2,200 characters, non-empty.
    - Hook: non-empty required opening hook.
    - CTA: non-empty required call-to-action.
    - Hashtags: 5 to 30 hashtags, each starting with '#' and containing no whitespace.
    - Media Direction: non-empty description, style, mood, and supported aspect ratio.
    """

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def max_caption_length(self) -> int:
        return 2200

    @property
    def min_hashtags(self) -> int:
        return 5

    @property
    def max_hashtags(self) -> int:
        return 30

    @property
    def allowed_aspect_ratios(self) -> set[str]:
        return {"1:1", "4:5", "9:16", "16:9"}

    @property
    def allowed_media_types(self) -> set[str]:
        return {"image", "video", "carousel", "photo"}

    @property
    def require_cta(self) -> bool:
        return True

    @property
    def require_hook(self) -> bool:
        return True

    @property
    def required_media_fields(self) -> set[str]:
        return {"description", "style", "mood", "aspect_ratio"}

    def validate(self, content: Any) -> list[ValidationErrorDetail]:
        """Validate content against Instagram constraints and return all violations."""
        errors: list[ValidationErrorDetail] = []

        # 1. Caption validation
        caption = _get_field(content, "caption")
        if caption is None or (isinstance(caption, str) and not caption.strip()):
            errors.append(
                ValidationErrorDetail(
                    field="caption",
                    code="CAPTION_EMPTY",
                    message="Caption is missing or empty.",
                    actual=None if caption is None else '""',
                    expected="Non-empty string",
                )
            )
        elif isinstance(caption, str) and len(caption) > self.max_caption_length:
            errors.append(
                ValidationErrorDetail(
                    field="caption",
                    code="CAPTION_TOO_LONG",
                    message=f"Caption length ({len(caption)}) exceeds maximum of {self.max_caption_length} characters.",
                    actual=len(caption),
                    expected=f"<= {self.max_caption_length}",
                )
            )

        # 2. Hook validation
        if self.require_hook:
            hook = _get_field(content, "hook")
            if hook is None or (isinstance(hook, str) and not hook.strip()):
                errors.append(
                    ValidationErrorDetail(
                        field="hook",
                        code="HOOK_EMPTY",
                        message="Hook line is missing or empty.",
                        actual=None if hook is None else '""',
                        expected="Non-empty string",
                    )
                )

        # 3. CTA validation
        if self.require_cta:
            cta = _get_field(content, "cta")
            if cta is None or (isinstance(cta, str) and not cta.strip()):
                errors.append(
                    ValidationErrorDetail(
                        field="cta",
                        code="CTA_MISSING",
                        message="Call-to-action (CTA) is required.",
                        actual=None if cta is None else '""',
                        expected="Non-empty string",
                    )
                )

        # 4. Hashtags validation
        hashtags = _get_field(content, "hashtags")
        if hashtags is None or not isinstance(hashtags, list):
            errors.append(
                ValidationErrorDetail(
                    field="hashtags",
                    code="HASHTAGS_MISSING",
                    message="Hashtags list is missing or not a list.",
                    actual=type(hashtags).__name__ if hashtags is not None else None,
                    expected=f"list[str] with {self.min_hashtags} to {self.max_hashtags} tags",
                )
            )
        else:
            # Count check
            tag_count = len(hashtags)
            if tag_count < self.min_hashtags:
                errors.append(
                    ValidationErrorDetail(
                        field="hashtags",
                        code="HASHTAGS_TOO_FEW",
                        message=f"Hashtag count ({tag_count}) is below minimum of {self.min_hashtags}.",
                        actual=tag_count,
                        expected=f">= {self.min_hashtags}",
                    )
                )
            elif tag_count > self.max_hashtags:
                errors.append(
                    ValidationErrorDetail(
                        field="hashtags",
                        code="HASHTAGS_TOO_MANY",
                        message=f"Hashtag count ({tag_count}) exceeds maximum of {self.max_hashtags}.",
                        actual=tag_count,
                        expected=f"<= {self.max_hashtags}",
                    )
                )

            # Format check on individual tags
            for idx, tag in enumerate(hashtags):
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(
                        ValidationErrorDetail(
                            field=f"hashtags[{idx}]",
                            code="HASHTAG_INVALID_FORMAT",
                            message=f"Hashtag at index {idx} must be a non-empty string.",
                            actual=tag,
                            expected="String starting with '#'",
                        )
                    )
                elif not tag.startswith("#"):
                    errors.append(
                        ValidationErrorDetail(
                            field=f"hashtags[{idx}]",
                            code="HASHTAG_INVALID_FORMAT",
                            message=f"Hashtag '{tag}' must start with '#'.",
                            actual=tag,
                            expected="Must start with '#'",
                        )
                    )
                elif len(tag.strip()) == 1:
                    errors.append(
                        ValidationErrorDetail(
                            field=f"hashtags[{idx}]",
                            code="HASHTAG_INVALID_FORMAT",
                            message=f"Hashtag at index {idx} cannot be '#' alone.",
                            actual=tag,
                            expected="Hashtag text following '#'",
                        )
                    )
                elif any(ch.isspace() for ch in tag):
                    errors.append(
                        ValidationErrorDetail(
                            field=f"hashtags[{idx}]",
                            code="HASHTAG_INVALID_FORMAT",
                            message=f"Hashtag '{tag}' contains invalid whitespace.",
                            actual=tag,
                            expected="No whitespace in hashtag",
                        )
                    )

        # 5. Media Direction validation
        media = _get_field(content, "media_direction")
        if media is None:
            errors.append(
                ValidationErrorDetail(
                    field="media_direction",
                    code="MEDIA_DIRECTION_MISSING",
                    message="Media direction is required.",
                    actual=None,
                    expected="MediaDirection object or dictionary",
                )
            )
        else:
            # Required subfields
            for req_field in sorted(self.required_media_fields):
                val = _get_field(media, req_field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append(
                        ValidationErrorDetail(
                            field=f"media_direction.{req_field}",
                            code="MEDIA_FIELD_MISSING",
                            message=f"Media direction field '{req_field}' is missing or empty.",
                            actual=val,
                            expected="Non-empty string",
                        )
                    )

            # Aspect ratio check
            aspect_ratio = _get_field(media, "aspect_ratio")
            if aspect_ratio is not None and aspect_ratio not in self.allowed_aspect_ratios:
                errors.append(
                    ValidationErrorDetail(
                        field="media_direction.aspect_ratio",
                        code="UNSUPPORTED_ASPECT_RATIO",
                        message=f"Aspect ratio '{aspect_ratio}' is not supported for Instagram.",
                        actual=aspect_ratio,
                        expected=sorted(list(self.allowed_aspect_ratios)),
                    )
                )

            # Media type/format check (if specified on media_direction or content)
            media_type = (
                _get_field(media, "media_type")
                or _get_field(media, "media_format")
                or _get_field(media, "type")
                or _get_field(content, "media_type")
                or _get_field(content, "media_format")
            )
            if media_type is not None:
                norm_type = str(media_type).lower().strip()
                if norm_type not in self.allowed_media_types:
                    errors.append(
                        ValidationErrorDetail(
                            field="media_direction.media_type",
                            code="UNSUPPORTED_MEDIA_TYPE",
                            message=f"Media type '{media_type}' is not supported for Instagram.",
                            actual=media_type,
                            expected=sorted(list(self.allowed_media_types)),
                        )
                    )

        return errors
