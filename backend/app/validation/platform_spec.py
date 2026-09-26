"""Abstract platform specification and validation result schemas."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import Platform


class ValidationErrorDetail(BaseModel):
    """Structured detail of a single platform validation rule violation."""

    field: str = Field(..., description="Field that failed validation")
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable explanation of failure")
    actual: Any = Field(default=None, description="Actual value or measured property")
    expected: Any = Field(default=None, description="Expected constraint or threshold")


class ValidationResult(BaseModel):
    """Outcome of platform validation."""

    valid: bool = Field(..., description="True if all platform rules passed")
    errors: list[ValidationErrorDetail] = Field(
        default_factory=list, description="List of violations found"
    )

    @classmethod
    def success(cls) -> "ValidationResult":
        """Convenience constructor for a passed validation."""
        return cls(valid=True, errors=[])

    @classmethod
    def failure(cls, errors: list[ValidationErrorDetail]) -> "ValidationResult":
        """Convenience constructor for a failed validation."""
        return cls(valid=False, errors=errors)


class PlatformSpec(ABC):
    """Abstract specification defining deterministic constraints for a platform."""

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """The platform this specification applies to."""
        ...

    @property
    @abstractmethod
    def max_caption_length(self) -> int:
        """Maximum character length for the caption."""
        ...

    @property
    @abstractmethod
    def min_hashtags(self) -> int:
        """Minimum number of hashtags required."""
        ...

    @property
    @abstractmethod
    def max_hashtags(self) -> int:
        """Maximum number of hashtags allowed."""
        ...

    @property
    @abstractmethod
    def allowed_aspect_ratios(self) -> set[str]:
        """Set of allowed aspect ratios (e.g. {'1:1', '4:5', '9:16', '16:9'})."""
        ...

    @property
    @abstractmethod
    def allowed_media_types(self) -> set[str]:
        """Set of allowed media types/formats (e.g. {'image', 'video', 'carousel', 'photo'})."""
        ...

    @property
    @abstractmethod
    def allowed_mime_types(self) -> set[str]:
        """Set of MIME types accepted by the platform adapter."""
        ...

    @property
    @abstractmethod
    def max_media_size_bytes(self) -> int:
        """Maximum accepted size of one media asset in bytes."""
        ...

    @property
    @abstractmethod
    def require_cta(self) -> bool:
        """Whether a call-to-action is mandatory."""
        ...

    @property
    @abstractmethod
    def require_hook(self) -> bool:
        """Whether an opening hook line is mandatory."""
        ...

    @property
    @abstractmethod
    def required_media_fields(self) -> set[str]:
        """Fields that must be populated in media_direction."""
        ...

    @abstractmethod
    def validate(self, content: Any) -> list[ValidationErrorDetail]:
        """Run all deterministic validation rules against content.

        Args:
            content: A generated post model, dict, or object with post attributes.

        Returns:
            A list of ValidationErrorDetail objects (empty if valid).
        """
        ...
