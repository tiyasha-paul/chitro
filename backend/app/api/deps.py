"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ChannelAdapter, MockInstagramAdapter
from app.ai.gemini import GeminiProvider
from app.ai.provider import LLMProvider
from app.database import get_db_session
from app.services.analytics import AnalyticsService
from app.services.approval import ApprovalService
from app.services.campaign import CampaignService
from app.services.generation import GenerationService
from app.services.publishing import PublishingService
from app.services.reporting import ReportingService
from app.services.validation import ValidationService
from app.services.workflow import ContentWorkflowService

# Default module-level mock adapter instance
_default_instagram_adapter: ChannelAdapter = MockInstagramAdapter()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session from async sessionmaker."""
    async for session in get_db_session():
        yield session


def get_llm_provider() -> LLMProvider:
    """Provide LLM provider instance (can be overridden in tests)."""
    return GeminiProvider()


def get_channel_adapter() -> ChannelAdapter:
    """Provide ChannelAdapter instance (can be overridden in tests)."""
    return _default_instagram_adapter


def get_generation_service(
    provider: LLMProvider = Depends(get_llm_provider),
) -> GenerationService:
    """Provide GenerationService."""
    return GenerationService(provider=provider)


def get_validation_service() -> ValidationService:
    """Provide ValidationService."""
    return ValidationService()


def get_campaign_service() -> CampaignService:
    """Provide CampaignService."""
    return CampaignService()


def get_approval_service() -> ApprovalService:
    """Provide ApprovalService."""
    return ApprovalService()


def get_workflow_service(
    generation_service: GenerationService = Depends(get_generation_service),
    validation_service: ValidationService = Depends(get_validation_service),
) -> ContentWorkflowService:
    """Provide ContentWorkflowService."""
    return ContentWorkflowService(
        generation_service=generation_service,
        validation_service=validation_service,
    )


def get_publishing_service(
    adapter: ChannelAdapter = Depends(get_channel_adapter),
) -> PublishingService:
    """Provide PublishingService."""
    return PublishingService(default_adapter=adapter)


def get_analytics_service() -> AnalyticsService:
    """Provide AnalyticsService."""
    return AnalyticsService()


def get_reporting_service(
    provider: LLMProvider = Depends(get_llm_provider),
) -> ReportingService:
    """Provide ReportingService."""
    return ReportingService(provider=provider)
