from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.v1_database import get_v1_db
from app.models.v1.user import User
from app.schemas.v1.users import ProfileUpdateRequest, UserResponse
from app.services.v1 import user_service

router = APIRouter(prefix="/users", tags=["v1-users"])


@router.get("/me", response_model=UserResponse)
def get_me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
def patch_me(
    body: ProfileUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_v1_db)],
) -> UserResponse:
    fields = body.model_fields_set
    updated = user_service.update_profile(
        db,
        user,
        first_name=body.first_name,
        last_name=body.last_name,
        mobile=body.mobile,
        mobile_set="mobile" in fields,
        country_code=body.country_code,
        country_code_set="country_code" in fields,
        gender=body.gender,
        gender_set="gender" in fields,
        image=body.image,
        image_set="image" in fields,
        dob=body.dob,
        dob_set="dob" in fields,
        current_address=body.current_address,
        current_address_set="current_address" in fields,
        permanent_address=body.permanent_address,
        permanent_address_set="permanent_address" in fields,
        two_factor_enabled=body.two_factor_enabled,
        two_factor_set="two_factor_enabled" in fields,
    )
    return UserResponse.model_validate(updated)
