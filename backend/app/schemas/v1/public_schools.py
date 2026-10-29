"""Public school website lookup response models (safe fields only)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PublicSchoolLookupOut(_Out):
    school_id: int
    name: str
    slug: str | None = None
    tagline: str | None = None
    logo: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    theme_primary: str | None = None
    theme_secondary: str | None = None
    about: str | None = None
    admissions_open: bool = True
    status: str | None = None
    setup_complete: bool = False
    custom_domain: str | None = None
    domain_status: str | None = None
    # Present only on by-code lookup
    code: str | None = None


def json_response(model: type[BaseModel], *, status_code: int = 200) -> dict:
    return {
        status_code: {"model": model, "description": "Successful Response"},
        404: {"description": "School not found"},
        422: {"description": "Validation Error"},
    }
