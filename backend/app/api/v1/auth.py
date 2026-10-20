from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import AuthContext, get_current_auth
from app.core import rate_limit
from app.core.v1_database import get_v1_db
from app.schemas.v1.auth import (
    AuthTokenResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.schemas.v1.users import UserResponse
from app.services.v1 import auth_service, password_reset_service

router = APIRouter(prefix="/auth", tags=["v1-auth"])
logger = logging.getLogger("eschool.auth")


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


def login_with_limits(request: Request, email: str, attempt) -> auth_service.IssuedSession:
    """Run a login, counting failed credentials per email and per IP (429 when exceeded).

    Shared by /auth/login and /super-admin/login. Only wrong-credential failures
    (401) count, so a user who signs in correctly is never locked out.
    """
    email_key = auth_service.normalize_email(email)
    ip_key = rate_limit.client_ip(request)
    rate_limit.LOGIN_PER_EMAIL.check(email_key)
    rate_limit.LOGIN_PER_IP.check(ip_key)
    try:
        issued = attempt()
    except auth_service.AuthError as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            rate_limit.LOGIN_PER_EMAIL.record(email_key)
            rate_limit.LOGIN_PER_IP.record(ip_key)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    rate_limit.LOGIN_PER_EMAIL.clear(email_key)
    return issued


@router.post("/login", response_model=AuthTokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_v1_db)],
) -> AuthTokenResponse:
    issued = login_with_limits(
        request, body.email, lambda: auth_service.login(db, email=body.email, password=body.password)
    )
    return _token_response(issued)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    db: Annotated[Session, Depends(get_v1_db)],
) -> dict[str, str]:
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password and confirmation must match.")
    try:
        auth_service.change_password(
            db,
            auth.user,
            auth.session,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"message": "Password changed."}


FORGOT_PASSWORD_MESSAGE = "If an account exists for that email, a reset link has been sent."


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_v1_db)],
) -> dict[str, str]:
    """Always the same answer, so the response never reveals whether the email exists.

    body.app_origin is ignored; the link uses ADMIN_RESET_URL. Mail is sent after
    the response so its timing does not differ between known and unknown emails.
    Limited per email and per IP whether or not the email exists.
    """
    rate_limit.FORGOT_PER_IP.hit(rate_limit.client_ip(request))
    rate_limit.FORGOT_PER_EMAIL.hit(auth_service.normalize_email(body.email))
    try:
        mail = password_reset_service.request_reset(db, body.email)
    except Exception:
        db.rollback()
        logger.exception("forgot_password_failed")
        mail = None
    if mail is not None:
        background.add_task(password_reset_service.send, mail)
    return {"message": FORGOT_PASSWORD_MESSAGE}


@router.post("/reset-password")
def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_v1_db)],
) -> dict[str, str]:
    """Set a new password from a reset or invitation link. Signs out every session."""
    rate_limit.RESET_PER_IP.hit(rate_limit.client_ip(request))
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password and confirmation must match.")
    try:
        password_reset_service.consume_token(db, body.token, body.new_password)
    except password_reset_service.PasswordResetError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Password could not be reset") from None
    return {"message": "Password has been reset."}


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
