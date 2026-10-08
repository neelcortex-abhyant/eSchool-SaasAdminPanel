from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SchoolAdminCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)


class SchoolAdminUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class SchoolAdminStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class SchoolAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    mobile: Optional[str] = None
    role: str
    school_id: Optional[int] = None
    status: int


class SchoolAdminListResponse(BaseModel):
    items: list[SchoolAdminResponse]
