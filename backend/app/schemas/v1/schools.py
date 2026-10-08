from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class SchoolCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    address: str = Field(default="", max_length=255)
    support_phone: str = Field(default="", max_length=255)
    support_email: str = Field(default="", max_length=255)
    tagline: str = Field(default="", max_length=255)
    logo: str = Field(default="", max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)


class SchoolUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    address: Optional[str] = Field(default=None, max_length=255)
    support_phone: Optional[str] = Field(default=None, max_length=255)
    support_email: Optional[str] = Field(default=None, max_length=255)
    tagline: Optional[str] = Field(default=None, max_length=255)
    logo: Optional[str] = Field(default=None, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)


class SchoolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    support_phone: str
    support_email: str
    tagline: str
    logo: str
    admin_id: Optional[int] = None
    v1_admin_id: Optional[str] = None
    status: int
    code: Optional[str] = None
    database_name: Optional[str] = None
    domain: Optional[str] = None
    installed: int
    provisioned_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SchoolProvisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: SchoolResponse
    provisioned: bool
    first_provision: bool


class SchoolListResponse(PaginatedResponse):
    items: list[SchoolResponse]
