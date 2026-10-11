from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SchoolRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    support_email: EmailStr
    support_phone: str = Field(min_length=6, max_length=32)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=80)
    postal_code: str = Field(min_length=3, max_length=16)
    tagline: str = Field(default="", max_length=255)
    logo: str = Field(default="", max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)
    admin_first_name: str = Field(min_length=1, max_length=128)
    admin_last_name: str = Field(min_length=1, max_length=128)
    admin_email: EmailStr
    admin_mobile: str = Field(min_length=6, max_length=32)
    admin_password: str = Field(min_length=8, max_length=128)
    terms_accepted: bool

    @field_validator("support_phone", "admin_mobile")
    @classmethod
    def _phone(cls, value: str) -> str:
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits.isdigit() or not 6 <= len(digits) <= 15:
            raise ValueError("Enter a mobile number with 6 to 15 digits.")
        return value.strip()

    @field_validator("logo")
    @classmethod
    def _logo(cls, value: str) -> str:
        text = value.strip()
        if text and not (text.startswith("http://") or text.startswith("https://") or text.startswith("/")):
            raise ValueError("Logo must be an http(s) URL or a path starting with /.")
        return text

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if " " in text:
            raise ValueError("Website cannot contain spaces.")
        return text

    @field_validator("terms_accepted")
    @classmethod
    def _terms(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Accept the terms and conditions to continue.")
        return value


class SchoolRegistrationResponse(BaseModel):
    school_id: int
    status: str
    message: str
