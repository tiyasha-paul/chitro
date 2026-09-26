"""Workspace membership operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import User, WorkspaceMember


class WorkspaceUserNotFoundError(Exception):
    """Raised when a requested member email has no Chitro account."""


class WorkspaceMemberAlreadyExistsError(Exception):
    """Raised when a user is already a member of the workspace."""


class WorkspaceMemberNotFoundError(Exception):
    """Raised when the target user is not a workspace member."""


class SoleOwnerRemovalError(Exception):
    """Raised when removing the only owner of a workspace."""


class WorkspaceService:
    """Encapsulate workspace and lightweight team membership operations."""

    async def list_user_workspaces(self, db: AsyncSession, user_id: uuid.UUID) -> list[WorkspaceMember]:
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .options(selectinload(WorkspaceMember.workspace))
            .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
        )
        return list((await db.execute(stmt)).scalars())

    async def list_workspace_members(
        self, db: AsyncSession, workspace_id: uuid.UUID
    ) -> list[WorkspaceMember]:
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMember.user))
            .join(User, WorkspaceMember.user_id == User.id)
            .order_by(User.email, User.id)
        )
        return list((await db.execute(stmt)).scalars())

    async def add_member_by_email(
        self, db: AsyncSession, workspace_id: uuid.UUID, email: str
    ) -> WorkspaceMember:
        normalized_email = email.strip().lower()
        user = await db.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            raise WorkspaceUserNotFoundError

        existing = await db.scalar(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if existing is not None:
            raise WorkspaceMemberAlreadyExistsError

        membership = WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role="member")
        db.add(membership)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise WorkspaceMemberAlreadyExistsError from None

        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.id == membership.id)
            .options(selectinload(WorkspaceMember.user))
        )
        return (await db.execute(stmt)).scalar_one()

    async def remove_member(
        self, db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        membership = await db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if membership is None:
            raise WorkspaceMemberNotFoundError

        if membership.role == "owner":
            owner_count = await db.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role == "owner")
            )
            if owner_count == 1:
                raise SoleOwnerRemovalError

        await db.delete(membership)
        await db.commit()
