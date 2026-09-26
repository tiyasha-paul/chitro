"""Deterministic validation engine for multi-platform content."""

import logging
from typing import Any

from app.domain.enums import Platform
from app.validation.instagram import InstagramSpec
from app.validation.platform_spec import PlatformSpec, ValidationResult

logger = logging.getLogger(__name__)


def _extract_platform(content: Any) -> Platform | None:
    """Attempt to detect the platform from a content object or dictionary."""
    val = None
    if isinstance(content, dict):
        val = content.get("platform")
    else:
        val = getattr(content, "platform", None)

    if isinstance(val, Platform):
        return val
    if isinstance(val, str):
        try:
            return Platform(val)
        except ValueError:
            return None
    return None


class ValidationEngine:
    """Registry and execution engine for deterministic platform specifications."""

    def __init__(self, specs: dict[Platform, PlatformSpec] | None = None) -> None:
        self._specs: dict[Platform, PlatformSpec] = specs if specs is not None else {
            Platform.INSTAGRAM: InstagramSpec(),
        }

    def register_spec(self, platform: Platform, spec: PlatformSpec) -> None:
        """Register or override a platform specification."""
        self._specs[platform] = spec

    def get_spec(self, platform: Platform) -> PlatformSpec:
        """Retrieve the specification for a platform, raising ValueError if not found."""
        spec = self._specs.get(platform)
        if spec is None:
            raise ValueError(f"No validation specification registered for platform: {platform.value}")
        return spec

    def validate(
        self,
        content: Any,
        platform: Platform | None = None,
        spec: PlatformSpec | None = None,
    ) -> ValidationResult:
        """Deterministically validate generated content against a platform specification.

        Args:
            content: The structured content to validate (e.g. GeneratedInstagramPost, dict).
            platform: Target platform. If omitted, inferred from content or spec.
            spec: Explicit PlatformSpec instance to use. If omitted, looked up by platform.

        Returns:
            ValidationResult with boolean `valid` and structured `errors` list.

        Raises:
            ValueError: If neither spec nor platform can be determined.
        """
        resolved_spec: PlatformSpec
        if spec is not None:
            resolved_spec = spec
        else:
            target_platform = platform or _extract_platform(content)
            if target_platform is None:
                raise ValueError(
                    "Target platform must be specified or inferable from content."
                )
            resolved_spec = self.get_spec(target_platform)

        errors = resolved_spec.validate(content)
        is_valid = len(errors) == 0

        logger.debug(
            "Validation for %s: valid=%s, error_count=%d",
            resolved_spec.platform.value,
            is_valid,
            len(errors),
        )

        return ValidationResult(valid=is_valid, errors=errors)


# Module-level default engine instance
_default_engine = ValidationEngine()


def validate_post(
    content: Any,
    platform: Platform = Platform.INSTAGRAM,
) -> ValidationResult:
    """Convenience function to validate content using the default engine."""
    return _default_engine.validate(content, platform=platform)
