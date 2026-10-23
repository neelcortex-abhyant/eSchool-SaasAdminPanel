"""School-admin class timetable entries (Module 1).

Classroom scheduling is deferred (no classroom entity). Working days are Mon–Sat.

Concurrency
-----------
Application overlap checks alone are not safe when no matching rows exist:
``SELECT … FOR UPDATE`` locks nothing on an empty set. Writes therefore take
**transaction-scoped PostgreSQL advisory locks** keyed by:

- school + session + class_section + day
- school + session + teacher + day

Locks are acquired in sorted label order (old + new keys on update) before
conflict queries. Soft-delete uses the same class/teacher keys. On non-PostgreSQL
dialects locks are skipped (tests that are not on Postgres do not prove safety).
"""

from __future__ import annotations

import hashlib
from datetime import time
from typing import Any, Iterable

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    ClassTimetableEntry,
    SchoolClass,
    Section,
    SessionYear,
    Subject,
    TeacherAssignment,
    User,
)
from app.services.v1.school_academics import (
    AcademicError,
    _assert_subject_mapped_to_class,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
    _same_school,
    _staff_for_teacher_user,
    _user_name,
)

WORKING_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
WORKING_DAY_SET = frozenset(WORKING_DAYS)
DAY_SORT_ORDER = {name: index for index, name in enumerate(WORKING_DAYS)}


def _is_postgresql(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _class_schedule_lock_label(
    school_id: int, session_year_id: int, class_section_id: int, day: str
) -> str:
    return f"tt:cs:{school_id}:{session_year_id}:{class_section_id}:{day}"


def _teacher_schedule_lock_label(
    school_id: int, session_year_id: int, teacher_user_id: int, day: str
) -> str:
    return f"tt:teacher:{school_id}:{session_year_id}:{teacher_user_id}:{day}"


def _schedule_lock_labels(
    school_id: int,
    *,
    session_year_id: int,
    class_section_id: int,
    teacher_user_id: int,
    day: str,
) -> list[str]:
    return [
        _class_schedule_lock_label(school_id, session_year_id, class_section_id, day),
        _teacher_schedule_lock_label(school_id, session_year_id, teacher_user_id, day),
    ]


def _advisory_lock_key(label: str) -> int:
    """Stable signed 64-bit key for ``pg_advisory_xact_lock(bigint)``."""
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _acquire_timetable_advisory_locks(db: Session, labels: Iterable[str]) -> None:
    """Take transaction-scoped advisory locks in deterministic sorted order.

    No-op on non-PostgreSQL engines. Does not commit — caller owns the transaction.
    """
    if not _is_postgresql(db):
        return
    for label in sorted(set(labels)):
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _advisory_lock_key(label)},
        )


def _normalize_day(raw: Any) -> str:
    if raw is None or not str(raw).strip():
        raise AcademicError(422, "day is required")
    value = str(raw).strip().lower()
    if value not in WORKING_DAY_SET:
        raise AcademicError(422, "day must be Monday through Saturday")
    return value


def _parse_time(raw: Any, field: str) -> time:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise AcademicError(422, f"{field} is required")
    if isinstance(raw, time):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw).strip()
    for fmt_len, parts in ((5, 2), (8, 3)):
        if len(text) >= fmt_len and text[2] == ":":
            try:
                chunks = text[:fmt_len].split(":")
                if len(chunks) < parts:
                    continue
                hour = int(chunks[0])
                minute = int(chunks[1])
                second = int(chunks[2]) if len(chunks) > 2 else 0
                return time(hour=hour, minute=minute, second=second)
            except ValueError:
                break
    raise AcademicError(422, f"{field} must be HH:MM or HH:MM:SS")


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


def _assert_time_order(start: time, end: time) -> None:
    if end <= start:
        raise AcademicError(422, "end_time must be after start_time")


