from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.v1.common import PaginatedResponse
from app.services.v1.school_service import SchoolServiceError, normalize_support_email


class SchoolCreateRequest(BaseModel):
    """Create school. ``domain`` stores the SaaS hostname.

    - Omit ``domain_type``: legacy behaviour — ``domain`` is stored as provided
      (full hostname preferred).
    - ``domain_type=default``: ``domain`` is a subdomain **prefix**; the API
      constructs ``{prefix}.{school_base_domain}`` and sets ``domain_verified=1``.
    - ``domain_type=custom``: ``domain`` is a full custom hostname;
      ``domain_verified`` stays ``0`` until verified out-of-band.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    address: str = Field(default="", max_length=255)
    support_phone: str = Field(default="", max_length=255)
    support_email: str = Field(
        default="",
        max_length=255,
        description="Blank is allowed. A non-blank value must be a valid email address.",
    )
    tagline: str = Field(default="", max_length=255)
    logo: str = Field(default="", max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=255)
    domain: Optional[str] = Field(
        default=None,
        max_length=255,
        description=(
            "Application hostname. For domain_type=default this is the subdomain prefix; "
            "for custom/legacy it is the full hostname."
        ),
    )
    domain_type: Optional[Literal["default", "custom"]] = Field(
        default=None,
        description="Omit for legacy clients. default builds prefix.base; custom stores FQDN unverified.",
    )
    school_website: str = Field(
        default="",
        max_length=512,
        description="Public school website URL (http/https). Not the SaaS hostname.",
    )

    @field_validator("support_email")
    @classmethod
    def _support_email(cls, value: str) -> str:
        try:
            return normalize_support_email(value)
        except SchoolServiceError as exc:
            raise ValueError(exc.detail) from exc


class SchoolUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    address: Optional[str] = Field(default=None, max_length=255)
    support_phone: Optional[str] = Field(default=None, max_length=255)
    support_email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Omit to leave unchanged. Blank clears the email. A non-blank value must be valid.",
    )
    tagline: Optional[str] = Field(default=None, max_length=255)
    logo: Optional[str] = Field(default=None, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=255)
    domain: Optional[str] = Field(default=None, max_length=255)
    domain_type: Optional[Literal["default", "custom"]] = Field(default=None)
    school_website: Optional[str] = Field(default=None, max_length=512)

    @field_validator("support_email")
    @classmethod
    def _support_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            return normalize_support_email(value)
        except SchoolServiceError as exc:
            raise ValueError(exc.detail) from exc


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
    domain_type: Optional[str] = None
    domain_verified: int = 0
    school_website: str = ""
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
