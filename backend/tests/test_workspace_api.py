"""Focused API tests for lightweight workspace team management."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import async_session_maker, init_db
from app.domain.models import Workspace, WorkspaceMember
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def ensure_schema():
    await init_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


async def _register(client: AsyncClient, label: str) -> dict[str, object]:
    response = await client.post(
        "/api/auth/register",
        json={"email": f"workspace-api-{label}-{uuid.uuid4().hex}@example.com", "password": "secure-password"},
    )
    assert response.status_code == 201
    return response.json()


def _headers(identity: dict[str, object], workspace_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {identity['access_token']}"}
    if workspace_id is not None:
        headers["X-Workspace-ID"] = workspace_id
    return headers


@pytest.mark.asyncio
async def test_list_workspaces_returns_only_the_callers_memberships_with_roles(client: AsyncClient):
    owner = await _register(client, "workspace-list")
    other_user = await _register(client, "workspace-list-other")
    owner_user_id = uuid.UUID(owner["user"]["id"])

    async with async_session_maker() as db:
        second_workspace = Workspace(name="Second workspace")
        db.add(second_workspace)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=second_workspace.id, user_id=owner_user_id, role="editor"))
        await db.commit()

    owner_response = await client.get("/api/workspaces", headers=_headers(owner))
    assert owner_response.status_code == 200
    owner_workspaces = owner_response.json()
    assert len(owner_workspaces) == 2
    assert {(workspace["id"], workspace["role"]) for workspace in owner_workspaces} == {
        (owner["workspace"]["id"], "owner"),
        (str(second_workspace.id), "editor"),
    }

    other_response = await client.get("/api/workspaces", headers=_headers(other_user))
    assert other_response.status_code == 200
    assert other_response.json() == [
        {
            "id": other_user["workspace"]["id"],
            "name": other_user["workspace"]["name"],
            "role": "owner",
        }
    ]


@pytest.mark.asyncio
async def test_workspace_member_can_list_members_without_exposing_password_data(client: AsyncClient):
    owner = await _register(client, "member-list-owner")
    member = await _register(client, "member-list-member")
    outsider = await _register(client, "member-list-outsider")
    workspace_id = owner["workspace"]["id"]

    added = await client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=_headers(owner),
        json={"email": member["user"]["email"]},
    )
    assert added.status_code == 201

    members_response = await client.get(f"/api/workspaces/{workspace_id}/members", headers=_headers(member))
    assert members_response.status_code == 200
    members = members_response.json()
    assert {(entry["id"], entry["email"], entry["role"]) for entry in members} == {
        (owner["user"]["id"], owner["user"]["email"], "owner"),
        (member["user"]["id"], member["user"]["email"], "member"),
    }
    assert all(set(entry) == {"id", "display_name", "email", "role"} for entry in members)
    assert "password_hash" not in members_response.text

    assert (await client.get(f"/api/workspaces/{workspace_id}/members", headers=_headers(outsider))).status_code == 403


@pytest.mark.asyncio
async def test_only_owner_can_add_existing_users_to_a_workspace(client: AsyncClient):
    owner = await _register(client, "add-owner")
    target = await _register(client, "add-target")
    non_member = await _register(client, "add-outsider")
    workspace_id = owner["workspace"]["id"]

    created = await client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=_headers(owner),
        json={"email": target["user"]["email"]},
    )
    assert created.status_code == 201
    assert created.json() == {
        "id": target["user"]["id"],
        "display_name": target["user"]["display_name"],
        "email": target["user"]["email"],
        "role": "member",
    }

    duplicate = await client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=_headers(owner),
        json={"email": target["user"]["email"]},
    )
    assert duplicate.status_code == 409
    unknown = await client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=_headers(owner),
        json={"email": "unknown@example.com"},
    )
    assert unknown.status_code == 404
    assert "needs a Chitro account" in unknown.json()["detail"]

    assert (
        await client.post(
            f"/api/workspaces/{workspace_id}/members",
            headers=_headers(target),
            json={"email": non_member["user"]["email"]},
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/workspaces/{workspace_id}/members",
            headers=_headers(non_member),
            json={"email": target["user"]["email"]},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_owner_can_remove_member_but_cannot_remove_the_sole_owner(client: AsyncClient):
    owner = await _register(client, "remove-owner")
    member = await _register(client, "remove-member")
    workspace_id = owner["workspace"]["id"]
    await client.post(
        f"/api/workspaces/{workspace_id}/members",
        headers=_headers(owner),
        json={"email": member["user"]["email"]},
    )

    assert (
        await client.delete(
            f"/api/workspaces/{workspace_id}/members/{owner['user']['id']}", headers=_headers(member)
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/workspaces/{workspace_id}/members/{uuid.uuid4()}", headers=_headers(owner))
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/workspaces/{workspace_id}/members/{member['user']['id']}", headers=_headers(owner)
        )
    ).status_code == 204

    members = await client.get(f"/api/workspaces/{workspace_id}/members", headers=_headers(owner))
    assert {entry["id"] for entry in members.json()} == {owner["user"]["id"]}
    assert (
        await client.get(
            "/api/campaigns",
            headers=_headers(member, workspace_id),
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/api/workspaces/{workspace_id}/members/{owner['user']['id']}", headers=_headers(owner)
        )
    ).status_code == 409
