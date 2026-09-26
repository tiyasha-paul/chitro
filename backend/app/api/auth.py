"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_current_user, get_db
from app.domain.models import User, Workspace
from app.schemas.auth import (
    AuthenticatedUserResponse,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    WorkspaceResponse,
)
from app.services.auth import AuthService, DuplicateEmailError, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _auth_response(user: User, workspace: Workspace) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=AuthenticatedUserResponse(id=user.id, email=user.email, display_name=user.display_name),
        workspace=WorkspaceResponse(id=workspace.id, name=workspace.name),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user, workspace = await auth_service.register_user(
            db, email=request.email, password=request.password, display_name=request.display_name
        )
    except DuplicateEmailError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from None
    return _auth_response(user, workspace)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    user = await auth_service.authenticate_user(db, email=request.email, password=request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    workspace = await auth_service.get_workspace_for_user(db, user.id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication state")
    return _auth_response(user, workspace)


@router.get("/me", response_model=AuthResponse)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    workspace = await auth_service.get_workspace_for_user(db, current_user.id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication state")
    return _auth_response(current_user, workspace)
