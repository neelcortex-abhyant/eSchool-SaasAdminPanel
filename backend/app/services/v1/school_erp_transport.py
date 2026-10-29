"""Transport ERP: driver/helper, capacity, trips, GPS polling, board/drop."""

from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tables import (
    Staff,
    Student,
    StudentTransportAssignment,
    TransportAttendanceEvent,
    TransportGpsPoint,
    TransportRoute,
    TransportStop,
    TransportTrip,
    TransportVehicle,
    User,
)
from app.services.v1.school_academics import AcademicError, _commit, _envelope, _now, _owned, _page
from app.services.v1.school_offline_exams import _guardian_children

TRIP_STATUSES = frozenset({"scheduled", "in_progress", "completed", "cancelled"})
EVENT_TYPES = frozenset({"board", "drop"})
# Ops contract: admin-web treats >5m as stale, >30m as offline.
GPS_STALE_SECONDS = 5 * 60
GPS_OFFLINE_SECONDS = 30 * 60
DEFAULT_POLL_SECONDS = 15


def gps_freshness(recorded_at: datetime | None, *, now: datetime | None = None) -> str:
    """Classify GPS age: live | stale | offline | missing."""
    if recorded_at is None:
        return "missing"
    ref = now or _now()
    age = (ref - recorded_at).total_seconds()
    if age <= GPS_STALE_SECONDS:
        return "live"
    if age <= GPS_OFFLINE_SECONDS:
        return "stale"
    return "offline"


def _latest_gps_for_trip(db: Session, school_id: int, trip_id: int) -> TransportGpsPoint | None:
    return (
        db.query(TransportGpsPoint)
        .filter(
            TransportGpsPoint.school_id == school_id,
            TransportGpsPoint.trip_id == trip_id,
        )
        .order_by(TransportGpsPoint.recorded_at.desc(), TransportGpsPoint.id.desc())
        .first()
    )


def _driver_name(db: Session, staff_id: int | None) -> str | None:
    if staff_id is None:
        return None
    staff = db.get(Staff, staff_id)
    if staff is None:
        return None
    user = db.get(User, staff.user_id)
    if user is None:
        return None
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or None


def get_trip(db: Session, school_id: int, trip_id: int) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    data = _trip_dict(trip)
    route = db.get(TransportRoute, trip.route_id)
    vehicle = db.get(TransportVehicle, trip.vehicle_id)
    data["route_name"] = route.name if route else None
    data["registration_no"] = vehicle.registration_no if vehicle else None
    data["driver_name"] = _driver_name(db, trip.driver_staff_id)
    point = _latest_gps_for_trip(db, school_id, trip.id)
    now = _now()
    if point is None:
        data["latest_gps"] = None
        data["freshness"] = "missing"
    else:
        data["latest_gps"] = {
            "lat": point.lat,
            "lng": point.lng,
            "recorded_at": point.recorded_at.isoformat() if point.recorded_at else None,
            "freshness": gps_freshness(point.recorded_at, now=now),
        }
        data["freshness"] = data["latest_gps"]["freshness"]
    data["server_time"] = now.isoformat()
    data["poll_seconds"] = DEFAULT_POLL_SECONDS
    return data


