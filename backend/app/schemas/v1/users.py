from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    mobile: Optional[str] = None
    role: str
    school_id: Optional[int] = None
    status: int = 1


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)
