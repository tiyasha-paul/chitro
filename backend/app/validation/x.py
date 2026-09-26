"""Deterministic validation rules for X content."""

from app.domain.enums import Platform
from app.validation.instagram import InstagramSpec


class XSpec(InstagramSpec):
    """X keeps shared content fields while enforcing concise social copy."""

    @property
    def platform(self) -> Platform:
        return Platform.X

    @property
    def max_caption_length(self) -> int:
        return 280

    @property
    def min_hashtags(self) -> int:
        return 0

    @property
    def max_hashtags(self) -> int:
        return 2
