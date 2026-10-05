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
    updated = user_service.update_profile(
        db,
        user,
        first_name=body.first_name,
        last_name=body.last_name,
        mobile=body.mobile,
        mobile_set="mobile" in body.model_fields_set,
    )
    return UserResponse.model_validate(updated)
