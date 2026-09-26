"""Campaign orchestration service."""

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.exceptions import ResourceNotFoundError
from app.domain.models import Campaign
from app.schemas.campaigns import CreateCampaignRequest


class CampaignService:
    """Orchestrates Campaign persistence and retrieval."""

    async def create_campaign(
        self,
        db: AsyncSession,
        request: CreateCampaignRequest,
        workspace_id: uuid.UUID | None = None,
    ) -> Campaign:
        """Create a new Campaign from a structured content brief."""
        brief = request.brief
        campaign_name = request.name or brief.title

        brief_dict = brief.model_dump()
        # Convert Enum to string for JSON serialization
        if hasattr(brief.language, "value"):
            brief_dict["language"] = brief.language.value

        campaign = Campaign(
            name=campaign_name,
            objective=brief.objective,
            target_audience=brief.audience,
            brief_context=f"Genre: {brief.genre}. Key themes: {', '.join(brief.key_themes)}",
            brief_payload=brief_dict,
            previous_insights={},
            workspace_id=workspace_id,
        )

        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        return campaign

    async def get_campaign(
        self,
        db: AsyncSession,
        campaign_id: uuid.UUID,
        workspace_id: uuid.UUID | None = None,
    ) -> Campaign:
        """Retrieve a campaign with its posts preloaded."""
        stmt = select(Campaign).where(Campaign.id == campaign_id).options(selectinload(Campaign.posts))
        if workspace_id is not None:
            stmt = stmt.where(Campaign.workspace_id == workspace_id)
        result = await db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise ResourceNotFoundError("Campaign", str(campaign_id))
        return campaign

    async def list_campaigns(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID | None = None,
    ) -> Sequence[Campaign]:
        """List all campaigns ordered by creation time descending."""
        stmt = select(Campaign).order_by(Campaign.created_at.desc()).options(selectinload(Campaign.posts))
        if workspace_id is not None:
            stmt = stmt.where(Campaign.workspace_id == workspace_id)
        result = await db.execute(stmt)
        return result.scalars().all()
