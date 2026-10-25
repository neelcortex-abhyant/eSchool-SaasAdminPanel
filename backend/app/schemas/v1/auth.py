from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.v1.users import UserResponse


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    mobile: Optional[str] = Field(default=None, max_length=32)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # Sent by the admin panel. Accepted for compatibility and ignored: reset
    # links always use the server's ADMIN_RESET_URL.
    app_origin: Optional[str] = Field(default=None, max_length=512)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    """Successful login/signup/register body. Always includes the session token.

    ``access_token`` is the opaque bearer value from ``auth_service.create_session``
    (``secrets.token_urlsafe``), not a JWT. Clients must send it as
    ``Authorization: Bearer <access_token>``.
    """

    model_config = ConfigDict(
        # Keep every auth field in OpenAPI examples and JSON responses.
        json_schema_extra={
            "examples": [
                {
                    "access_token": "opaque-session-token",
                    "token_type": "bearer",
                    "expires_at": "2026-10-25T12:00:00Z",
                    "user": {
                        "id": "00000000-0000-0000-0000-000000000001",
                        "email": "admin@school.com",
                        "first_name": "Ada",
                        "last_name": "Admin",
                        "mobile": None,
                        "country_code": None,
                        "gender": None,
                        "image": None,
                        "dob": None,
                        "current_address": None,
                        "permanent_address": None,
                        "two_factor_enabled": 0,
                        "role": "school_admin",
                        "school_id": 1,
                        "status": 1,
                    },
                }
            ]
        }
    )

    access_token: str = Field(
        ...,
        min_length=1,
        description="Opaque bearer session token issued at login (not a JWT).",
    )
    token_type: str = Field(default="bearer", description="Always 'bearer'.")
    expires_at: datetime = Field(description="UTC expiry of the session token.")
    user: UserResponse