def list_vehicle_locations(db: Session, school_id: int) -> dict:
    """Latest GPS per vehicle for in-progress trips (School Admin map poll)."""
    now = _now()
    trips = (
        db.query(TransportTrip)
        .filter(
            TransportTrip.school_id == school_id,
            TransportTrip.deleted_at.is_(None),
            TransportTrip.status == "in_progress",
        )
        .order_by(TransportTrip.id.desc())
        .all()
    )
    # One trip per vehicle (newest wins).
    by_vehicle: dict[int, TransportTrip] = {}
    for trip in trips:
        if trip.vehicle_id not in by_vehicle:
            by_vehicle[trip.vehicle_id] = trip

    items: list[dict] = []
    for vehicle_id, trip in by_vehicle.items():
        vehicle = db.get(TransportVehicle, vehicle_id)
        route = db.get(TransportRoute, trip.route_id)
        point = _latest_gps_for_trip(db, school_id, trip.id)
        freshness = gps_freshness(point.recorded_at if point else None, now=now)
        items.append(
            {
                "vehicle_id": vehicle_id,
                "registration_no": vehicle.registration_no if vehicle else None,
                "vehicle_name": vehicle.name if vehicle else None,
                "route_id": trip.route_id,
                "route_name": route.name if route else None,
                "driver_staff_id": trip.driver_staff_id,
                "driver_name": _driver_name(db, trip.driver_staff_id),
                "trip_id": trip.id,
                "trip_status": trip.status,
                "latitude": point.lat if point else None,
                "longitude": point.lng if point else None,
                "recorded_at": point.recorded_at.isoformat() if point and point.recorded_at else None,
                "freshness": freshness,
            }
        )
    items.sort(key=lambda row: row["vehicle_id"])
    return {
        "items": items,
        "total": len(items),
        "server_time": now.isoformat(),
        "poll_seconds": DEFAULT_POLL_SECONDS,
        "stale_after_seconds": GPS_STALE_SECONDS,
        "offline_after_seconds": GPS_OFFLINE_SECONDS,
    }


def _staff_same_school(db: Session, school_id: int, staff_id: int | None) -> Staff | None:
    if staff_id is None:
        return None
    staff = (
        db.query(Staff)
        .filter(Staff.id == int(staff_id), Staff.school_id == school_id)
        .first()
    )
    if staff is None:
        raise AcademicError(422, "Staff not found in this school")
    return staff


