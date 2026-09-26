"""Post retrieval, approval, rejection, regeneration, scheduling, and publishing endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_analytics_service,
    get_approval_service,
    get_db,
    get_publishing_service,
    get_workflow_service,
)
from app.schemas.analytics import MetricSnapshotCreate, MetricSnapshotResponse
from app.schemas.posts import (
    PlatformPostResponse,
    RejectPostRequest,
    SchedulePostRequest,
)
from app.services.analytics import AnalyticsService
from app.services.approval import ApprovalService
from app.services.publishing import PublishingService
from app.services.workflow import ContentWorkflowService

router = APIRouter(prefix="/posts", tags=["Posts & Workflow Lifecycle"])


@router.get(
    "/{post_id}",
    response_model=PlatformPostResponse,
    summary="Get platform post details and lifecycle status",
)
async def get_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workflow_service: ContentWorkflowService = Depends(get_workflow_service),
) -> PlatformPostResponse:
    """Retrieve full post details, content, validation status, and audit history."""
    post = await workflow_service.get_post(db, post_id)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/approve",
    response_model=PlatformPostResponse,
    summary="Approve a post currently pending approval",
)
async def approve_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> PlatformPostResponse:
    """Approve a post in PENDING_APPROVAL status.

    Transitions: PENDING_APPROVAL -> APPROVED
    """
    post = await approval_service.approve_post(db, post_id)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/reject",
    response_model=PlatformPostResponse,
    summary="Reject a post with human feedback",
)
async def reject_post(
    post_id: uuid.UUID,
    request: RejectPostRequest,
    db: AsyncSession = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> PlatformPostResponse:
    """Reject a post in PENDING_APPROVAL status with a mandatory rejection reason.

    Transitions: PENDING_APPROVAL -> REJECTED
    """
    post = await approval_service.reject_post(db, post_id, request.reason)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/regenerate",
    response_model=PlatformPostResponse,
    summary="Regenerate a rejected or failed post",
)
async def regenerate_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    workflow_service: ContentWorkflowService = Depends(get_workflow_service),
) -> PlatformPostResponse:
    """Regenerate a post in REJECTED or VALIDATION_FAILED status.

    Preserves current content into generation_history audit log, increments
    attempt counter, and applies previous rejection feedback to prompt.
    """
    post = await workflow_service.regenerate_post(db, post_id)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/schedule",
    response_model=PlatformPostResponse,
    summary="Schedule an approved post for future publication",
)
async def schedule_post(
    post_id: uuid.UUID,
    request: SchedulePostRequest,
    db: AsyncSession = Depends(get_db),
    publishing_service: PublishingService = Depends(get_publishing_service),
) -> PlatformPostResponse:
    """Schedule an approved post for publication at a future timestamp.

    Transitions: APPROVED -> SCHEDULED
    """
    post = await publishing_service.schedule_post(db, post_id, request.scheduled_at)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/publish",
    response_model=PlatformPostResponse,
    summary="Publish an approved or scheduled post to the platform",
)
async def publish_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    publishing_service: PublishingService = Depends(get_publishing_service),
) -> PlatformPostResponse:
    """Publish a post immediately to the platform adapter.

    Transitions:
    - If APPROVED: APPROVED -> SCHEDULED -> PUBLISHED
    - If SCHEDULED: SCHEDULED -> PUBLISHED
    - If already PUBLISHED: Idempotent (returns existing post without re-calling adapter)
    """
    post = await publishing_service.publish_post(db, post_id)
    return PlatformPostResponse.model_validate(post)


@router.post(
    "/{post_id}/metrics",
    response_model=MetricSnapshotResponse,
    status_code=201,
    summary="Record a metric snapshot for a published post",
)
async def record_metric_snapshot(
    post_id: uuid.UUID,
    request: MetricSnapshotCreate,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> MetricSnapshotResponse:
    """Record performance metrics (reach, impressions, likes, etc.) for a published post.

    Requires:
    - Post must exist (404)
    - Post must be in PUBLISHED status (409)
    """
    snapshot = await analytics_service.record_snapshot(db, post_id, request)
    return MetricSnapshotResponse.model_validate(snapshot)


@router.get(
    "/{post_id}/metrics",
    response_model=list[MetricSnapshotResponse],
    summary="Retrieve all metric snapshots for a post",
)
async def get_metric_snapshots(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> list[MetricSnapshotResponse]:
    """Retrieve full chronological history of metric snapshots for a post."""
    snapshots = await analytics_service.get_snapshots(db, post_id)
    return [MetricSnapshotResponse.model_validate(s) for s in snapshots]