def _owned_entry(db: Session, school_id: int, entry_id: int) -> ClassTimetableEntry:
    return _owned(db, ClassTimetableEntry, entry_id, school_id)


def _active_session(db: Session, school_id: int, session_year_id: int) -> SessionYear:
    row = _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    return row


def _active_class_section(db: Session, school_id: int, class_section_id: int) -> ClassSection:
    return _same_school(db, ClassSection, class_section_id, school_id, "Class section")


def _assert_teacher_assignment(
    db: Session,
    school_id: int,
    *,
    staff_id: int,
    subject_id: int,
    class_section_id: int,
    session_year_id: int,
) -> None:
    """Require an active TeacherAssignment covering this subject and scope.

    Null class_section_id / session_year_id on an assignment means “any” within
    the school for that dimension (same semantics as assignment uniqueness).
    """
    rows = (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.staff_id == staff_id,
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.deleted_at.is_(None),
            or_(
                TeacherAssignment.class_section_id.is_(None),
                TeacherAssignment.class_section_id == class_section_id,
            ),
            or_(
                TeacherAssignment.session_year_id.is_(None),
                TeacherAssignment.session_year_id == session_year_id,
            ),
        )
        .all()
    )
    if not rows:
        raise AcademicError(
            422,
            "Teacher has no active assignment for this subject and class/session scope",
        )


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and a_end > b_start


def _assert_no_class_overlap(
    db: Session,
    school_id: int,
    *,
    session_year_id: int,
    class_section_id: int,
    day: str,
    start_time: time,
    end_time: time,
    exclude_id: int | None,
) -> None:
    """Require matching advisory locks already held for this class-section/day."""
    query = db.query(ClassTimetableEntry).filter(
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.session_year_id == session_year_id,
        ClassTimetableEntry.class_section_id == class_section_id,
        ClassTimetableEntry.day == day,
        ClassTimetableEntry.deleted_at.is_(None),
    )
    if exclude_id is not None:
        query = query.filter(ClassTimetableEntry.id != exclude_id)
    for row in query.order_by(ClassTimetableEntry.id).all():
        if _overlaps(start_time, end_time, row.start_time, row.end_time):
            raise AcademicError(409, "Timetable period overlaps an existing class period")


def _assert_no_teacher_overlap(
    db: Session,
    school_id: int,
    *,
    session_year_id: int,
    teacher_user_id: int,
    day: str,
    start_time: time,
    end_time: time,
    exclude_id: int | None,
) -> None:
    """Require matching advisory locks already held for this teacher/day."""
    query = db.query(ClassTimetableEntry).filter(
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.session_year_id == session_year_id,
        ClassTimetableEntry.teacher_user_id == teacher_user_id,
        ClassTimetableEntry.day == day,
        ClassTimetableEntry.deleted_at.is_(None),
    )
    if exclude_id is not None:
        query = query.filter(ClassTimetableEntry.id != exclude_id)
    for row in query.order_by(ClassTimetableEntry.id).all():
        if _overlaps(start_time, end_time, row.start_time, row.end_time):
            raise AcademicError(409, "Teacher is already scheduled for an overlapping period")


def _assert_schedule_conflicts(
    db: Session,
    school_id: int,
    *,
    session_year_id: int,
    class_section_id: int,
    teacher_user_id: int,
    day: str,
    start_time: time,
    end_time: time,
    exclude_id: int | None,
) -> None:
    _assert_no_class_overlap(
        db,
        school_id,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        day=day,
        start_time=start_time,
        end_time=end_time,
        exclude_id=exclude_id,
    )
    _assert_no_teacher_overlap(
        db,
        school_id,
        session_year_id=session_year_id,
        teacher_user_id=teacher_user_id,
        day=day,
        start_time=start_time,
        end_time=end_time,
        exclude_id=exclude_id,
    )


