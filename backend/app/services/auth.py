"""Authentication and workspace identity services."""

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.domain.models import User, Workspace, WorkspaceMember


class InvalidTokenError(Exception):
    """Raised when an access token is malformed, invalid, or expired."""


class DuplicateEmailError(Exception):
    """Raised when attempting to register an already-used email address."""


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a unique random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "$".join(
        (
            "scrypt",
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password without exposing parsing or comparison details."""
    if not password_hash:
        return False
    try:
        algorithm, encoded_salt, encoded_digest = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    except (ValueError, TypeError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(actual, expected)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived HS256 JWT containing only the user identifier."""
    expiration = int(time.time() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).total_seconds())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": str(user_id), "exp": expiration}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(settings.AUTH_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def decode_access_token(token: str) -> uuid.UUID:
    """Validate an HS256 JWT and return its subject as a UUID."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
        if header.get("alg") != "HS256" or not isinstance(payload.get("exp"), int):
            raise InvalidTokenError
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(settings.AUTH_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_b64)) or payload["exp"] <= time.time():
            raise InvalidTokenError
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise InvalidTokenError from None


class AuthService:
    """Coordinates user credentials and workspace ownership."""

    async def register_user(
        self, db: AsyncSession, *, email: str, password: str, display_name: str | None
    ) -> tuple[User, Workspace]:
        normalized_email = email.strip().lower()
        existing = await db.scalar(select(User.id).where(User.email == normalized_email))
        if existing is not None:
            raise DuplicateEmailError

        user = User(
            email=normalized_email,
            display_name=display_name or normalized_email.split("@", 1)[0],
            password_hash=hash_password(password),
        )
        workspace = Workspace(name=f"{user.display_name}'s Workspace")
        db.add_all((user, workspace))
        await db.flush()
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        await db.commit()
        await db.refresh(user)
        await db.refresh(workspace)
        return user, workspace

    async def authenticate_user(self, db: AsyncSession, *, email: str, password: str) -> User | None:
        user = await db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    async def get_user_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await db.get(User, user_id)

    async def get_workspace_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> Workspace | None:
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(WorkspaceMember.created_at)
            .options(selectinload(WorkspaceMember.workspace))
        )
        membership = (await db.execute(stmt)).scalars().first()
        return membership.workspace if membership else None
