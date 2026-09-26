"""Focused API coverage for explicit workspace selection and isolation."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import async_session_maker, init_db
from app.domain.enums import PostStatus
from app.domain.models import Campaign, PlatformPost, Workspace, WorkspaceMember
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def ensure_schema():
    await init_db()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def brief_payload() -> dict[str, object]:
    return {
        "title": "Workspace campaign",
        "genre": "Thriller",
        "language": "bn",
        "audience": "Bengali viewers",
        "objective": "Build awareness",
        "key_themes": ["mystery"],
        "tone": "Suspenseful",
        "cta": "Watch now",
        "release_date": "Friday",
    }


async def _register(client: AsyncClient, label: str) -> dict[str, object]:
    response = await client.post(
        "/api/auth/register",
        json={"email": f"workspace-isolation-{label}-{uuid.uuid4().hex}@example.com", "password": "secure-password"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_selected_workspace_header_changes_campaign_scope_and_headerless_falls_back(
    client: AsyncClient, brief_payload: dict[str, object]
):
    identity = await _register(client, "member")
    user_id = uuid.UUID(identity["user"]["id"])
    workspace_a_id = uuid.UUID(identity["workspace"]["id"])

    async with async_session_maker() as db:
        workspace_b = Workspace(name="Second workspace")
        db.add(workspace_b)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=workspace_b.id, user_id=user_id, role="member"))
        db.add_all(
            (
                Campaign(name="Campaign A", workspace_id=workspace_a_id),
                Campaign(name="Campaign B", workspace_id=workspace_b.id),
            )
        )
        await db.commit()
        workspace_b_id = workspace_b.id

    auth_headers = {"Authorization": f"Bearer {identity['access_token']}"}
    workspace_a_headers = {**auth_headers, "X-Workspace-ID": str(workspace_a_id)}
    workspace_b_headers = {**auth_headers, "X-Workspace-ID": str(workspace_b_id)}

    # Header omission has a deliberate, centralized compatibility fallback.
    fallback = await client.get("/api/campaigns", headers=auth_headers)
    assert fallback.status_code == 200
    assert [campaign["name"] for campaign in fallback.json()] == ["Campaign A"]

    selected_a = await client.get("/api/campaigns", headers=workspace_a_headers)
    selected_b = await client.get("/api/campaigns", headers=workspace_b_headers)
    assert [campaign["name"] for campaign in selected_a.json()] == ["Campaign A"]
    assert [campaign["name"] for campaign in selected_b.json()] == ["Campaign B"]

    created = await client.post("/api/campaigns", json={"brief": brief_payload}, headers=workspace_b_headers)
    assert created.status_code == 201
    async with async_session_maker() as db:
        campaign = await db.get(Campaign, uuid.UUID(created.json()["id"]))
        assert campaign is not None
        assert campaign.workspace_id == workspace_b_id


@pytest.mark.asyncio
async def test_workspace_header_rejects_malformed_and_non_member_selections(client: AsyncClient):
    first = await _register(client, "first")
    second = await _register(client, "second")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {
        "Authorization": f"Bearer {second['access_token']}",
        "X-Workspace-ID": first["workspace"]["id"],
    }

    assert (await client.get("/api/campaigns", headers={**first_headers, "X-Workspace-ID": "not-a-uuid"})).status_code == 422
    assert (await client.get("/api/campaigns", headers=second_headers)).status_code == 403


@pytest.mark.asyncio
async def test_campaign_and_post_routes_hide_resources_outside_selected_workspace(client: AsyncClient):
    identity = await _register(client, "routes")
    user_id = uuid.UUID(identity["user"]["id"])
    workspace_a_id = uuid.UUID(identity["workspace"]["id"])

    async with async_session_maker() as db:
        workspace_b = Workspace(name="Other selected workspace")
        db.add(workspace_b)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=workspace_b.id, user_id=user_id, role="member"))
        campaign = Campaign(name="Private campaign", workspace_id=workspace_a_id)
        db.add(campaign)
        await db.flush()
        post = PlatformPost(
            campaign_id=campaign.id,
            platform="instagram",
            language="bn",
            status=PostStatus.PENDING_APPROVAL.value,
        )
        db.add(post)
        await db.commit()
        campaign_id = campaign.id
        post_id = post.id
        workspace_b_id = workspace_b.id

    headers = {
        "Authorization": f"Bearer {identity['access_token']}",
        "X-Workspace-ID": str(workspace_b_id),
    }

    campaign_paths = [
        ("get", f"/api/campaigns/{campaign_id}"),
        ("post", f"/api/campaigns/{campaign_id}/posts/generate"),
        ("get", f"/api/campaigns/{campaign_id}/analytics/comparison"),
        ("get", f"/api/campaigns/{campaign_id}/insights"),
        ("post", f"/api/campaigns/{campaign_id}/insights/generate"),
        ("post", f"/api/campaigns/{campaign_id}/reports/weekly"),
    ]
    for method, path in campaign_paths:
        if method == "post":
            response = await client.post(path, headers=headers, json={})
        else:
            response = await client.get(path, headers=headers)
        assert response.status_code == 404, path

    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    post_requests = [
        ("get", f"/api/posts/{post_id}", None),
        ("post", f"/api/posts/{post_id}/approve", None),
        ("post", f"/api/posts/{post_id}/reject", {"reason": "Needs revision"}),
        ("post", f"/api/posts/{post_id}/regenerate", None),
        ("post", f"/api/posts/{post_id}/schedule", {"scheduled_at": future_time}),
        ("post", f"/api/posts/{post_id}/publish", None),
        ("post", f"/api/posts/{post_id}/metrics", {"reach": 100}),
        ("get", f"/api/posts/{post_id}/metrics", None),
    ]
    for method, path, body in post_requests:
        if method == "post":
            response = await client.post(path, headers=headers, json=body)
        else:
            response = await client.get(path, headers=headers)
        assert response.status_code == 404, path


@pytest.mark.asyncio
async def test_post_route_uses_same_malformed_workspace_validation(client: AsyncClient):
    identity = await _register(client, "post-header")
    response = await client.get(
        f"/api/posts/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {identity['access_token']}", "X-Workspace-ID": "not-a-uuid"},
    )
    assert response.status_code == 422