def _entry_item(db: Session, row: ClassTimetableEntry) -> dict:
    subject = db.get(Subject, row.subject_id)
    teacher = db.get(User, row.teacher_user_id)
    link = db.get(ClassSection, row.class_section_id)
    klass = db.get(SchoolClass, link.class_id) if link is not None else None
    section = db.get(Section, link.section_id) if link is not None else None
    return {
        "id": row.id,
        "entry_id": row.id,
        "session_year_id": row.session_year_id,
        "class_section_id": row.class_section_id,
        "class_id": link.class_id if link is not None else None,
        "section_id": link.section_id if link is not None else None,
        "class_name": klass.name if klass is not None else None,
        "section_name": section.name if section is not None else None,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject is not None else None,
        "teacher_user_id": row.teacher_user_id,
        "teacher_name": _user_name(teacher),
        "staff_id": row.staff_id,
        "day": row.day,
        "start_time": _format_time(row.start_time),
        "end_time": _format_time(row.end_time),
        "note": row.note,
    }


def _require_timetable_teacher(db: Session, school_id: int, teacher_user_id: int) -> User:
    """Same-school Teacher with Staff row and active account, or 404."""
    from app.services.v1.school_teachers import _owned_teacher

    user, _staff = _owned_teacher(db, school_id, teacher_user_id)
    if getattr(user, "status", 1) != 1:
        raise AcademicError(404, "Teacher not found")
    return user


def _teacher_entries_query(
    db: Session,
    school_id: int,
    *,
    teacher_user_id: int,
    session_year_id: int,
    day: str | None = None,
):
    query = db.query(ClassTimetableEntry).filter(
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.teacher_user_id == teacher_user_id,
        ClassTimetableEntry.session_year_id == session_year_id,
        ClassTimetableEntry.deleted_at.is_(None),
    )
    if day is not None:
        query = query.filter(ClassTimetableEntry.day == day)
    return query


