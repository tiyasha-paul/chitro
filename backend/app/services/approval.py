"""Approval service for human review of generated content."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PostStatus
from app.domain.exceptions import ResourceNotFoundError
from app.domain.models import PlatformPost
from app.domain.state_machine import transition_post


class ApprovalService:
    """Orchestrates human approval and rejection transitions."""

    async def approve_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
    ) -> PlatformPost:
        """Approve a post currently in PENDING_APPROVAL state.

        Transitions: PENDING_APPROVAL -> APPROVED
        Raises:
            ResourceNotFoundError: If post does not exist.
            InvalidStateTransitionError: If post is not in PENDING_APPROVAL.
        """
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        transition_post(post, PostStatus.APPROVED)
        await db.commit()
        await db.refresh(post)
        return post

    async def reject_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
        reason: str,
    ) -> PlatformPost:
        """Reject a post currently in PENDING_APPROVAL state with feedback.

        Transitions: PENDING_APPROVAL -> REJECTED
        Raises:
            ResourceNotFoundError: If post does not exist.
            InvalidStateTransitionError: If post is not in PENDING_APPROVAL.
        """
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        transition_post(post, PostStatus.REJECTED)
        post.rejection_reason = reason.strip()

        await db.commit()
        await db.refresh(post)
        return post
