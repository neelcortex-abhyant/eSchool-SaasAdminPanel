"""Public (unauthenticated) school website lookup APIs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.schemas.v1 import public_schools as public_out
from app.services.v1 import public_school_lookup as lookup
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="/public/schools", tags=["v1-public-schools"])


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/by-host", responses=public_out.json_response(public_out.PublicSchoolLookupOut))
def public_school_by_host(
    response: Response,
    db: Annotated[Session, Depends(central_db)],
    host: str = Query(..., min_length=1, description="School hostname, e.g. greenvalley.example.com"),
):
    """Resolve a public school website by hostname. Safe fields only; no auth."""
    payload = _run(lambda: lookup.lookup_by_host(db, host))
    response.headers["Cache-Control"] = "public, max-age=60"
    return payload


@router.get("/by-code", responses=public_out.json_response(public_out.PublicSchoolLookupOut))
def public_school_by_code(
    response: Response,
    db: Annotated[Session, Depends(central_db)],
    code: str = Query(..., min_length=1, description="Public school code"),
):
    """Resolve a school by public ``code``. Safe fields only; no auth."""
    payload = _run(lambda: lookup.lookup_by_code(db, code))
    response.headers["Cache-Control"] = "public, max-age=60"
    return payload
