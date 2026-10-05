from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import AuthContext, get_current_auth
from app.core.v1_database import get_v1_db
from app.schemas.v1.auth import AuthTokenResponse, LoginRequest, SignupRequest
from app.schemas.v1.users import UserResponse
from app.services.v1 import auth_service

router = APIRouter(prefix="/auth", tags=["v1-auth"])


def _token_response(issued: auth_service.IssuedSession) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=issued.plain_token,
        token_type="bearer",
        expires_at=issued.expires_at,
        user=UserResponse.model_validate(issued.user),
    )


@router.post("/signup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Annotated[Session, Depends(get_v1_db)]) -> AuthTokenResponse:
    try:
        issued = auth_service.signup(
            db,
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _token_response(issued)


@router.post("/login", response_model=AuthTokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_v1_db)]) -> AuthTokenResponse:
    try:
        issued = auth_service.login(db, email=body.email, password=body.password)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _token_response(issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    db: Annotated[Session, Depends(get_v1_db)],
) -> Response:
    auth_service.logout(db, auth.session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def auth_me(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> UserResponse:
    return UserResponse.model_validate(auth.user)
