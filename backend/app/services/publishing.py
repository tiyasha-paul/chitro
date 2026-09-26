"""Publishing and scheduling service managing post distribution."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import ChannelAdapter, PublishPayload, get_channel_adapter
from app.domain.enums import Platform, PostStatus
from app.domain.exceptions import ResourceNotFoundError
from app.domain.models import PlatformPost
from app.domain.state_machine import transition_post
from app.validation.media import ensure_valid_media_asset


class PublishingService:
    """Orchestrates scheduling and publishing of approved posts."""

    def __init__(self, default_adapter: Optional[ChannelAdapter] = None) -> None:
        self.default_adapter = default_adapter

    async def schedule_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
        scheduled_at: datetime,
    ) -> PlatformPost:
        """Schedule an approved post for future publication.

        Enforces:
        - Post existence (ResourceNotFoundError if not found)
        - Target time must be strictly in the future
        - State machine transition: APPROVED -> SCHEDULED
        """
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        ensure_valid_media_asset(post.media_spec, Platform(post.platform))

        # Ensure timestamp is timezone-aware UTC
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if scheduled_at <= now:
            raise ValueError("scheduled_at must be in the future")

        # Enforce state transition: only APPROVED can move to SCHEDULED
        transition_post(post, PostStatus.SCHEDULED)
        post.scheduled_at = scheduled_at

        await db.commit()
        await db.refresh(post)
        return post

    async def publish_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
        adapter: Optional[ChannelAdapter] = None,
    ) -> PlatformPost:
        """Publish a post to its target channel adapter.

        Supports:
        - Direct publish from APPROVED (APPROVED -> SCHEDULED -> PUBLISHED)
        - Publish from SCHEDULED (SCHEDULED -> PUBLISHED)
        - Idempotent republish (if already PUBLISHED, returns existing post without calling adapter)

        Enforces:
        - State machine transitions
        - Rollback / failure isolation if channel adapter raises an error
        - Persistence of external post ID, published timestamp, and publish result payload
        """
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()

        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))

        # Idempotency guard: if already published, return existing entity
        if post.status == PostStatus.PUBLISHED.value:
            return post

        ensure_valid_media_asset(post.media_spec, Platform(post.platform))

        # Check and perform initial transition to SCHEDULED if currently APPROVED
        if post.status == PostStatus.APPROVED.value:
            transition_post(post, PostStatus.SCHEDULED)
            if post.scheduled_at is None:
                post.scheduled_at = datetime.now(timezone.utc)
        elif post.status != PostStatus.SCHEDULED.value:
            # If in any other state (DRAFT, PENDING_APPROVAL, REJECTED, etc.), trigger transition check to fail cleanly
            transition_post(post, PostStatus.SCHEDULED)

        # Resolve publishing adapter
        active_adapter = adapter or self.default_adapter
        if active_adapter is None:
            active_adapter = get_channel_adapter(Platform(post.platform))

        # Normalize hashtags
        tags: list[str] = []
        if isinstance(post.hashtags, list):
            tags = post.hashtags
        elif isinstance(post.hashtags, dict) and "tags" in post.hashtags:
            tags = post.hashtags["tags"]

        payload = PublishPayload(
            post_id=post.id,
            caption=post.caption or "",
            media_spec=post.media_spec,
            hashtags=tags,
            cta=post.cta,
            platform=post.platform,
        )

        # Execute channel publication (if this raises, post does NOT transition to PUBLISHED)
        publish_result = await active_adapter.publish(payload)

        # Final state transition: SCHEDULED -> PUBLISHED
        transition_post(post, PostStatus.PUBLISHED)
        post.published_at = publish_result.published_at
        post.published_post_id = publish_result.external_post_id
        post.publish_result = publish_result.model_dump(mode="json")

        await db.commit()
        await db.refresh(post)
        return post
