"""Content workflow orchestration service.

Connects Campaign, GenerationService, ValidationService, and state transitions
into a coherent, stateful lifecycle.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Language, Platform, PostStatus
from app.domain.exceptions import ResourceNotFoundError
from app.domain.models import Campaign, PlatformPost
from app.domain.state_machine import transition_post
from app.schemas.briefs import ContentBrief
from app.services.generation import GenerationService
from app.services.validation import ValidationService
from app.validation.media import build_mock_media_asset, validate_media_asset


class ContentWorkflowService:
    """Coordinates generation, deterministic validation, and regeneration workflows."""

    def __init__(
        self,
        generation_service: GenerationService,
        validation_service: ValidationService | None = None,
    ) -> None:
        self._generation_service = generation_service
        self._validation_service = validation_service or ValidationService()

    def _build_brief_from_campaign(
        self,
        campaign: Campaign,
        language: Language,
    ) -> ContentBrief:
        """Reconstruct a ContentBrief from a Campaign model."""
        if campaign.brief_payload:
            payload = dict(campaign.brief_payload)
            payload["language"] = language
            return ContentBrief(**payload)

        # Fallback if brief_payload was not preserved
        return ContentBrief(
            title=campaign.name,
            genre="Drama",
            language=language,
            audience=campaign.target_audience or "General Audience",
            objective=campaign.objective or "Engagement",
            key_themes=[],
        )

    def _snapshot_current_attempt(self, post: PlatformPost) -> dict[str, Any]:
        """Create an audit snapshot of the post's current state."""
        return {
            "attempt": post.generation_attempt,
            "status": post.status,
            "caption": post.caption,
            "hook": post.hook,
            "hashtags": post.hashtags,
            "cta": post.cta,
            "media_spec": post.media_spec,
            "validation_errors": post.validation_errors,
            "rejection_reason": post.rejection_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
    ) -> PlatformPost:
        """Retrieve a platform post by ID."""
        stmt = select(PlatformPost).where(PlatformPost.id == post_id)
        result = await db.execute(stmt)
        post = result.scalar_one_or_none()
        if post is None:
            raise ResourceNotFoundError("PlatformPost", str(post_id))
        return post

    async def generate_post(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
        platform: Platform = Platform.INSTAGRAM,
        language: Language = Language.BENGALI,
    ) -> PlatformPost:
        """Generate, validate, and persist a new platform post for a campaign.

        Lifecycle:
            DRAFT -> GENERATED -> VALIDATED -> PENDING_APPROVAL (on success)
            DRAFT -> GENERATED -> VALIDATION_FAILED (on failure)
        """
        # 1. Retrieve campaign
        stmt = select(Campaign).where(Campaign.id == campaign_id)
        result = await db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))

        brief = self._build_brief_from_campaign(campaign, language)

        # 2. Create initial post record in DRAFT
        post = PlatformPost(
            campaign_id=campaign.id,
            platform=platform.value,
            language=language.value,
            status=PostStatus.DRAFT.value,
            generation_attempt=1,
            generation_history=[],
        )
        db.add(post)
        await db.flush()

        # 3. Transition DRAFT -> GENERATED
        transition_post(post, PostStatus.GENERATED)

        # 4. Invoke AI generation
        insights_list = []
        if isinstance(campaign.previous_insights, list):
            insights_list = campaign.previous_insights
        elif isinstance(campaign.previous_insights, dict) and campaign.previous_insights:
            insights_list = [campaign.previous_insights]

        generated = await self._generation_service.generate_post(
            brief=brief,
            platform=platform,
            previous_insights=insights_list,
        )

        # 5. Populate post fields
        post.hook = getattr(generated, "hook", None)
        post.caption = getattr(generated, "caption", None)
        post.hashtags = getattr(generated, "hashtags", None)
        post.cta = getattr(generated, "cta", None)
        media_asset = getattr(generated, "media_asset", None)
        media_dir = getattr(generated, "media_direction", None)
        post.media_spec = (
            media_asset.model_dump()
            if hasattr(media_asset, "model_dump")
            else media_asset
            if media_asset is not None
            else build_mock_media_asset(getattr(media_dir, "aspect_ratio", None), post.id)
        )

        # 6. Deterministic platform validation
        validation_result = self._validation_service.validate_post(
            content=generated,
            platform=platform,
        )
        media_validation = validate_media_asset(post.media_spec, platform)
        validation_errors = [*validation_result.errors, *media_validation.errors]

        # 7. Apply deterministic transitions
        if not validation_errors:
            post.validation_errors = None
            transition_post(post, PostStatus.VALIDATED)
            transition_post(post, PostStatus.PENDING_APPROVAL)
        else:
            post.validation_errors = [e.model_dump() for e in validation_errors]
            transition_post(post, PostStatus.VALIDATION_FAILED)

        await db.commit()
        await db.refresh(post)
        return post

    async def regenerate_post(
        self,
        db: AsyncSession,
        post_id: uuid.UUID,
    ) -> PlatformPost:
        """Regenerate a post that is currently in REJECTED or VALIDATION_FAILED state.

        Preserves prior attempt in generation_history and passes human feedback
        into the generation prompt.

        Lifecycle:
            REJECTED / VALIDATION_FAILED -> GENERATED -> VALIDATED -> PENDING_APPROVAL
            OR
            REJECTED / VALIDATION_FAILED -> GENERATED -> VALIDATION_FAILED
        """
        post = await self.get_post(db, post_id)

        # 1. Snapshot previous state before modifying
        snapshot = self._snapshot_current_attempt(post)
        history = list(post.generation_history or [])
        history.append(snapshot)
        post.generation_history = history

        # 2. Transition to GENERATED
        transition_post(post, PostStatus.GENERATED)
        post.generation_attempt += 1

        # 3. Retrieve campaign and build brief
        stmt = select(Campaign).where(Campaign.id == post.campaign_id)
        result = await db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(post.campaign_id))

        target_lang = Language(post.language)
        target_platform = Platform(post.platform)
        brief = self._build_brief_from_campaign(campaign, target_lang)

        # 4. Generate with previous rejection reason
        insights_list = []
        if isinstance(campaign.previous_insights, list):
            insights_list = campaign.previous_insights
        elif isinstance(campaign.previous_insights, dict) and campaign.previous_insights:
            insights_list = [campaign.previous_insights]

        generated = await self._generation_service.generate_post(
            brief=brief,
            platform=target_platform,
            previous_insights=insights_list,
            rejection_reason=post.rejection_reason,
        )

        # 5. Populate new content
        post.hook = getattr(generated, "hook", None)
        post.caption = getattr(generated, "caption", None)
        post.hashtags = getattr(generated, "hashtags", None)
        post.cta = getattr(generated, "cta", None)
        media_asset = getattr(generated, "media_asset", None)
        media_dir = getattr(generated, "media_direction", None)
        post.media_spec = (
            media_asset.model_dump()
            if hasattr(media_asset, "model_dump")
            else media_asset
            if media_asset is not None
            else build_mock_media_asset(getattr(media_dir, "aspect_ratio", None), post.id)
        )

        # 6. Validate new attempt
        validation_result = self._validation_service.validate_post(
            content=generated,
            platform=target_platform,
        )
        media_validation = validate_media_asset(post.media_spec, target_platform)
        validation_errors = [*validation_result.errors, *media_validation.errors]

        # 7. Apply deterministic transitions
        if not validation_errors:
            post.validation_errors = None
            transition_post(post, PostStatus.VALIDATED)
            transition_post(post, PostStatus.PENDING_APPROVAL)
        else:
            post.validation_errors = [e.model_dump() for e in validation_errors]
            transition_post(post, PostStatus.VALIDATION_FAILED)

        await db.commit()
        await db.refresh(post)
        return post
