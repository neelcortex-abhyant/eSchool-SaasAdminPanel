"""Request/response schemas for school branch APIs."""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BranchCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)
    address: str = Field(default="", max_length=512)


class BranchUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)
    address: Optional[str] = Field(default=None, max_length=512)
    status: Optional[int] = Field(default=None, ge=0, le=1)


class BranchAdminsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[uuid.UUID] = Field(default_factory=list)


class BranchOut(BaseModel):
    id: int
    school_id: int
    name: str
    code: Optional[str] = None
    address: str = ""
    status: int
    is_default: bool
    deleted_at: Optional[str] = None


class BranchListOut(BaseModel):
    items: list[BranchOut]


class BranchAdminsOut(BaseModel):
    branch_id: int
    user_ids: list[str]


class BranchDeletedOut(BaseModel):
    id: int
    deleted: bool


class BranchSummaryItem(BranchOut):
    created_at: Optional[str] = None
    student_count: int = 0
    teacher_count: int = 0


class SchoolBranchSummaryOut(BaseModel):
    school_id: int
    school_name: str
    total_branches: int
    active_branches: int
    inactive_branches: int
    max_branches: int
    remaining_capacity: int
    branch_creation_enabled: bool
    branches: list[BranchSummaryItem]


class BranchSettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_branches: int = Field(ge=1, le=500)
    branch_creation_enabled: bool


class SchoolBranchCapabilityOut(BaseModel):
    """Additive fields on GET /school-admin/me/branches. Existing keys remain."""

    branches: list[BranchOut]
    default_branch_id: Optional[int] = None
    active_branch_id: Optional[int] = None
    is_full_school_admin: bool
    total_branches: int
    active_branches: int
    max_branches: int
    remaining_capacity: int
    branch_creation_enabled: bool
    can_create_branch: bool
