"""Public certificate verification (opaque token, minimal fields, no auth)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.schemas.v1 import school_admin_mgmt_responses as mgmt_out
from app.services.v1 import school_academic_mgmt as mgmt
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="/public/certificates", tags=["v1-public-certificates"])


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get(
    "/verify/{token}",
    responses=mgmt_out.json_response(mgmt_out.CertificateVerifyOut),
)
def verify_certificate(
    token: str,
    response: Response,
    db: Annotated[Session, Depends(central_db)],
):
    payload = _run(lambda: mgmt.verify_certificate_public(db, token))
    response.headers["Cache-Control"] = "no-store"
    return payload
