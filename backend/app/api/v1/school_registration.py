from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.v1_database import get_v1_db
from app.schemas.v1.school_registration import SchoolRegistrationRequest, SchoolRegistrationResponse
from app.services.v1.school_admin_service import SchoolAdminServiceError
from app.services.v1.school_registration_service import SchoolRegistrationError, register_school
from app.services.v1.school_service import SchoolServiceError

router = APIRouter(prefix="/schools", tags=["v1-school-registration"])


@router.post("/register", response_model=SchoolRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_public_school(
    body: SchoolRegistrationRequest,
    db: Annotated[Session, Depends(get_v1_db)],
) -> SchoolRegistrationResponse:
    """Public registration. No token is issued and the school stays pending approval."""
    try:
        school = register_school(
            db,
            name=body.name,
            support_email=str(body.support_email),
            support_phone=body.support_phone,
            address=body.address,
            city=body.city,
            state=body.state,
            country=body.country,
            postal_code=body.postal_code,
            tagline=body.tagline,
            logo=body.logo,
            domain=body.domain,
            admin_first_name=body.admin_first_name,
            admin_last_name=body.admin_last_name,
            admin_email=str(body.admin_email),
            admin_mobile=body.admin_mobile,
            admin_password=body.admin_password,
            terms_accepted=body.terms_accepted,
        )
    except (SchoolRegistrationError, SchoolServiceError, SchoolAdminServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolRegistrationResponse(
        school_id=school.id,
        status="pending_approval",
        message="Your school registration has been submitted successfully.",
    )
