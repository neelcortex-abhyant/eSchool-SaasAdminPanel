from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SchoolAdminCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # Omit to send an invitation link instead (needs mail configured; see invite_sent).
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)
    # Keys from GET /super-admin/roles. Omit for the full school_admin role.
    roles: Optional[list[str]] = Field(default=None, min_length=1, max_length=10)
    status: int = Field(default=1, ge=0, le=1)

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        # The service strips names, so a whitespace-only name would be saved empty.
        if not value.strip():
            raise ValueError("Must not be blank")
        return value


class SchoolAdminUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class SchoolAdminStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class SchoolAdminRolesRequest(BaseModel):
    """Replaces the admin's roles. Keys come from GET /super-admin/roles."""

    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(min_length=1, max_length=10)


class SchoolAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    mobile: Optional[str] = None
    role: str
    school_id: Optional[int] = None
    school_name: Optional[str] = None
    status: int
    # Admin roles from the RBAC catalog and the permissions they grant.
    roles: list[str] = []
    permissions: list[str] = []
    created_at: Optional[datetime] = None
    # Set by create and /invite only: true when the invitation email was accepted
    # by the mail server, false when it was not sent. null on other responses.
    invite_sent: Optional[bool] = None


class SchoolAdminListResponse(BaseModel):
    items: list[SchoolAdminResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class PermissionResponse(BaseModel):
    key: str
    label: str


class PermissionListResponse(BaseModel):
    items: list[PermissionResponse]


class RoleResponse(BaseModel):
    key: str
    label: str
    permissions: list[str]


class RoleListResponse(BaseModel):
    items: list[RoleResponse]
