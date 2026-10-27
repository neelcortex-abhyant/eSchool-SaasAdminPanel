"""DB-free checks: login response always serializes a real access_token.

Lives outside ``tests/`` so collection does not load ``tests/conftest.py``
(which requires TEST_DATABASE_URL / Neon).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.auth import _token_response
from app.schemas.v1.auth import AuthTokenResponse
from app.schemas.v1.users import UserResponse
from app.services.v1.auth_service import IssuedSession


def _fake_user(**overrides):
    base = {
        "id": uuid4(),
        "email": "login@school.com",
        "first_name": "Log",
        "last_name": "In",
        "mobile": None,
        "country_code": None,
        "gender": None,
        "image": None,
        "dob": None,
        "current_address": None,
        "permanent_address": None,
        "two_factor_enabled": 0,
        "role": "user",
        "school_id": None,
        "status": 1,
    }
    base.update(overrides)
    return type("UserStub", (), base)()


def test_auth_token_response_json_includes_access_token():
    expires = datetime.now(timezone.utc) + timedelta(hours=2)
    body = AuthTokenResponse(
        access_token="real-opaque-token-value",
        token_type="bearer",
        expires_at=expires,
        user=UserResponse.model_validate(_fake_user()),
    )
    payload = body.model_dump(mode="json")
    assert payload["access_token"] == "real-opaque-token-value"
    assert payload["token_type"] == "bearer"
    assert payload["expires_at"]
    assert payload["user"]["email"] == "login@school.com"


def test_token_response_helper_maps_plain_token_to_access_token():
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    issued = IssuedSession(
        plain_token="session-plain-abc123",
        expires_at=expires,
        user=_fake_user(email="mapped@school.com", role="school_admin", school_id=9),
    )
    resp = _token_response(issued)
    assert isinstance(resp, AuthTokenResponse)
    assert resp.access_token == "session-plain-abc123"
    assert resp.token_type == "bearer"
    assert resp.expires_at == expires
    assert resp.user.email == "mapped@school.com"
    assert resp.user.role == "school_admin"

    http_payload = resp.model_dump(mode="json")
    assert "access_token" in http_payload
    assert http_payload["access_token"] == "session-plain-abc123"


def test_login_route_response_model_emits_access_token_over_http():
    """Exercise FastAPI response_model serialization the same way /auth/login does."""
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    issued = IssuedSession(
        plain_token="http-response-token",
        expires_at=expires,
        user=_fake_user(),
    )

    app = FastAPI()

    @app.post("/login", response_model=AuthTokenResponse)
    def login():
        return _token_response(issued)

    client = TestClient(app)
    res = client.post("/login")
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"] == "http-response-token"
    assert data["token_type"] == "bearer"
    assert data["expires_at"]
    assert data["user"]["email"] == "login@school.com"


def test_auth_token_response_rejects_empty_access_token():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AuthTokenResponse(
            access_token="",
            token_type="bearer",
            expires_at=datetime.now(timezone.utc),
            user=UserResponse.model_validate(_fake_user()),
        )
