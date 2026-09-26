"""Content generation orchestration service."""

import logging
from typing import Any

from pydantic import BaseModel

from app.ai.platform_strategy import InstagramStrategy, PlatformStrategy, XStrategy
from app.ai.prompts import build_generation_prompt, build_system_instruction
from app.ai.provider import LLMProvider
from app.domain.enums import Language, Platform
from app.schemas.briefs import ContentBrief

logger = logging.getLogger(__name__)

# Registry of platform strategies
_STRATEGY_REGISTRY: dict[Platform, PlatformStrategy] = {
    Platform.INSTAGRAM: InstagramStrategy(),
    Platform.X: XStrategy(),
}


class GenerationService:
    """Orchestrates content generation: brief -> strategy -> prompt -> LLM -> output."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def _get_strategy(self, platform: Platform) -> PlatformStrategy:
        strategy = _STRATEGY_REGISTRY.get(platform)
        if strategy is None:
            raise ValueError(f"No generation strategy registered for {platform.value}")
        return strategy

    async def generate_post(
        self,
        *,
        brief: ContentBrief,
        platform: Platform,
        previous_insights: list[dict[str, Any]] | None = None,
        rejection_reason: str | None = None,
    ) -> BaseModel:
        """Generate a platform-specific post from a content brief.

        Returns:
            A Pydantic model instance matching the platform's output schema.
        """
        strategy = self._get_strategy(platform)

        system_instruction = build_system_instruction(
            strategy=strategy,
            language=brief.language,
        )
        prompt = build_generation_prompt(
            brief=brief,
            strategy=strategy,
            previous_insights=previous_insights,
            rejection_reason=rejection_reason,
        )

        logger.info(
            "Generating %s post for '%s' in %s",
            platform.value,
            brief.title,
            brief.language.value,
        )

        result = await self._provider.generate_structured(
            prompt=prompt,
            system_instruction=system_instruction,
            output_schema=strategy.output_schema(),
        )

        logger.info("Generation complete for '%s'", brief.title)
        return result
