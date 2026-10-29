"""Staff/driver transport trip GPS and attendance (HTTP polling)."""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_staff_user
from app.models.tables import School, User
from app.schemas.v1.school_admin_erp import TransportAttendanceBody, TransportGpsBody
from app.schemas.v1.school_admin_erp_responses import (
    TransportAttendanceEventOut,
    TransportGpsPointOut,
    TransportTripListOut,
    json_response,
)
from app.services.v1 import school_erp_transport as erp_transport
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="/staff/transport", tags=["staff-transport"])


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/my-trips", responses=json_response(TransportTripListOut))
def staff_my_trips(
    tenant: Tuple[Session, User, School] = Depends(require_staff_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    db, user, school = tenant
    return _run(lambda: erp_transport.my_trips(db, school.id, user, page=page, page_size=page_size))


@router.post("/trips/{trip_id}/gps", responses=json_response(TransportGpsPointOut))
def staff_post_gps(
    trip_id: int,
    body: TransportGpsBody,
    tenant: Tuple[Session, User, School] = Depends(require_staff_user),
):
    db, user, school = tenant
    return _run(
        lambda: erp_transport.post_gps_as_staff(db, school.id, user, trip_id, body.lat, body.lng)
    )


@router.post("/trips/{trip_id}/attendance", responses=json_response(TransportAttendanceEventOut))
def staff_post_attendance(
    trip_id: int,
    body: TransportAttendanceBody,
    tenant: Tuple[Session, User, School] = Depends(require_staff_user),
):
    db, user, school = tenant
    return _run(
        lambda: erp_transport.post_attendance_as_staff(
            db,
            school.id,
            user,
            trip_id,
            student_id=body.student_id,
            event_type=body.event_type,
            stop_id=body.stop_id,
        )
    )
