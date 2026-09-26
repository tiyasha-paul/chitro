"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ChannelAdapter, MockInstagramAdapter
from app.ai.gemini import GeminiProvider
from app.ai.provider import LLMProvider
from app.database import get_db_session
from app.domain.models import Campaign, PlatformPost, User, Workspace, WorkspaceMember
from app.services.analytics import AnalyticsService
from app.services.approval import ApprovalService
from app.services.campaign import CampaignService
from app.services.generation import GenerationService
from app.services.publishing import PublishingService
from app.services.reporting import ReportingService
from app.services.auth import AuthService, InvalidTokenError, decode_access_token
from app.services.validation import ValidationService
from app.services.workflow import ContentWorkflowService
from app.services.workspace import WorkspaceService

# Default module-level mock adapter instance
_default_instagram_adapter: ChannelAdapter = MockInstagramAdapter()
_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_auth_service() -> AuthService:
    """Provide authentication service."""
    return AuthService()


def get_workspace_service() -> WorkspaceService:
    """Provide WorkspaceService."""
    return WorkspaceService()


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    """Resolve a bearer token when one is provided, preserving legacy unauthenticated APIs."""
    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials") from None
    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return user


async def get_current_user(
    current_user: User | None = Depends(get_optional_current_user),
) -> User:
    """Require and return the user represented by a valid bearer token."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return current_user


async def get_selected_workspace(
    current_user: User = Depends(get_current_user),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> Workspace:
    """Resolve an authenticated user's selected workspace.

    Clients should send ``X-Workspace-ID``. During the frontend rollout, an
    omitted header deliberately falls back to the user's earliest membership;
    this compatibility behavior is centralized here and should be removed once
    all clients send an explicit selection.
    """
    if x_workspace_id is None:
        workspace = await auth_service.get_workspace_for_user(db, current_user.id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace membership required")
        return workspace

    try:
        workspace_id = uuid.UUID(x_workspace_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="X-Workspace-ID must be a valid UUID") from None

    membership = await auth_service.get_workspace_membership(db, current_user.id, workspace_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace membership required")
    return membership.workspace


async def get_selected_workspace_post(
    post_id: uuid.UUID,
    selected_workspace: Workspace = Depends(get_selected_workspace),
    db: AsyncSession = Depends(get_db),
) -> PlatformPost:
    """Load a post only when its campaign belongs to the selected workspace."""
    stmt = (
        select(PlatformPost)
        .join(Campaign, PlatformPost.campaign_id == Campaign.id)
        .where(PlatformPost.id == post_id, Campaign.workspace_id == selected_workspace.id)
    )
    post = (await db.execute(stmt)).scalar_one_or_none()
    if post is None:
        # A 404 prevents callers from using post IDs to discover another
        # workspace's resources.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def get_workspace_membership_for_path(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> WorkspaceMember:
    """Require membership in the workspace identified by the route parameter."""
    membership = await auth_service.get_workspace_membership(db, current_user.id, workspace_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace membership required")
    return membership


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
