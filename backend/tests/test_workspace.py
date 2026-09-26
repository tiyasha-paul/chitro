"""Tests for Milestone 8A: Workspace and identity persistence foundation for Chitro.

Covers:
1. User creation and persistence.
2. User email uniqueness.
3. Workspace creation and persistence.
4. Workspace membership creation.
5. User -> memberships relationship.
6. Workspace -> members relationship.
7. Duplicate workspace membership rejection.
8. Campaign associated with a workspace.
9. Workspace -> campaigns relationship.
10. Campaign can still be created without workspace_id.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.database import async_session_maker, init_db
from app.domain.models import Campaign, User, Workspace, WorkspaceMember


@pytest.fixture(scope="module", autouse=True)
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_user_creation_and_persistence():
    """1. Verify that a User can be created, persisted, and fetched from the database."""
    unique_email = f"user_{uuid.uuid4().hex[:10]}@hoichoi.tv"
    display_name = "Joydeep Mukherjee"

    async with async_session_maker() as session:
        user = User(
            email=unique_email,
            display_name=display_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        user_id = user.id
        assert user_id is not None
        assert isinstance(user_id, uuid.UUID)
        assert user.email == unique_email
        assert user.display_name == display_name
        assert user.created_at is not None

    async with async_session_maker() as session:
        fetched = await session.get(User, user_id)
        assert fetched is not None
        assert fetched.id == user_id
        assert fetched.email == unique_email
        assert fetched.display_name == display_name
        assert isinstance(fetched.created_at, datetime)


@pytest.mark.asyncio
async def test_user_email_uniqueness():
    """2. Verify that duplicate email addresses are rejected by unique constraint."""
    duplicate_email = f"dup_{uuid.uuid4().hex[:10]}@hoichoi.tv"

    async with async_session_maker() as session:
        user1 = User(email=duplicate_email, display_name="User One")
        session.add(user1)
        await session.commit()

    async with async_session_maker() as session:
        user2 = User(email=duplicate_email, display_name="User Two")
        session.add(user2)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_workspace_creation_and_persistence():
    """3. Verify that a Workspace can be created, persisted, and retrieved."""
    ws_name = f"Marketing Hub {uuid.uuid4().hex[:6]}"

    async with async_session_maker() as session:
        workspace = Workspace(name=ws_name)
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)

        ws_id = workspace.id
        assert ws_id is not None
        assert isinstance(ws_id, uuid.UUID)
        assert workspace.name == ws_name
        assert workspace.created_at is not None

    async with async_session_maker() as session:
        fetched = await session.get(Workspace, ws_id)
        assert fetched is not None
        assert fetched.id == ws_id
        assert fetched.name == ws_name
        assert isinstance(fetched.created_at, datetime)


@pytest.mark.asyncio
async def test_workspace_membership_creation():
    """4. Verify that a WorkspaceMember entry can be created and persisted with default role."""
    async with async_session_maker() as session:
        user = User(email=f"member_{uuid.uuid4().hex[:8]}@hoichoi.tv", display_name="Member User")
        workspace = Workspace(name=f"Workspace {uuid.uuid4().hex[:6]}")
        session.add_all([user, workspace])
        await session.commit()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)

        member_id = member.id
        assert member_id is not None
        assert isinstance(member_id, uuid.UUID)
        assert member.role == "owner"  # Default role
        assert member.workspace_id == workspace.id
        assert member.user_id == user.id
        assert member.created_at is not None

    async with async_session_maker() as session:
        fetched = await session.get(WorkspaceMember, member_id)
        assert fetched is not None
        assert fetched.role == "owner"
        assert fetched.workspace_id == workspace.id
        assert fetched.user_id == user.id


@pytest.mark.asyncio
async def test_user_to_memberships_relationship():
    """5. Verify User -> workspace_members and User -> memberships relationship navigation."""
    async with async_session_maker() as session:
        user = User(email=f"multi_{uuid.uuid4().hex[:8]}@hoichoi.tv", display_name="Multi-Member")
        ws1 = Workspace(name=f"Studio 1 {uuid.uuid4().hex[:4]}")
        ws2 = Workspace(name=f"Studio 2 {uuid.uuid4().hex[:4]}")
        session.add_all([user, ws1, ws2])
        await session.commit()

        m1 = WorkspaceMember(workspace_id=ws1.id, user_id=user.id, role="owner")
        m2 = WorkspaceMember(workspace_id=ws2.id, user_id=user.id, role="editor")
        session.add_all([m1, m2])
        await session.commit()
        user_id = user.id

    async with async_session_maker() as session:
        stmt = (
            select(User)
            .options(
                selectinload(User.workspace_members).selectinload(WorkspaceMember.workspace)
            )
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        loaded_user = result.scalar_one()

        assert len(loaded_user.workspace_members) == 2
        # Check convenience alias
        assert len(loaded_user.memberships) == 2

        roles = {m.role for m in loaded_user.workspace_members}
        assert roles == {"owner", "editor"}

        ws_names = {m.workspace.name for m in loaded_user.workspace_members}
        assert ws1.name in ws_names
        assert ws2.name in ws_names

        # Check reverse navigation member -> user
        for m in loaded_user.workspace_members:
            assert m.user.id == loaded_user.id


@pytest.mark.asyncio
async def test_workspace_to_members_relationship():
    """6. Verify Workspace -> members relationship navigation."""
    async with async_session_maker() as session:
        ws = Workspace(name=f"Team Hub {uuid.uuid4().hex[:6]}")
        u1 = User(email=f"team1_{uuid.uuid4().hex[:6]}@hoichoi.tv", display_name="Team 1")
        u2 = User(email=f"team2_{uuid.uuid4().hex[:6]}@hoichoi.tv", display_name="Team 2")
        session.add_all([ws, u1, u2])
        await session.commit()

        m1 = WorkspaceMember(workspace_id=ws.id, user_id=u1.id, role="owner")
        m2 = WorkspaceMember(workspace_id=ws.id, user_id=u2.id, role="viewer")
        session.add_all([m1, m2])
        await session.commit()
        ws_id = ws.id

    async with async_session_maker() as session:
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.members).selectinload(WorkspaceMember.user))
            .where(Workspace.id == ws_id)
        )
        result = await session.execute(stmt)
        loaded_ws = result.scalar_one()

        assert len(loaded_ws.members) == 2
        member_user_ids = {m.user_id for m in loaded_ws.members}
        assert u1.id in member_user_ids
        assert u2.id in member_user_ids

        # Check reverse navigation member -> workspace
        for m in loaded_ws.members:
            assert m.workspace.id == ws_id


@pytest.mark.asyncio
async def test_duplicate_workspace_member_rejected():
    """7. Verify database constraint rejects duplicate (workspace_id, user_id) membership."""
    async with async_session_maker() as session:
        user = User(email=f"dup_{uuid.uuid4().hex[:8]}@hoichoi.tv", display_name="Dup Member")
        ws = Workspace(name=f"Exclusive WS {uuid.uuid4().hex[:6]}")
        session.add_all([user, ws])
        await session.commit()

        m1 = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
        session.add(m1)
        await session.commit()

    async with async_session_maker() as session:
        m2 = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="contributor")
        session.add(m2)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_campaign_associated_with_workspace():
    """8. Verify that a Campaign can be associated with a Workspace."""
    async with async_session_maker() as session:
        ws = Workspace(name=f"Campaign Workspace {uuid.uuid4().hex[:6]}")
        session.add(ws)
        await session.commit()

        camp = Campaign(
            name="Byomkesh Season 9 Promotion",
            workspace_id=ws.id,
            objective="Drive subscriptions",
            target_audience="Detective thriller fans in Bengal",
        )
        session.add(camp)
        await session.commit()
        await session.refresh(camp)

        camp_id = camp.id
        assert camp.workspace_id == ws.id

    async with async_session_maker() as session:
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.workspace))
            .where(Campaign.id == camp_id)
        )
        result = await session.execute(stmt)
        loaded_camp = result.scalar_one()

        assert loaded_camp.workspace_id == ws.id
        assert loaded_camp.workspace is not None
        assert loaded_camp.workspace.id == ws.id
        assert loaded_camp.workspace.name == ws.name


@pytest.mark.asyncio
async def test_workspace_to_campaigns_relationship():
    """9. Verify Workspace -> campaigns relationship navigation."""
    async with async_session_maker() as session:
        ws = Workspace(name=f"Studio Campaigns {uuid.uuid4().hex[:6]}")
        session.add(ws)
        await session.commit()

        c1 = Campaign(name="Campaign 1", workspace_id=ws.id)
        c2 = Campaign(name="Campaign 2", workspace_id=ws.id)
        session.add_all([c1, c2])
        await session.commit()
        ws_id = ws.id

    async with async_session_maker() as session:
        stmt = (
            select(Workspace)
            .options(selectinload(Workspace.campaigns))
            .where(Workspace.id == ws_id)
        )
        result = await session.execute(stmt)
        loaded_ws = result.scalar_one()

        assert len(loaded_ws.campaigns) == 2
        camp_names = {c.name for c in loaded_ws.campaigns}
        assert camp_names == {"Campaign 1", "Campaign 2"}

        for c in loaded_ws.campaigns:
            assert c.workspace_id == ws_id


@pytest.mark.asyncio
async def test_campaign_created_without_workspace_id():
    """10. Verify that a Campaign can still be created without workspace_id (nullable ownership)."""
    camp_name = f"Standalone Campaign {uuid.uuid4().hex[:6]}"

    async with async_session_maker() as session:
        camp = Campaign(
            name=camp_name,
            objective="Global Bengali diaspora engagement",
        )
        session.add(camp)
        await session.commit()
        await session.refresh(camp)

        camp_id = camp.id
        assert camp.workspace_id is None

    async with async_session_maker() as session:
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.workspace))
            .where(Campaign.id == camp_id)
        )
        result = await session.execute(stmt)
        loaded_camp = result.scalar_one()

        assert loaded_camp.name == camp_name
        assert loaded_camp.workspace_id is None
        assert loaded_camp.workspace is None

