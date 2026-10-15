from __future__ import annotations

import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    mobile: Optional[str] = None
    country_code: Optional[str] = None
    gender: Optional[str] = None
    image: Optional[str] = None
    dob: Optional[date] = None
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None
    two_factor_enabled: int = 0
    role: str
    school_id: Optional[int] = None
    status: int = 1


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)
    country_code: Optional[str] = Field(default=None, max_length=8)
    gender: Optional[Literal["male", "female"]] = None
    image: Optional[str] = Field(default=None, max_length=255)
    dob: Optional[date] = None
    current_address: Optional[str] = Field(default=None, max_length=512)
    permanent_address: Optional[str] = Field(default=None, max_length=512)
    two_factor_enabled: Optional[int] = Field(default=None, ge=0, le=1)

    @field_validator("image")
    @classmethod
    def image_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if value.startswith("/") or value.startswith("https://") or value.startswith("http://"):
            return value
        raise ValueError("Image must be an uploaded file")

    @field_validator("country_code")
    @classmethod
    def dial_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        cleaned = value.strip()
        if len(cleaned) > 8 or not cleaned.startswith("+") or not cleaned[1:].isdigit():
            raise ValueError("Country code must look like +93")
        return cleaned