def _vehicle_item(row: TransportVehicle) -> dict:
    return {
        "id": row.id,
        "school_id": row.school_id,
        "name": row.name,
        "registration_no": row.registration_no,
        "capacity": row.capacity,
        "driver_staff_id": row.driver_staff_id,
        "helper_staff_id": row.helper_staff_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def update_vehicle_staff_fields(
    db: Session, school_id: int, row: TransportVehicle, body: dict
) -> None:
    """Validate and apply driver_staff_id / helper_staff_id on a vehicle row (no commit)."""
    if "driver_staff_id" in body:
        val = body["driver_staff_id"]
        if val is None:
            row.driver_staff_id = None
        else:
            _staff_same_school(db, school_id, int(val))
            row.driver_staff_id = int(val)
    if "helper_staff_id" in body:
        val = body["helper_staff_id"]
        if val is None:
            row.helper_staff_id = None
        else:
            _staff_same_school(db, school_id, int(val))
            row.helper_staff_id = int(val)


def assert_route_vehicle_capacity(db: Session, school_id: int, route_id: int) -> None:
    """Raise 409 if active assignments on the route's vehicle already meet capacity."""
    route = _owned(db, TransportRoute, route_id, school_id)
    if route.vehicle_id is None:
        return
    vehicle = _owned(db, TransportVehicle, route.vehicle_id, school_id)
    if vehicle.capacity is None:
        return
    route_ids = [
        r.id
        for r in db.query(TransportRoute)
        .filter(
            TransportRoute.school_id == school_id,
            TransportRoute.vehicle_id == vehicle.id,
            TransportRoute.deleted_at.is_(None),
        )
        .all()
    ]
    count = (
        db.query(func.count(StudentTransportAssignment.id))
        .filter(
            StudentTransportAssignment.school_id == school_id,
            StudentTransportAssignment.route_id.in_(route_ids),
            StudentTransportAssignment.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    if int(count) >= int(vehicle.capacity):
        raise AcademicError(409, "Vehicle capacity reached for this route")


def _trip_dict(row: TransportTrip) -> dict:
    return {
        "id": row.id,
        "school_id": row.school_id,
        "route_id": row.route_id,
        "vehicle_id": row.vehicle_id,
        "driver_staff_id": row.driver_staff_id,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_trips(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    route_id: int | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    q = db.query(TransportTrip).filter(
        TransportTrip.school_id == school_id,
        TransportTrip.deleted_at.is_(None),
    )
    if status:
        q = q.filter(TransportTrip.status == status)
    if route_id is not None:
        q = q.filter(TransportTrip.route_id == route_id)
    total = q.count()
    rows = q.order_by(TransportTrip.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_trip_dict(r) for r in rows], total, page, page_size)


def create_trip(db: Session, school_id: int, body: dict) -> dict:
    route_id = int(body.get("route_id") or 0)
    if not route_id:
        raise AcademicError(422, "route_id is required")
    route = _owned(db, TransportRoute, route_id, school_id)
    vehicle_id = body.get("vehicle_id")
    if vehicle_id is None:
        vehicle_id = route.vehicle_id
    if vehicle_id is None:
        raise AcademicError(422, "vehicle_id is required (route has no vehicle)")
    vehicle = _owned(db, TransportVehicle, int(vehicle_id), school_id)
    driver_staff_id = body.get("driver_staff_id")
    if driver_staff_id is None:
        driver_staff_id = vehicle.driver_staff_id
    if driver_staff_id is not None:
        _staff_same_school(db, school_id, int(driver_staff_id))
    row = TransportTrip(
        school_id=school_id,
        route_id=route.id,
        vehicle_id=vehicle.id,
        driver_staff_id=int(driver_staff_id) if driver_staff_id is not None else None,
        status="scheduled",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _trip_dict(row)


def start_trip(db: Session, school_id: int, trip_id: int) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.status not in ("scheduled",):
        raise AcademicError(422, "Only scheduled trips can be started")
    trip.status = "in_progress"
    trip.started_at = _now()
    trip.updated_at = _now()
    _commit(db)
    return _trip_dict(trip)


def complete_trip(db: Session, school_id: int, trip_id: int) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.status != "in_progress":
        raise AcademicError(422, "Only in-progress trips can be completed")
    trip.status = "completed"
    trip.ended_at = _now()
    trip.updated_at = _now()
    _commit(db)
    return _trip_dict(trip)


def cancel_trip(db: Session, school_id: int, trip_id: int) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.status in ("completed", "cancelled"):
        raise AcademicError(422, "Trip already finished")
    trip.status = "cancelled"
    trip.ended_at = _now()
    trip.updated_at = _now()
    _commit(db)
    return _trip_dict(trip)


def soft_delete_trip(db: Session, school_id: int, trip_id: int) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    trip.deleted_at = _now()
    trip.updated_at = _now()
    _commit(db)
    return {"id": trip.id, "deleted": True}


def _gps_retention_expires(now: datetime) -> datetime | None:
    days = getattr(get_settings(), "gps_retention_days", None)
    if days is None:
        return None
    try:
        d = int(days)
    except (TypeError, ValueError):
        return None
    if d <= 0:
        return None
    return now + timedelta(days=d)


def post_gps(
    db: Session,
    school_id: int,
    trip_id: int,
    lat: float,
    lng: float,
    staff_id: int | None = None,
) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.status != "in_progress":
        raise AcademicError(422, "GPS accepted only for in-progress trips")
    now = _now()
    point = TransportGpsPoint(
        school_id=school_id,
        trip_id=trip.id,
        vehicle_id=trip.vehicle_id,
        lat=float(lat),
        lng=float(lng),
        recorded_at=now,
        staff_id=staff_id,
        expires_at=_gps_retention_expires(now),
        created_at=now,
        updated_at=now,
    )
    db.add(point)
    _commit(db)
    db.refresh(point)
    return {
        "id": point.id,
        "trip_id": point.trip_id,
        "vehicle_id": point.vehicle_id,
        "lat": point.lat,
        "lng": point.lng,
        "recorded_at": point.recorded_at.isoformat(),
        "staff_id": point.staff_id,
        "expires_at": point.expires_at.isoformat() if point.expires_at else None,
    }


def post_attendance(
    db: Session,
    school_id: int,
    trip_id: int,
    *,
    student_id: int,
    event_type: str,
    stop_id: int | None = None,
) -> dict:
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.status not in ("in_progress", "scheduled"):
        raise AcademicError(422, "Attendance only for active trips")
    event_type = str(event_type or "").strip().lower()
    if event_type not in EVENT_TYPES:
        raise AcademicError(422, "event_type must be board or drop")
    _owned(db, Student, student_id, school_id)
    if stop_id is not None:
        stop = _owned(db, TransportStop, int(stop_id), school_id)
        if stop.route_id != trip.route_id:
            raise AcademicError(422, "stop does not belong to trip route")

    existing_same = (
        db.query(TransportAttendanceEvent)
        .filter(
            TransportAttendanceEvent.school_id == school_id,
            TransportAttendanceEvent.trip_id == trip.id,
            TransportAttendanceEvent.student_id == student_id,
            TransportAttendanceEvent.event_type == event_type,
            TransportAttendanceEvent.deleted_at.is_(None),
        )
        .first()
    )
    if existing_same:
        raise AcademicError(409, f"Duplicate {event_type} event for student on this trip")

    if event_type == "drop":
        boarded = (
            db.query(TransportAttendanceEvent)
            .filter(
                TransportAttendanceEvent.school_id == school_id,
                TransportAttendanceEvent.trip_id == trip.id,
                TransportAttendanceEvent.student_id == student_id,
                TransportAttendanceEvent.event_type == "board",
                TransportAttendanceEvent.deleted_at.is_(None),
            )
            .first()
        )
        if boarded is None:
            raise AcademicError(422, "Student must board before drop")

    now = _now()
    row = TransportAttendanceEvent(
        school_id=school_id,
        trip_id=trip.id,
        student_id=student_id,
        stop_id=int(stop_id) if stop_id is not None else None,
        event_type=event_type,
        recorded_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {
        "id": row.id,
        "trip_id": row.trip_id,
        "student_id": row.student_id,
        "stop_id": row.stop_id,
        "event_type": row.event_type,
        "recorded_at": row.recorded_at.isoformat(),
    }


def list_trip_attendance(db: Session, school_id: int, trip_id: int) -> dict:
    _owned(db, TransportTrip, trip_id, school_id)
    rows = (
        db.query(TransportAttendanceEvent)
        .filter(
            TransportAttendanceEvent.school_id == school_id,
            TransportAttendanceEvent.trip_id == trip_id,
            TransportAttendanceEvent.deleted_at.is_(None),
        )
        .order_by(TransportAttendanceEvent.recorded_at.asc(), TransportAttendanceEvent.id.asc())
        .all()
    )
    items = [
        {
            "id": r.id,
            "trip_id": r.trip_id,
            "student_id": r.student_id,
            "stop_id": r.stop_id,
            "event_type": r.event_type,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def trips_report(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    q = db.query(TransportTrip).filter(
        TransportTrip.school_id == school_id,
        TransportTrip.deleted_at.is_(None),
    )
    if from_dt is not None:
        q = q.filter(TransportTrip.created_at >= from_dt)
    if to_dt is not None:
        q = q.filter(TransportTrip.created_at <= to_dt)
    total = q.count()
    rows = q.order_by(TransportTrip.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for t in rows:
        gps_count = (
            db.query(func.count(TransportGpsPoint.id))
            .filter(TransportGpsPoint.trip_id == t.id, TransportGpsPoint.school_id == school_id)
            .scalar()
            or 0
        )
        att_count = (
            db.query(func.count(TransportAttendanceEvent.id))
            .filter(
                TransportAttendanceEvent.trip_id == t.id,
                TransportAttendanceEvent.school_id == school_id,
                TransportAttendanceEvent.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
        item = _trip_dict(t)
        item["gps_points"] = int(gps_count)
        item["attendance_events"] = int(att_count)
        items.append(item)
    return _envelope(items, total, page, page_size)


def staff_for_user(db: Session, school_id: int, user: User) -> Staff:
    staff = (
        db.query(Staff)
        .filter(Staff.user_id == user.id, Staff.school_id == school_id)
        .first()
    )
    if staff is None:
        raise AcademicError(403, "Staff profile not found")
    return staff


def my_trips(db: Session, school_id: int, user: User, *, page: int = 1, page_size: int = 20) -> dict:
    staff = staff_for_user(db, school_id, user)
    page, page_size = _page(page, page_size)
    q = db.query(TransportTrip).filter(
        TransportTrip.school_id == school_id,
        TransportTrip.deleted_at.is_(None),
        TransportTrip.driver_staff_id == staff.id,
    )
    total = q.count()
    rows = q.order_by(TransportTrip.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_trip_dict(r) for r in rows], total, page, page_size)


def post_gps_as_staff(
    db: Session, school_id: int, user: User, trip_id: int, lat: float, lng: float
) -> dict:
    staff = staff_for_user(db, school_id, user)
    trip = _owned(db, TransportTrip, trip_id, school_id)
    if trip.driver_staff_id and trip.driver_staff_id != staff.id:
        # Allow helper on vehicle as well
        vehicle = _owned(db, TransportVehicle, trip.vehicle_id, school_id)
        if vehicle.helper_staff_id != staff.id and vehicle.driver_staff_id != staff.id:
            raise AcademicError(403, "Not assigned to this trip vehicle")
    return post_gps(db, school_id, trip_id, lat, lng, staff_id=staff.id)


def post_attendance_as_staff(
    db: Session,
    school_id: int,
    user: User,
    trip_id: int,
    *,
    student_id: int,
    event_type: str,
    stop_id: int | None = None,
) -> dict:
    staff_for_user(db, school_id, user)
    return post_attendance(
        db, school_id, trip_id, student_id=student_id, event_type=event_type, stop_id=stop_id
    )


def parent_child_bus_status(db: Session, school_id: int, parent: User, student_id: int) -> dict:
    children = _guardian_children(db, parent, school_id)
    if student_id not in {c.id for c in children}:
        raise AcademicError(404, "Record not found")
    assignment = (
        db.query(StudentTransportAssignment)
        .filter(
            StudentTransportAssignment.school_id == school_id,
            StudentTransportAssignment.student_id == student_id,
            StudentTransportAssignment.deleted_at.is_(None),
        )
        .first()
    )
    if assignment is None:
        return {
            "student_id": student_id,
            "assignment": None,
            "active_trip": None,
            "latest_gps": None,
        }
    route = db.get(TransportRoute, assignment.route_id)
    active_trip = (
        db.query(TransportTrip)
        .filter(
            TransportTrip.school_id == school_id,
            TransportTrip.route_id == assignment.route_id,
            TransportTrip.status == "in_progress",
            TransportTrip.deleted_at.is_(None),
        )
        .order_by(TransportTrip.id.desc())
        .first()
    )
    latest_gps = None
    if active_trip:
        point = (
            db.query(TransportGpsPoint)
            .filter(
                TransportGpsPoint.school_id == school_id,
                TransportGpsPoint.trip_id == active_trip.id,
            )
            .order_by(TransportGpsPoint.recorded_at.desc())
            .first()
        )
        if point:
            latest_gps = {
                "lat": point.lat,
                "lng": point.lng,
                "recorded_at": point.recorded_at.isoformat(),
            }
    return {
        "student_id": student_id,
        "assignment": {
            "id": assignment.id,
            "route_id": assignment.route_id,
            "route_name": route.name if route else None,
            "stop_id": assignment.stop_id,
            "vehicle_id": route.vehicle_id if route else None,
        },
        "active_trip": _trip_dict(active_trip) if active_trip else None,
        "latest_gps": latest_gps,
    }
