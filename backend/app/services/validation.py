"""Validation service orchestrating deterministic platform validation."""

from typing import Any

from app.domain.enums import Platform
from app.validation.engine import ValidationEngine
from app.validation.platform_spec import ValidationResult


class ValidationService:
    """Service boundary for validating generated content against platform specifications."""

    def __init__(self, engine: ValidationEngine | None = None) -> None:
        self._engine = engine or ValidationEngine()

    def validate_post(
        self,
        content: Any,
        platform: Platform = Platform.INSTAGRAM,
    ) -> ValidationResult:
        """Validate content deterministically against the target platform specification."""
        return self._engine.validate(content=content, platform=platform)
