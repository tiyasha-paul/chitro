"""Authentication and authenticated workspace-access tests for Milestone 8B."""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.domain.models import User, WorkspaceMember
from app.main import app
from app.services.auth import (
    AuthService,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


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
        "title": "Workspace Campaign",
        "genre": "Thriller",
        "language": "bn",
        "audience": "Bengali viewers",
        "objective": "Build awareness",
        "key_themes": ["mystery"],
        "tone": "Suspenseful",
        "cta": "Watch now",
        "release_date": "Friday",
    }


def test_password_hash_does_not_store_plaintext():
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert "correct horse battery staple" not in password_hash


def test_password_verification_accepts_correct_password_and_rejects_incorrect_password():
    password_hash = hash_password("correct-password")
    assert verify_password("correct-password", password_hash)
    assert not verify_password("incorrect-password", password_hash)


@pytest.mark.asyncio
async def test_successful_registration_creates_user_workspace_and_owner_membership(client: AsyncClient):
    email = f"register-{uuid.uuid4().hex}@example.com"
    response = await client.post("/api/auth/register", json={"email": email, "password": "secure-password"})

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert "password_hash" not in body

    async with async_session_maker() as db:
        user = await db.get(User, uuid.UUID(body["user"]["id"]))
        assert user is not None
        assert user.password_hash is not None
        assert user.password_hash != "secure-password"
        membership = await db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user.id,
                WorkspaceMember.workspace_id == uuid.UUID(body["workspace"]["id"]),
            )
        )
        assert membership is not None
        assert membership.role == "owner"


@pytest.mark.asyncio
async def test_duplicate_registration_is_rejected(client: AsyncClient):
    email = f"duplicate-{uuid.uuid4().hex}@example.com"
    payload = {"email": email, "password": "secure-password"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    assert (await client.post("/api/auth/register", json=payload)).status_code == 409


@pytest.mark.asyncio
async def test_login_and_me(client: AsyncClient):
    email = f"login-{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/auth/register", json={"email": email, "password": "secure-password", "display_name": "Login User"}
    )
    assert register.status_code == 201

    login = await client.post("/api/auth/login", json={"email": email, "password": "secure-password"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email
    assert me.json()["workspace"]["id"] == register.json()["workspace"]["id"]


@pytest.mark.asyncio
async def test_incorrect_login_and_unauthenticated_me_are_rejected(client: AsyncClient):
    email = f"wrong-login-{uuid.uuid4().hex}@example.com"
    await client.post("/api/auth/register", json={"email": email, "password": "secure-password"})

    failed_login = await client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    assert failed_login.status_code == 401
    assert failed_login.json()["detail"] == "Invalid email or password"
    assert (await client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_valid_and_expired_jwts_are_accepted_or_rejected_by_the_auth_dependency(client: AsyncClient):
    async with async_session_maker() as db:
        user, _ = await AuthService().register_user(
            db, email=f"jwt-{uuid.uuid4().hex}@example.com", password="secure-password", display_name=None
        )

    valid_token = create_access_token(user.id)
    expired_token = create_access_token(user.id, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(valid_token) == user.id
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {valid_token}"})).status_code == 200
    assert (await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})).status_code == 401
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid-token"})).status_code == 401
    with pytest.raises(InvalidTokenError):
        decode_access_token(expired_token)


@pytest.mark.asyncio
async def test_authenticated_campaign_is_workspace_scoped(client: AsyncClient, brief_payload: dict[str, object]):
    first = await client.post(
        "/api/auth/register", json={"email": f"first-{uuid.uuid4().hex}@example.com", "password": "secure-password"}
    )
    second = await client.post(
        "/api/auth/register", json={"email": f"second-{uuid.uuid4().hex}@example.com", "password": "secure-password"}
    )
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    created = await client.post("/api/campaigns", json={"brief": brief_payload}, headers=first_headers)
    assert created.status_code == 201
    campaign_id = created.json()["id"]

    async with async_session_maker() as db:
        from app.domain.models import Campaign

        campaign = await db.get(Campaign, uuid.UUID(campaign_id))
        assert campaign is not None
        assert campaign.workspace_id == uuid.UUID(first.json()["workspace"]["id"])

    assert (await client.get(f"/api/campaigns/{campaign_id}", headers=first_headers)).status_code == 200
    assert (await client.get(f"/api/campaigns/{campaign_id}", headers=second_headers)).status_code == 404
    listed = await client.get("/api/campaigns", headers=first_headers)
    assert listed.status_code == 200
    assert campaign_id in {campaign["id"] for campaign in listed.json()}
    assert (await client.get("/api/campaigns", headers=second_headers)).json() == []