def list_teacher_timetable(
    db: Session,
    school_id: int,
    teacher_user_id: int,
    *,
    session_year_id: int,
    day: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated periods for one teacher in a session (optional day filter)."""
    _require_timetable_teacher(db, school_id, teacher_user_id)
    _active_session(db, school_id, session_year_id)
    day_filter = _normalize_day(day) if day is not None and str(day).strip() else None
    page, page_size = _page(page, page_size)
    query = _teacher_entries_query(
        db,
        school_id,
        teacher_user_id=teacher_user_id,
        session_year_id=session_year_id,
        day=day_filter,
    )
    rows = query.all()
    rows.sort(key=lambda row: (DAY_SORT_ORDER.get(row.day, 99), row.start_time, row.id))
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    return _envelope([_entry_item(db, row) for row in page_rows], total, page, page_size)


def teacher_daily_timetable(
    db: Session,
    school_id: int,
    teacher_user_id: int,
    *,
    session_year_id: int,
    day: str,
) -> dict:
    user = _require_timetable_teacher(db, school_id, teacher_user_id)
    _active_session(db, school_id, session_year_id)
    day_norm = _normalize_day(day)
    rows = (
        _teacher_entries_query(
            db,
            school_id,
            teacher_user_id=teacher_user_id,
            session_year_id=session_year_id,
            day=day_norm,
        )
        .all()
    )
    rows.sort(key=lambda row: (row.start_time, row.id))
    return {
        "teacher_user_id": teacher_user_id,
        "teacher_name": _user_name(user),
        "session_year_id": session_year_id,
        "day": day_norm,
        "entries": [_entry_item(db, row) for row in rows],
    }


def teacher_weekly_timetable(
    db: Session,
    school_id: int,
    teacher_user_id: int,
    *,
    session_year_id: int,
) -> dict:
    user = _require_timetable_teacher(db, school_id, teacher_user_id)
    _active_session(db, school_id, session_year_id)
    rows = _teacher_entries_query(
        db,
        school_id,
        teacher_user_id=teacher_user_id,
        session_year_id=session_year_id,
    ).all()
    rows.sort(key=lambda row: (DAY_SORT_ORDER.get(row.day, 99), row.start_time, row.id))
    by_day: dict[str, list[dict]] = {name: [] for name in WORKING_DAYS}
    for row in rows:
        if row.day in by_day:
            by_day[row.day].append(_entry_item(db, row))
    return {
        "teacher_user_id": teacher_user_id,
        "teacher_name": _user_name(user),
        "session_year_id": session_year_id,
        "days": [{"day": name, "entries": by_day[name]} for name in WORKING_DAYS],
    }


def check_teacher_availability(
    db: Session,
    school_id: int,
    teacher_user_id: int,
    *,
    session_year_id: int,
    day: str,
    start_time: Any,
    end_time: Any,
    exclude_entry_id: int | None = None,
) -> dict:
    """Read-only availability check (no advisory locks — writes re-validate under locks)."""
    user = _require_timetable_teacher(db, school_id, teacher_user_id)
    _active_session(db, school_id, session_year_id)
    day_norm = _normalize_day(day)
    start = _parse_time(start_time, "start_time")
    end = _parse_time(end_time, "end_time")
    _assert_time_order(start, end)

    exclude_id: int | None = None
    if exclude_entry_id is not None:
        # Only exclude an active same-school entry (typically the row being updated).
        existing = db.get(ClassTimetableEntry, int(exclude_entry_id))
        if (
            existing is not None
            and existing.school_id == school_id
            and existing.deleted_at is None
        ):
            exclude_id = existing.id

    query = _teacher_entries_query(
        db,
        school_id,
        teacher_user_id=teacher_user_id,
        session_year_id=session_year_id,
        day=day_norm,
    )
    if exclude_id is not None:
        query = query.filter(ClassTimetableEntry.id != exclude_id)

    conflicts: list[dict] = []
    for row in query.order_by(ClassTimetableEntry.start_time, ClassTimetableEntry.id).all():
        if _overlaps(start, end, row.start_time, row.end_time):
            item = _entry_item(db, row)
            conflicts.append(
                {
                    "entry_id": item["entry_id"],
                    "day": item["day"],
                    "start_time": item["start_time"],
                    "end_time": item["end_time"],
                    "class_section_id": item["class_section_id"],
                    "class_id": item["class_id"],
                    "section_id": item["section_id"],
                    "class_name": item["class_name"],
                    "section_name": item["section_name"],
                    "subject_id": item["subject_id"],
                    "subject_name": item["subject_name"],
                }
            )

    return {
        "available": len(conflicts) == 0,
        "teacher_user_id": teacher_user_id,
        "teacher_name": _user_name(user),
        "session_year_id": session_year_id,
        "day": day_norm,
        "start_time": _format_time(start),
        "end_time": _format_time(end),
        "exclude_entry_id": exclude_id,
        "conflicts": conflicts,
    }


def _resolve_write_fields(
    db: Session,
    school_id: int,
    body: dict,
    *,
    existing: ClassTimetableEntry | None,
) -> dict:
    if existing is None:
        required = (
            "session_year_id",
            "class_section_id",
            "subject_id",
            "teacher_user_id",
            "day",
            "start_time",
            "end_time",
        )
        for field in required:
            if field not in body or body[field] is None or body[field] == "":
                raise AcademicError(422, f"{field} is required")

    session_year_id = (
        int(body["session_year_id"])
        if "session_year_id" in body
        else existing.session_year_id  # type: ignore[union-attr]
    )
    class_section_id = (
        int(body["class_section_id"])
        if "class_section_id" in body
        else existing.class_section_id  # type: ignore[union-attr]
    )
    subject_id = (
        int(body["subject_id"]) if "subject_id" in body else existing.subject_id  # type: ignore[union-attr]
    )
    teacher_user_id = (
        int(body["teacher_user_id"])
        if "teacher_user_id" in body
        else existing.teacher_user_id  # type: ignore[union-attr]
    )
    day = _normalize_day(body["day"] if "day" in body else existing.day)  # type: ignore[union-attr]
    start_time = _parse_time(
        body["start_time"] if "start_time" in body else existing.start_time,  # type: ignore[union-attr]
        "start_time",
    )
    end_time = _parse_time(
        body["end_time"] if "end_time" in body else existing.end_time,  # type: ignore[union-attr]
        "end_time",
    )
    _assert_time_order(start_time, end_time)

    if "note" in body:
        note_raw = body.get("note")
        note = None if note_raw is None else (str(note_raw).strip() or None)
        if note is not None and len(note) > 512:
            raise AcademicError(422, "note must be at most 512 characters")
    else:
        note = existing.note if existing is not None else None

    _active_session(db, school_id, session_year_id)
    link = _active_class_section(db, school_id, class_section_id)
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, link.class_id, subject_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )

    return {
        "session_year_id": session_year_id,
        "class_section_id": class_section_id,
        "subject_id": subject_id,
        "teacher_user_id": teacher_user_id,
        "staff_id": staff.id,
        "day": day,
        "start_time": start_time,
        "end_time": end_time,
        "note": note,
    }


def create_entry(db: Session, school_id: int, body: dict) -> dict:
    fields = _resolve_write_fields(db, school_id, body, existing=None)
    _acquire_timetable_advisory_locks(
        db,
        _schedule_lock_labels(
            school_id,
            session_year_id=fields["session_year_id"],
            class_section_id=fields["class_section_id"],
            teacher_user_id=fields["teacher_user_id"],
            day=fields["day"],
        ),
    )
    _assert_schedule_conflicts(
        db,
        school_id,
        session_year_id=fields["session_year_id"],
        class_section_id=fields["class_section_id"],
        teacher_user_id=fields["teacher_user_id"],
        day=fields["day"],
        start_time=fields["start_time"],
        end_time=fields["end_time"],
        exclude_id=None,
    )
    row = ClassTimetableEntry(
        school_id=school_id,
        session_year_id=fields["session_year_id"],
        class_section_id=fields["class_section_id"],
        subject_id=fields["subject_id"],
        teacher_user_id=fields["teacher_user_id"],
        staff_id=fields["staff_id"],
        day=fields["day"],
        start_time=fields["start_time"],
        end_time=fields["end_time"],
        note=fields["note"],
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _entry_item(db, row)


def list_entries(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    session_year_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    class_section_id: int | None = None,
    day: str | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(ClassTimetableEntry).filter(
        ClassTimetableEntry.school_id == school_id,
        ClassTimetableEntry.deleted_at.is_(None),
    )
    if session_year_id is not None:
        _active_session(db, school_id, session_year_id)
        query = query.filter(ClassTimetableEntry.session_year_id == session_year_id)
    if class_section_id is not None:
        _active_class_section(db, school_id, class_section_id)
        query = query.filter(ClassTimetableEntry.class_section_id == class_section_id)
    if class_id is not None or section_id is not None:
        query = query.join(
            ClassSection,
            and_(
                ClassSection.id == ClassTimetableEntry.class_section_id,
                ClassSection.school_id == school_id,
                ClassSection.deleted_at.is_(None),
            ),
        )
        if class_id is not None:
            _owned(db, SchoolClass, class_id, school_id)
            query = query.filter(ClassSection.class_id == class_id)
        if section_id is not None:
            _same_school(db, Section, section_id, school_id, "Section")
            query = query.filter(ClassSection.section_id == section_id)
    if day is not None and str(day).strip():
        query = query.filter(ClassTimetableEntry.day == _normalize_day(day))

    total = query.count()
    rows = query.order_by(ClassTimetableEntry.id.asc()).all()
    # Stable day + start_time order (day stored as normalized strings).
    rows.sort(
        key=lambda row: (
            DAY_SORT_ORDER.get(row.day, 99),
            row.start_time,
            row.id,
        )
    )
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    return _envelope([_entry_item(db, row) for row in page_rows], total, page, page_size)


def get_entry(db: Session, school_id: int, entry_id: int) -> dict:
    return _entry_item(db, _owned_entry(db, school_id, entry_id))


def update_entry(db: Session, school_id: int, entry_id: int, body: dict) -> dict:
    row = _owned_entry(db, school_id, entry_id)
    if not body:
        return _entry_item(db, row)
    fields = _resolve_write_fields(db, school_id, body, existing=row)
    # Old + new schedule keys; sorted unique acquisition avoids deadlocks.
    _acquire_timetable_advisory_locks(
        db,
        _schedule_lock_labels(
            school_id,
            session_year_id=row.session_year_id,
            class_section_id=row.class_section_id,
            teacher_user_id=row.teacher_user_id,
            day=row.day,
        )
        + _schedule_lock_labels(
            school_id,
            session_year_id=fields["session_year_id"],
            class_section_id=fields["class_section_id"],
            teacher_user_id=fields["teacher_user_id"],
            day=fields["day"],
        ),
    )
    _assert_schedule_conflicts(
        db,
        school_id,
        session_year_id=fields["session_year_id"],
        class_section_id=fields["class_section_id"],
        teacher_user_id=fields["teacher_user_id"],
        day=fields["day"],
        start_time=fields["start_time"],
        end_time=fields["end_time"],
        exclude_id=row.id,
    )
    row.session_year_id = fields["session_year_id"]
    row.class_section_id = fields["class_section_id"]
    row.subject_id = fields["subject_id"]
    row.teacher_user_id = fields["teacher_user_id"]
    row.staff_id = fields["staff_id"]
    row.day = fields["day"]
    row.start_time = fields["start_time"]
    row.end_time = fields["end_time"]
    row.note = fields["note"]
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _entry_item(db, row)


def soft_delete_entry(db: Session, school_id: int, entry_id: int) -> dict:
    row = _owned_entry(db, school_id, entry_id)
    _acquire_timetable_advisory_locks(
        db,
        _schedule_lock_labels(
            school_id,
            session_year_id=row.session_year_id,
            class_section_id=row.class_section_id,
            teacher_user_id=row.teacher_user_id,
            day=row.day,
        ),
    )
    row.deleted_at = _now()
    row.updated_at = _now()
    _commit(db)
    return {"deleted": True}


# Module 1 class weekly view (class-section scoped). Teacher weekly is teacher_weekly_timetable.


def weekly_timetable(
    db: Session,
    school_id: int,
    *,
    session_year_id: int,
    class_section_id: int,
) -> dict:
    _active_session(db, school_id, session_year_id)
    link = _active_class_section(db, school_id, class_section_id)
    rows = (
        db.query(ClassTimetableEntry)
        .filter(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.session_year_id == session_year_id,
            ClassTimetableEntry.class_section_id == class_section_id,
            ClassTimetableEntry.deleted_at.is_(None),
        )
        .all()
    )
    rows.sort(key=lambda row: (DAY_SORT_ORDER.get(row.day, 99), row.start_time, row.id))
    by_day: dict[str, list[dict]] = {name: [] for name in WORKING_DAYS}
    for row in rows:
        if row.day in by_day:
            by_day[row.day].append(_entry_item(db, row))
    klass = db.get(SchoolClass, link.class_id)
    section = db.get(Section, link.section_id)
    return {
        "session_year_id": session_year_id,
        "class_section_id": class_section_id,
        "class_id": link.class_id,
        "section_id": link.section_id,
        "class_name": klass.name if klass is not None else None,
        "section_name": section.name if section is not None else None,
        "days": [{"day": name, "entries": by_day[name]} for name in WORKING_DAYS],
    }
