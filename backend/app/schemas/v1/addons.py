from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class AddonCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=255)
    price: float = Field(default=0.0, ge=0)


class AddonUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)
    price: Optional[float] = Field(default=None, ge=0)


class AddonStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class AddonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    price: float = 0.0
    status: int
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AddonListResponse(PaginatedResponse):
    items: list[AddonResponse]


class SchoolAddonAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_id: int = Field(ge=1)
    subscription_id: Optional[int] = Field(default=None, ge=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SchoolAddonStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class SchoolAddonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    addon_id: int
    subscription_id: int
    status: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SchoolAddonListResponse(PaginatedResponse):
    items: list[SchoolAddonResponse]
