"""Campaign and generation API endpoints."""

import uuid
from typing import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_campaign_service, get_db, get_workflow_service
from app.schemas.campaigns import CampaignResponse, CreateCampaignRequest
from app.schemas.posts import GeneratePostRequest, PlatformPostResponse
from app.services.campaign import CampaignService
from app.services.workflow import ContentWorkflowService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


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
) -> CampaignResponse:
    """Create and persist a new Campaign from a ContentBrief."""
    campaign = await campaign_service.create_campaign(db, request)
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
) -> CampaignResponse:
    """Retrieve campaign information including all associated posts."""
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
) -> PlatformPostResponse:
    """Generate, validate, and transition a platform post.

    Transitions:
        DRAFT -> GENERATED -> VALIDATED -> PENDING_APPROVAL (valid)
        DRAFT -> GENERATED -> VALIDATION_FAILED (invalid)
    """
    post = await workflow_service.generate_post(
        db=db,
        campaign_id=campaign_id,
        platform=request.platform,
        language=request.language,
    )
    return PlatformPostResponse.model_validate(post)
