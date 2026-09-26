"""Platform-specific generation strategies.

Each strategy provides content rules, system prompt fragments, and
the structured output schema for a particular platform.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.domain.enums import Platform


class PlatformStrategy(ABC):
    """Abstract strategy for platform-specific content generation."""

    @abstractmethod
    def platform(self) -> Platform:
        """Which platform this strategy serves."""
        ...

    @abstractmethod
    def content_rules(self) -> dict[str, Any]:
        """Platform-specific content rules and constraints."""
        ...

    @abstractmethod
    def system_prompt_fragment(self) -> str:
        """Platform-specific instructions for the system prompt."""
        ...

    @abstractmethod
    def output_schema(self) -> type[BaseModel]:
        """Pydantic model class for structured output from this platform."""
        ...


class InstagramStrategy(PlatformStrategy):
    """Generation strategy for Instagram posts."""

    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    def content_rules(self) -> dict[str, Any]:
        return {
            "platform": "Instagram",
            "caption_length": "150–2200 characters",
            "hashtag_range": "5–30 hashtags",
            "tone": "Visual-first, aspirational, conversational",
            "cta_style": "Soft CTAs (link in bio, swipe, comment)",
            "media_format": "Square (1:1) or Portrait (4:5) image",
            "content_structure": "Hook line → story/context → CTA → hashtags",
            "audience_behaviour": "Mobile-first scroll, short attention span",
        }

    def system_prompt_fragment(self) -> str:
        return (
            "You are an expert Instagram content strategist. "
            "Create engaging Instagram posts optimised for reach and engagement. "
            "Always follow the hook → story → CTA → hashtags structure. "
            "Captions should be scroll-stopping and emotionally resonant. "
            "Hashtags must be a mix of niche and broad-reach tags relevant to the content."
        )

    def output_schema(self) -> type[BaseModel]:
        from app.schemas.content import GeneratedInstagramPost
        return GeneratedInstagramPost
