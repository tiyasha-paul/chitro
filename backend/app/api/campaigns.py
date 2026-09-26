"""Campaign and generation API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_analytics_service,
    get_auth_service,
    get_campaign_service,
    get_optional_current_user,
    get_db,
    get_workflow_service,
    get_reporting_service,
)
from app.schemas.analytics import AnalyticsComparisonResponse, InsightResponse
from app.schemas.campaigns import CampaignResponse, CreateCampaignRequest
from app.schemas.posts import GeneratePostRequest, PlatformPostResponse
from app.schemas.reports import PerformanceReport, WeeklyReportRequest
from app.services.analytics import AnalyticsService
from app.services.auth import AuthService
from app.services.campaign import CampaignService
from app.services.workflow import ContentWorkflowService
from app.services.reporting import ReportingService
from app.domain.models import User
from app.domain.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/campaigns", tags=["Campaigns & Analytics"])


async def _ensure_campaign_access(
    campaign_id: uuid.UUID,
    db: AsyncSession,
    current_user: User | None,
    auth_service: AuthService,
    campaign_service: CampaignService,
) -> None:
    """Confirm that an authenticated request only operates on its workspace's campaign."""
    if current_user is None:
        return
    workspace = await auth_service.get_workspace_for_user(db, current_user.id)
    if workspace is None:
        # Treat an incomplete identity record as inaccessible rather than falling back to legacy access.
        raise ResourceNotFoundError("Campaign", str(campaign_id))
    await campaign_service.get_campaign(db, campaign_id, workspace_id=workspace.id)


@router.get(
    "",
    response_model=list[CampaignResponse],
    summary="List campaigns in the current workspace",
)
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[CampaignResponse]:
    """List campaigns, scoped to the caller's workspace when authenticated."""
    workspace = await auth_service.get_workspace_for_user(db, current_user.id) if current_user else None
    campaigns = await campaign_service.list_campaigns(db, workspace_id=workspace.id if workspace else None)
    return [CampaignResponse.model_validate(campaign) for campaign in campaigns]


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new campaign from a brief",
)
async def create_campaign(
    request: CreateCampaignRequest,
    db: AsyncSession = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> CampaignResponse:
    """Create and persist a new Campaign from a ContentBrief."""
    workspace = await auth_service.get_workspace_for_user(db, current_user.id) if current_user else None
    campaign = await campaign_service.create_campaign(db, request, workspace_id=workspace.id if workspace else None)
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        objective=campaign.objective,
        target_audience=campaign.target_audience,
        brief_context=campaign.brief_context,
        brief_payload=campaign.brief_payload,
        previous_insights=campaign.previous_insights,
        created_at=campaign.created_at,
        posts=[],
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get campaign details with generated posts",
)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    campaign_service: CampaignService = Depends(get_campaign_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> CampaignResponse:
    """Retrieve campaign information including all associated posts."""
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    campaign = await campaign_service.get_campaign(db, campaign_id)
    return CampaignResponse.model_validate(campaign)


@router.post(
    "/{campaign_id}/posts/generate",
    response_model=PlatformPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate platform post from campaign brief",
)
async def generate_post(
    campaign_id: uuid.UUID,
    request: GeneratePostRequest = GeneratePostRequest(),
    db: AsyncSession = Depends(get_db),
    workflow_service: ContentWorkflowService = Depends(get_workflow_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> PlatformPostResponse:
    """Generate, validate, and transition a platform post.

    Transitions:
        DRAFT -> GENERATED -> VALIDATED -> PENDING_APPROVAL (valid)
        DRAFT -> GENERATED -> VALIDATION_FAILED (invalid)
    """
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    post = await workflow_service.generate_post(
        db=db,
        campaign_id=campaign_id,
        platform=request.platform,
        language=request.language,
    )
    return PlatformPostResponse.model_validate(post)


@router.get(
    "/{campaign_id}/analytics/comparison",
    response_model=AnalyticsComparisonResponse,
    summary="Perform like-for-like cross-platform metric comparison",
)
async def get_campaign_comparison(
    campaign_id: uuid.UUID,
    window: Optional[str] = Query("latest", description="Comparison window timing, e.g. 'latest' or '24h'"),
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> AnalyticsComparisonResponse:
    """Compare performance across published posts for this campaign.

    Normalizes derived metrics (such as engagement rate) while preserving raw platform counts.
    Does not produce subjective 'winner' evaluations.
    """
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    return await analytics_service.get_campaign_comparison(db, campaign_id, window=window)


@router.post(
    "/{campaign_id}/insights/generate",
    response_model=list[InsightResponse],
    summary="Generate deterministic evidence-backed insights from published metrics",
)
async def generate_campaign_insights(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> list[InsightResponse]:
    """Derive verifiable insights from published post performance and update Campaign.previous_insights."""
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    insights = await analytics_service.generate_campaign_insights(db, campaign_id)
    return [InsightResponse.model_validate(ins) for ins in insights]


@router.get(
    "/{campaign_id}/insights",
    response_model=list[InsightResponse],
    summary="List stored insights for a campaign",
)
async def get_campaign_insights(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> list[InsightResponse]:
    """Retrieve all persisted insights for this campaign."""
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    insights = await analytics_service.get_campaign_insights(db, campaign_id)
    return [InsightResponse.model_validate(ins) for ins in insights]


@router.post(
    "/{campaign_id}/reports/weekly",
    response_model=PerformanceReport,
    summary="Generate an evidence-backed weekly performance report",
)
async def generate_weekly_report(
    campaign_id: uuid.UUID,
    request: WeeklyReportRequest = WeeklyReportRequest(),
    db: AsyncSession = Depends(get_db),
    reporting_service: ReportingService = Depends(get_reporting_service),
    current_user: User | None = Depends(get_optional_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    campaign_service: CampaignService = Depends(get_campaign_service),
) -> PerformanceReport:
    """Generate a deterministic-citation-validated performance report."""
    await _ensure_campaign_access(campaign_id, db, current_user, auth_service, campaign_service)
    return await reporting_service.generate_weekly_report(
        db=db,
        campaign_id=campaign_id,
        start=request.start,
        end=request.end,
    )
