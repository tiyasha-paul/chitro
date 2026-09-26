"""Workspace and lightweight team membership endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db,
    get_workspace_membership_for_path,
    get_workspace_service,
)
from app.domain.models import User, WorkspaceMember
from app.schemas.workspaces import AddMemberRequest, WorkspaceMemberResponse, WorkspaceSummary
from app.services.workspace import (
    SoleOwnerRemovalError,
    WorkspaceMemberAlreadyExistsError,
    WorkspaceMemberNotFoundError,
    WorkspaceService,
    WorkspaceUserNotFoundError,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def _member_response(membership: WorkspaceMember) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        id=membership.user.id,
        display_name=membership.user.display_name,
        email=membership.user.email,
        role=membership.role,
    )


def _require_owner(membership: WorkspaceMember) -> None:
    if membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace owner access required")


@router.get("", response_model=list[WorkspaceSummary], summary="List the current user's workspaces")
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceSummary]:
    memberships = await workspace_service.list_user_workspaces(db, current_user.id)
    return [
        WorkspaceSummary(id=membership.workspace.id, name=membership.workspace.name, role=membership.role)
        for membership in memberships
    ]


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List members of a workspace",
)
async def list_members(
    membership: WorkspaceMember = Depends(get_workspace_membership_for_path),
    db: AsyncSession = Depends(get_db),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> list[WorkspaceMemberResponse]:
    members = await workspace_service.list_workspace_members(db, membership.workspace_id)
    return [_member_response(member) for member in members]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an existing Chitro user to a workspace",
)
async def add_member(
    request: AddMemberRequest,
    membership: WorkspaceMember = Depends(get_workspace_membership_for_path),
    db: AsyncSession = Depends(get_db),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> WorkspaceMemberResponse:
    _require_owner(membership)
    try:
        added_membership = await workspace_service.add_member_by_email(db, membership.workspace_id, request.email)
    except WorkspaceUserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This person needs a Chitro account before they can be added.",
        ) from None
    except WorkspaceMemberAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a workspace member") from None
    return _member_response(added_membership)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workspace member",
)
async def remove_member(
    user_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership_for_path),
    db: AsyncSession = Depends(get_db),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> Response:
    _require_owner(membership)
    try:
        await workspace_service.remove_member(db, membership.workspace_id, user_id)
    except WorkspaceMemberNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found") from None
    except SoleOwnerRemovalError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer ownership before removing the only owner.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
