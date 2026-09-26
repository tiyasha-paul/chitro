"""Workspace and membership request/response DTOs."""

import uuid

from pydantic import BaseModel, Field


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class WorkspaceMemberResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str
    role: str


class AddMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
