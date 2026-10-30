"""Offline exams, subject schedules, marks, audits and results (Module 6).

Reuses legacy ``Exam`` (extended additively). New schedule/marks/result tables use
``offline_exam_*`` names (Laravel ``exam_timetables`` / ``exam_marks`` /
``exam_results`` / ``grades`` remain unmapped).

Grading
-------
No school Grade ORM exists. Pass/fail uses per-schedule ``passing_marks`` and
overall obtained vs sum of included schedule max marks. No letter-grade bands.

Publication
-----------
``Exam.publish`` gates student/parent reads. Corrections require ``publish=0``
(unpublish) when results were published. Processing is idempotent (upsert).

Mark status
-----------
- present: marks_obtained required, 0..max_marks
- absent: marks treated as 0 in totals; max still in denominator
- withheld: excluded from numerator and denominator
- missing mark row: student omitted from processed results (pending)

Rounding: Decimal ROUND_HALF_UP to 2 places for percentages.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    Exam,
    OfflineExamMark,
    OfflineExamMarkAudit,
    OfflineExamResult,
    OfflineExamSchedule,
    SessionYear,
    Student,
    StudentGuardian,
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

ENROLLED = frozenset({"admitted", "active"})
MARK_PRESENT = "present"
MARK_ABSENT = "absent"
MARK_WITHHELD = "withheld"
MARK_STATUSES = frozenset({MARK_PRESENT, MARK_ABSENT, MARK_WITHHELD})

_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "staff_id",
        "evaluated_by_v1_user_id",
        "results_processed_at",
        "actor_v1_user_id",
    }
)


def sanitize_body(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _BLOCKLIST}


def _is_pg(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _lock(db: Session, label: str) -> None:
    if not _is_pg(db):
        return
    key = int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _parse_date(raw: Any, field: str) -> date:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise AcademicError(422, f"{field} is required")
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be YYYY-MM-DD") from exc


def _parse_time(raw: Any, field: str) -> time | None:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None
    if isinstance(raw, time):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text_v = str(raw).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text_v, fmt).time()
        except ValueError:
            continue
    raise AcademicError(422, f"{field} must be HH:MM or HH:MM:SS")


def _dt(v: datetime | date | time | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return v.isoformat()


def _round_pct(obtained: float, total: float) -> float:
    if total <= 0:
        return 0.0
    value = (Decimal(str(obtained)) / Decimal(str(total))) * Decimal("100")
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _assert_teacher(
    db: Session,
    school_id: int,
    *,
    staff_id: int,
    subject_id: int,
    class_section_id: int,
    session_year_id: int,
) -> None:
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


def _active_exam(db: Session, school_id: int, exam_id: int) -> Exam:
    return _owned(db, Exam, exam_id, school_id)


def _marks_exist(db: Session, exam_id: int) -> bool:
    return (
        db.query(OfflineExamMark)
        .filter(
            OfflineExamMark.exam_id == exam_id,
            OfflineExamMark.deleted_at.is_(None),
        )
        .first()
        is not None
    )


def _enrolled(db: Session, school_id: int, class_section_id: int, session_year_id: int) -> list[Student]:
    return (
        db.query(Student)
        .filter(
            Student.school_id == school_id,
            Student.class_section_id == class_section_id,
            Student.session_year_id == session_year_id,
            Student.deleted_at.is_(None),
            Student.enrollment_status.in_(tuple(ENROLLED)),
        )
        .order_by(Student.id.asc())
        .all()
    )


def _exam_item(row: Exam) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "class_id": row.class_id,
        "class_section_id": row.class_section_id,
        "session_year_id": row.session_year_id,
        "exam_type": row.exam_type,
        "exam_date": _dt(row.exam_date),
        "publish": bool(row.publish),
        "results_processed_at": _dt(row.results_processed_at),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _schedule_item(db: Session, row: OfflineExamSchedule) -> dict:
    subject = db.get(Subject, row.subject_id)
    return {
        "id": row.id,
        "exam_id": row.exam_id,
        "session_year_id": row.session_year_id,
        "class_section_id": row.class_section_id,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject else None,
        "teacher_user_id": row.teacher_user_id,
        "exam_date": _dt(row.exam_date),
        "start_time": _dt(row.start_time),
        "end_time": _dt(row.end_time),
        "max_marks": row.max_marks,
        "passing_marks": row.passing_marks,
    }


def _mark_item(db: Session, row: OfflineExamMark) -> dict:
    student = db.get(Student, row.student_id)
    user = db.get(User, student.user_id) if student else None
    return {
        "id": row.id,
        "exam_id": row.exam_id,
        "schedule_id": row.schedule_id,
        "student_id": row.student_id,
        "student_name": _user_name(user),
        "admission_no": student.admission_no if student else None,
        "marks_obtained": row.marks_obtained,
        "status": row.status,
        "evaluated_by_v1_user_id": row.evaluated_by_v1_user_id,
        "updated_at": _dt(row.updated_at),
    }


def _result_item(db: Session, row: OfflineExamResult, *, include_subjects: bool = True) -> dict:
    student = db.get(Student, row.student_id)
    user = db.get(User, student.user_id) if student else None
    data = {
        "id": row.id,
        "exam_id": row.exam_id,
        "student_id": row.student_id,
        "student_name": _user_name(user),
        "admission_no": student.admission_no if student else None,
        "total_max_marks": row.total_max_marks,
        "total_obtained": row.total_obtained,
        "percentage": row.percentage,
        "passed": bool(row.passed),
        "processed_at": _dt(row.processed_at),
    }
    if include_subjects and row.subjects_json:
        try:
            data["subjects"] = json.loads(row.subjects_json)
        except json.JSONDecodeError:
            data["subjects"] = []
    return data


# --- Exam CRUD ---


def create_exam(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    session_year_id = int(data.get("session_year_id") or 0)
    class_section_id = int(data.get("class_section_id") or 0)
    if not session_year_id or not class_section_id:
        raise AcademicError(422, "session_year_id and class_section_id are required")
    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    cs = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 128:
        raise AcademicError(422, "name is required")
    exam_type = data.get("exam_type")
    if exam_type is not None:
        exam_type = str(exam_type).strip()[:64] or None
    exam_date = None
    if "exam_date" in data and data["exam_date"] is not None:
        exam_date = _parse_date(data["exam_date"], "exam_date")
    description = data.get("description")
    if description is not None:
        description = str(description)[:1024]
    row = Exam(
        name=name,
        description=description,
        class_id=cs.class_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
        exam_type=exam_type,
        exam_date=exam_date,
        publish=0,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _exam_item(row)


def list_exams(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    q: str = "",
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(Exam).filter(Exam.school_id == school_id, Exam.deleted_at.is_(None))
    if session_year_id is not None:
        query = query.filter(Exam.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(Exam.class_section_id == class_section_id)
    if q.strip():
        query = query.filter(Exam.name.ilike(f"%{q.strip()}%"))
    total = query.count()
    rows = query.order_by(Exam.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_exam_item(r) for r in rows], total, page, page_size)


def get_exam(db: Session, school_id: int, exam_id: int) -> dict:
    row = _active_exam(db, school_id, exam_id)
    data = _exam_item(row)
    schedules = (
        db.query(OfflineExamSchedule)
        .filter(
            OfflineExamSchedule.school_id == school_id,
            OfflineExamSchedule.exam_id == row.id,
            OfflineExamSchedule.deleted_at.is_(None),
        )
        .order_by(OfflineExamSchedule.exam_date.asc(), OfflineExamSchedule.id.asc())
        .all()
    )
    data["schedules"] = [_schedule_item(db, s) for s in schedules]
    return data


def update_exam(db: Session, school_id: int, exam_id: int, body: dict) -> dict:
    row = _active_exam(db, school_id, exam_id)
    data = sanitize_body(body)
    if _marks_exist(db, row.id) and any(
        k in data for k in ("session_year_id", "class_section_id")
    ):
        raise AcademicError(422, "Cannot change session/class-section after marks exist")
    if "name" in data:
        name = str(data["name"] or "").strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name
    if "description" in data:
        row.description = str(data["description"])[:1024] if data["description"] is not None else None
    if "exam_type" in data:
        row.exam_type = str(data["exam_type"]).strip()[:64] if data["exam_type"] else None
    if "exam_date" in data:
        row.exam_date = (
            _parse_date(data["exam_date"], "exam_date") if data["exam_date"] is not None else None
        )
    if "session_year_id" in data and data["session_year_id"] is not None:
        row.session_year_id = int(data["session_year_id"])
        _same_school(db, SessionYear, row.session_year_id, school_id, "Session year")
    if "class_section_id" in data and data["class_section_id"] is not None:
        cs = _same_school(db, ClassSection, int(data["class_section_id"]), school_id, "Class section")
        row.class_section_id = cs.id
        row.class_id = cs.class_id
    became_published = False
    if "publish" in data:
        new_pub = 1 if data["publish"] in (True, 1, "1", "true") else 0
        became_published = new_pub == 1 and int(row.publish or 0) != 1
        row.publish = new_pub
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    if became_published:
        try:
            from app.services.v1 import notification_delivery as notif

            notif.enqueue_exam_announcement(
                db, school_id, exam_id=row.id, exam_name=row.name or f"Exam {row.id}"
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "exam_publish_notification_failed exam_id=%s", row.id
            )
    return _exam_item(row)


def soft_delete_exam(db: Session, school_id: int, exam_id: int) -> dict:
    row = _active_exam(db, school_id, exam_id)
    if row.publish:
        raise AcademicError(422, "Unpublish the exam before deleting")
    if _marks_exist(db, row.id):
        raise AcademicError(422, "Cannot delete an exam that already has marks; unpublish and archive instead")
    row.deleted_at = _now()
    row.updated_at = _now()
    _commit(db)
    return {"id": exam_id, "deleted": True}


# --- Schedules ---


def _assert_no_schedule_conflict(
    db: Session,
    school_id: int,
    *,
    class_section_id: int,
    exam_date: date,
    start_time: time | None,
    end_time: time | None,
    exclude_id: int | None,
) -> None:
    if start_time is None or end_time is None:
        return
    rows = (
        db.query(OfflineExamSchedule)
        .filter(
            OfflineExamSchedule.school_id == school_id,
            OfflineExamSchedule.class_section_id == class_section_id,
            OfflineExamSchedule.exam_date == exam_date,
            OfflineExamSchedule.deleted_at.is_(None),
            OfflineExamSchedule.start_time.isnot(None),
            OfflineExamSchedule.end_time.isnot(None),
        )
        .all()
    )
    for other in rows:
        if exclude_id and other.id == exclude_id:
            continue
        if start_time < other.end_time and end_time > other.start_time:
            raise AcademicError(409, "Schedule conflicts with another exam for this class-section")


def create_schedule(db: Session, school_id: int, exam_id: int, body: dict) -> dict:
    exam = _active_exam(db, school_id, exam_id)
    if exam.class_section_id is None:
        raise AcademicError(422, "Exam must have class_section_id (Module 6 offline exam)")
    data = sanitize_body(body)
    subject_id = int(data.get("subject_id") or 0)
    if not subject_id:
        raise AcademicError(422, "subject_id is required")
    class_section_id = int(data.get("class_section_id") or exam.class_section_id)
    if class_section_id != exam.class_section_id:
        raise AcademicError(422, "class_section_id must match the exam")
    cs = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, cs.class_id, subject_id)

    teacher_user_id = data.get("teacher_user_id")
    staff_id = None
    if teacher_user_id is not None:
        staff = _staff_for_teacher_user(db, school_id, int(teacher_user_id))
        _assert_teacher(
            db,
            school_id,
            staff_id=staff.id,
            subject_id=subject_id,
            class_section_id=class_section_id,
            session_year_id=exam.session_year_id,
        )
        staff_id = staff.id
        teacher_user_id = int(teacher_user_id)

    exam_date = _parse_date(data.get("exam_date"), "exam_date")
    start_time = _parse_time(data.get("start_time"), "start_time")
    end_time = _parse_time(data.get("end_time"), "end_time")
    if (start_time is None) != (end_time is None):
        raise AcademicError(422, "Provide both start_time and end_time, or neither")
    if start_time and end_time and end_time <= start_time:
        raise AcademicError(422, "end_time must be after start_time")
    try:
        max_marks = float(data.get("max_marks"))
        passing_marks = float(data.get("passing_marks"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "max_marks and passing_marks are required") from exc
    if max_marks <= 0 or passing_marks < 0 or passing_marks > max_marks:
        raise AcademicError(422, "invalid max_marks / passing_marks")

    _assert_no_schedule_conflict(
        db,
        school_id,
        class_section_id=class_section_id,
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        exclude_id=None,
    )

    row = OfflineExamSchedule(
        school_id=school_id,
        exam_id=exam.id,
        session_year_id=exam.session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=teacher_user_id,
        staff_id=staff_id,
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        max_marks=max_marks,
        passing_marks=passing_marks,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _schedule_item(db, row)


def list_schedules(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    exam_id: int | None = None,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    exam_date: date | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(OfflineExamSchedule).filter(
        OfflineExamSchedule.school_id == school_id,
        OfflineExamSchedule.deleted_at.is_(None),
    )
    if exam_id is not None:
        query = query.filter(OfflineExamSchedule.exam_id == exam_id)
    if session_year_id is not None:
        query = query.filter(OfflineExamSchedule.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(OfflineExamSchedule.class_section_id == class_section_id)
    if subject_id is not None:
        query = query.filter(OfflineExamSchedule.subject_id == subject_id)
    if exam_date is not None:
        query = query.filter(OfflineExamSchedule.exam_date == exam_date)
    total = query.count()
    rows = (
        query.order_by(OfflineExamSchedule.exam_date.asc(), OfflineExamSchedule.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_schedule_item(db, r) for r in rows], total, page, page_size)


def get_schedule(db: Session, school_id: int, schedule_id: int) -> dict:
    return _schedule_item(db, _owned(db, OfflineExamSchedule, schedule_id, school_id))


def update_schedule(db: Session, school_id: int, schedule_id: int, body: dict) -> dict:
    """Edit a subject paper/schedule. Blocked when marks already exist for the schedule."""
    row = _owned(db, OfflineExamSchedule, schedule_id, school_id)
    exam = _active_exam(db, school_id, row.exam_id)
    if exam.publish == 1:
        raise AcademicError(409, "Unpublish the exam before editing subject papers")
    if _marks_exist_for_schedule(db, schedule_id):
        raise AcademicError(409, "Cannot edit a schedule that already has marks")

    data = sanitize_body(body)
    subject_id = int(data["subject_id"]) if "subject_id" in data and data["subject_id"] is not None else row.subject_id
    class_section_id = (
        int(data["class_section_id"])
        if "class_section_id" in data and data["class_section_id"] is not None
        else row.class_section_id
    )
    if class_section_id != exam.class_section_id:
        raise AcademicError(422, "class_section_id must match the exam")
    cs = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, cs.class_id, subject_id)

    teacher_user_id = row.teacher_user_id
    staff_id = row.staff_id
    if "teacher_user_id" in data:
        if data["teacher_user_id"] is None:
            teacher_user_id = None
            staff_id = None
        else:
            staff = _staff_for_teacher_user(db, school_id, int(data["teacher_user_id"]))
            _assert_teacher(
                db,
                school_id,
                staff_id=staff.id,
                subject_id=subject_id,
                class_section_id=class_section_id,
                session_year_id=exam.session_year_id,
            )
            staff_id = staff.id
            teacher_user_id = int(data["teacher_user_id"])

    exam_date = _parse_date(data["exam_date"], "exam_date") if "exam_date" in data else row.exam_date
    if "start_time" in data or "end_time" in data:
        start_time = _parse_time(data.get("start_time", row.start_time), "start_time") if "start_time" in data else row.start_time
        end_time = _parse_time(data.get("end_time", row.end_time), "end_time") if "end_time" in data else row.end_time
    else:
        start_time = row.start_time
        end_time = row.end_time
    if (start_time is None) != (end_time is None):
        raise AcademicError(422, "Provide both start_time and end_time, or neither")
    if start_time and end_time and end_time <= start_time:
        raise AcademicError(422, "end_time must be after start_time")

    max_marks = float(data["max_marks"]) if "max_marks" in data else row.max_marks
    passing_marks = float(data["passing_marks"]) if "passing_marks" in data else row.passing_marks
    if max_marks <= 0 or passing_marks < 0 or passing_marks > max_marks:
        raise AcademicError(422, "invalid max_marks / passing_marks")

    # Unique subject paper per exam (when subject changes).
    if subject_id != row.subject_id:
        clash = (
            db.query(OfflineExamSchedule)
            .filter(
                OfflineExamSchedule.exam_id == row.exam_id,
                OfflineExamSchedule.subject_id == subject_id,
                OfflineExamSchedule.class_section_id == class_section_id,
                OfflineExamSchedule.deleted_at.is_(None),
                OfflineExamSchedule.id != row.id,
            )
            .first()
        )
        if clash is not None:
            raise AcademicError(409, "A schedule for this subject already exists on the exam")

    _assert_no_schedule_conflict(
        db,
        school_id,
        class_section_id=class_section_id,
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        exclude_id=row.id,
    )

    row.subject_id = subject_id
    row.class_section_id = class_section_id
    row.teacher_user_id = teacher_user_id
    row.staff_id = staff_id
    row.exam_date = exam_date
    row.start_time = start_time
    row.end_time = end_time
    row.max_marks = max_marks
    row.passing_marks = passing_marks
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _schedule_item(db, row)


def soft_delete_schedule(db: Session, school_id: int, schedule_id: int) -> dict:
    """Remove a subject paper. Blocked when marks exist or exam is published."""
    row = _owned(db, OfflineExamSchedule, schedule_id, school_id)
    exam = _active_exam(db, school_id, row.exam_id)
    if exam.publish == 1:
        raise AcademicError(409, "Unpublish the exam before deleting subject papers")
    if _marks_exist_for_schedule(db, schedule_id):
        raise AcademicError(409, "Cannot delete a schedule that already has marks")
    row.deleted_at = _now()
    row.updated_at = _now()
    _commit(db)
    return {"id": schedule_id, "deleted": True}


def _marks_exist_for_schedule(db: Session, schedule_id: int) -> bool:
    return (
        db.query(OfflineExamMark.id)
        .filter(
            OfflineExamMark.schedule_id == schedule_id,
            OfflineExamMark.deleted_at.is_(None),
        )
        .first()
        is not None
    )


# --- Marks ---


def _validate_mark_values(schedule: OfflineExamSchedule, marks_obtained: Any, status: str) -> float | None:
    if status not in MARK_STATUSES:
        raise AcademicError(422, "status must be present, absent or withheld")
    if status == MARK_PRESENT:
        if marks_obtained is None:
            raise AcademicError(422, "marks_obtained is required when status=present")
        try:
            value = float(marks_obtained)
        except (TypeError, ValueError) as exc:
            raise AcademicError(422, "marks_obtained must be a number") from exc
        if value < 0 or value > float(schedule.max_marks):
            raise AcademicError(422, "marks_obtained must be between 0 and max_marks")
        return value
    return None


def _assert_student_for_schedule(db: Session, school_id: int, schedule: OfflineExamSchedule, student_id: int) -> Student:
    student = _same_school(db, Student, student_id, school_id, "Student")
    if student.deleted_at is not None or student.enrollment_status not in ENROLLED:
        raise AcademicError(422, "Student enrollment is not active")
    if (
        student.class_section_id != schedule.class_section_id
        or student.session_year_id != schedule.session_year_id
    ):
        raise AcademicError(422, "Student is not enrolled in this class-section/session")
    return student


def upsert_mark(
    db: Session,
    school_id: int,
    schedule_id: int,
    body: dict,
    *,
    actor_v1_user_id: str,
    reason: str | None = None,
) -> dict:
    schedule = _owned(db, OfflineExamSchedule, schedule_id, school_id)
    exam = _active_exam(db, school_id, schedule.exam_id)
    if exam.publish:
        raise AcademicError(422, "Unpublish results before entering or correcting marks")
    data = sanitize_body(body)
    student_id = int(data.get("student_id") or 0)
    if not student_id:
        raise AcademicError(422, "student_id is required")
    _assert_student_for_schedule(db, school_id, schedule, student_id)
    status = str(data.get("status") or MARK_PRESENT).strip().lower()
    marks_obtained = _validate_mark_values(schedule, data.get("marks_obtained"), status)

    if schedule.teacher_user_id is not None:
        staff = _staff_for_teacher_user(db, school_id, schedule.teacher_user_id)
        _assert_teacher(
            db,
            school_id,
            staff_id=staff.id,
            subject_id=schedule.subject_id,
            class_section_id=schedule.class_section_id,
            session_year_id=schedule.session_year_id,
        )

    _lock(db, f"oe:mark:{schedule_id}:{student_id}")
    existing = (
        db.query(OfflineExamMark)
        .filter(
            OfflineExamMark.schedule_id == schedule_id,
            OfflineExamMark.student_id == student_id,
            OfflineExamMark.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    now = _now()
    if existing is None:
        row = OfflineExamMark(
            school_id=school_id,
            exam_id=exam.id,
            schedule_id=schedule_id,
            student_id=student_id,
            marks_obtained=marks_obtained,
            status=status,
            evaluated_by_v1_user_id=str(actor_v1_user_id)[:36],
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        _commit(db)
        db.refresh(row)
        return _mark_item(db, row)

    prev_marks, prev_status = existing.marks_obtained, existing.status
    changed = prev_marks != marks_obtained or prev_status != status
    if changed:
        reason_text = str(reason).strip() if reason else ""
        if exam.results_processed_at is not None and not reason_text:
            raise AcademicError(
                422, "reason is required to correct marks after results were processed"
            )
        if reason_text:
            db.add(
                OfflineExamMarkAudit(
                    school_id=school_id,
                    mark_id=existing.id,
                    exam_id=exam.id,
                    student_id=student_id,
                    previous_marks=prev_marks,
                    new_marks=marks_obtained,
                    previous_status=prev_status,
                    new_status=status,
                    reason=reason_text[:512],
                    actor_v1_user_id=str(actor_v1_user_id)[:36],
                    created_at=now,
                )
            )
        if exam.results_processed_at is not None:
            exam.results_processed_at = None
            exam.updated_at = now

    existing.marks_obtained = marks_obtained
    existing.status = status
    existing.evaluated_by_v1_user_id = str(actor_v1_user_id)[:36]
    existing.updated_at = now
    _commit(db)
    db.refresh(existing)
    return _mark_item(db, existing)


def bulk_upsert_marks(
    db: Session,
    school_id: int,
    schedule_id: int,
    items: list,
    *,
    actor_v1_user_id: str,
) -> dict:
    """All-or-nothing bulk entry. Validates every row before committing."""
    if not isinstance(items, list) or not items:
        raise AcademicError(422, "items must be a non-empty list")
    if len(items) > 200:
        raise AcademicError(422, "at most 200 mark rows per request")
    schedule = _owned(db, OfflineExamSchedule, schedule_id, school_id)
    exam = _active_exam(db, school_id, schedule.exam_id)
    if exam.publish:
        raise AcademicError(422, "Unpublish results before entering marks")
    errors: list[str] = []
    prepared: list[dict] = []
    for idx, raw in enumerate(items):
        try:
            if not isinstance(raw, dict):
                raise AcademicError(422, "item must be an object")
            student_id = int(raw.get("student_id") or 0)
            _assert_student_for_schedule(db, school_id, schedule, student_id)
            status = str(raw.get("status") or MARK_PRESENT).strip().lower()
            marks_obtained = _validate_mark_values(schedule, raw.get("marks_obtained"), status)
            prepared.append(
                {"student_id": student_id, "status": status, "marks_obtained": marks_obtained}
            )
        except AcademicError as exc:
            errors.append(f"row {idx}: {exc.detail}")
        except (TypeError, ValueError):
            errors.append(f"row {idx}: invalid student_id or marks")
    if errors:
        preview = "; ".join(errors[:5])
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        raise AcademicError(422, f"Bulk validation failed: {preview}{more}")

    created = updated = 0
    now = _now()
    _lock(db, f"oe:bulk:{schedule_id}")
    for item in prepared:
        existing = (
            db.query(OfflineExamMark)
            .filter(
                OfflineExamMark.schedule_id == schedule_id,
                OfflineExamMark.student_id == item["student_id"],
                OfflineExamMark.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        if existing is None:
            db.add(
                OfflineExamMark(
                    school_id=school_id,
                    exam_id=exam.id,
                    schedule_id=schedule_id,
                    student_id=item["student_id"],
                    marks_obtained=item["marks_obtained"],
                    status=item["status"],
                    evaluated_by_v1_user_id=str(actor_v1_user_id)[:36],
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1
        else:
            existing.marks_obtained = item["marks_obtained"]
            existing.status = item["status"]
            existing.evaluated_by_v1_user_id = str(actor_v1_user_id)[:36]
            existing.updated_at = now
            updated += 1
    if exam.results_processed_at is not None:
        exam.results_processed_at = None
        exam.updated_at = now
    _commit(db)
    return {"created": created, "updated": updated, "total": created + updated}


def list_marks(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    exam_id: int | None = None,
    schedule_id: int | None = None,
    student_id: int | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(OfflineExamMark).filter(
        OfflineExamMark.school_id == school_id,
        OfflineExamMark.deleted_at.is_(None),
    )
    if exam_id is not None:
        query = query.filter(OfflineExamMark.exam_id == exam_id)
    if schedule_id is not None:
        query = query.filter(OfflineExamMark.schedule_id == schedule_id)
    if student_id is not None:
        query = query.filter(OfflineExamMark.student_id == student_id)
    total = query.count()
    rows = (
        query.order_by(OfflineExamMark.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_mark_item(db, r) for r in rows], total, page, page_size)


def list_mark_audits(db: Session, school_id: int, mark_id: int) -> list[dict]:
    _owned(db, OfflineExamMark, mark_id, school_id)
    rows = (
        db.query(OfflineExamMarkAudit)
        .filter(
            OfflineExamMarkAudit.school_id == school_id,
            OfflineExamMarkAudit.mark_id == mark_id,
        )
        .order_by(OfflineExamMarkAudit.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "previous_marks": r.previous_marks,
            "new_marks": r.new_marks,
            "previous_status": r.previous_status,
            "new_status": r.new_status,
            "reason": r.reason,
            "actor_v1_user_id": r.actor_v1_user_id,
            "created_at": _dt(r.created_at),
        }
        for r in rows
    ]


# --- Results processing ---


def process_results(db: Session, school_id: int, exam_id: int) -> dict:
    exam = _active_exam(db, school_id, exam_id)
    if exam.class_section_id is None:
        raise AcademicError(422, "Exam must have class_section_id")
    _lock(db, f"oe:process:{exam_id}")
    schedules = (
        db.query(OfflineExamSchedule)
        .filter(
            OfflineExamSchedule.school_id == school_id,
            OfflineExamSchedule.exam_id == exam_id,
            OfflineExamSchedule.deleted_at.is_(None),
        )
        .all()
    )
    if not schedules:
        raise AcademicError(422, "Exam has no subject schedules")
    enrolled = _enrolled(db, school_id, exam.class_section_id, exam.session_year_id)
    marks = (
        db.query(OfflineExamMark)
        .filter(
            OfflineExamMark.school_id == school_id,
            OfflineExamMark.exam_id == exam_id,
            OfflineExamMark.deleted_at.is_(None),
        )
        .all()
    )
    by_student: dict[int, dict[int, OfflineExamMark]] = {}
    for m in marks:
        by_student.setdefault(m.student_id, {})[m.schedule_id] = m

    now = _now()
    processed = 0
    pending = 0
    schedule_ids = {s.id for s in schedules}
    for student in enrolled:
        student_marks = by_student.get(student.id, {})
        if set(student_marks.keys()) != schedule_ids:
            pending += 1
            continue
        subjects = []
        total_max = 0.0
        total_obt = 0.0
        passed_all = True
        for sched in schedules:
            m = student_marks[sched.id]
            subject = db.get(Subject, sched.subject_id)
            if m.status == MARK_WITHHELD:
                subjects.append(
                    {
                        "schedule_id": sched.id,
                        "subject_id": sched.subject_id,
                        "subject_name": subject.name if subject else None,
                        "status": m.status,
                        "marks_obtained": None,
                        "max_marks": sched.max_marks,
                        "passed": None,
                        "included": False,
                    }
                )
                continue
            obtained = 0.0 if m.status == MARK_ABSENT else float(m.marks_obtained or 0)
            total_max += float(sched.max_marks)
            total_obt += obtained
            subj_pass = obtained >= float(sched.passing_marks)
            if not subj_pass:
                passed_all = False
            subjects.append(
                {
                    "schedule_id": sched.id,
                    "subject_id": sched.subject_id,
                    "subject_name": subject.name if subject else None,
                    "status": m.status,
                    "marks_obtained": obtained,
                    "max_marks": sched.max_marks,
                    "passing_marks": sched.passing_marks,
                    "passed": subj_pass,
                    "included": True,
                }
            )
        percentage = _round_pct(total_obt, total_max)
        overall_pass = 1 if (passed_all and total_max > 0) else 0
        existing = (
            db.query(OfflineExamResult)
            .filter(
                OfflineExamResult.exam_id == exam_id,
                OfflineExamResult.student_id == student.id,
                OfflineExamResult.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        payload = json.dumps(subjects, separators=(",", ":"))
        if existing is None:
            db.add(
                OfflineExamResult(
                    school_id=school_id,
                    exam_id=exam_id,
                    student_id=student.id,
                    total_max_marks=total_max,
                    total_obtained=total_obt,
                    percentage=percentage,
                    passed=overall_pass,
                    subjects_json=payload,
                    processed_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.total_max_marks = total_max
            existing.total_obtained = total_obt
            existing.percentage = percentage
            existing.passed = overall_pass
            existing.subjects_json = payload
            existing.processed_at = now
            existing.updated_at = now
        processed += 1

    exam.results_processed_at = now
    exam.updated_at = now
    _commit(db)
    try:
        from app.services.v1 import notification_delivery as notif

        notif.enqueue_exam_results(
            db, school_id, exam_id=exam_id, exam_name=exam.name or f"Exam {exam_id}"
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "exam_results_notification_failed exam_id=%s", exam_id
        )
    return {
        "exam_id": exam_id,
        "processed_students": processed,
        "pending_students": pending,
        "enrolled_students": len(enrolled),
        "processed_at": _dt(now),
        "notes": {
            "pending": "students missing a mark row for one or more schedules",
            "absent": "counts as 0 obtained; max still in denominator",
            "withheld": "excluded from numerator and denominator",
            "pass_rule": "all included subjects must meet schedule passing_marks",
            "rounding": "percentage ROUND_HALF_UP to 2 decimals",
            "grades": "no Grade ORM; letter grades not assigned",
        },
    }


def list_results(
    db: Session,
    school_id: int,
    exam_id: int,
    *,
    page: int,
    page_size: int,
    require_published: bool = False,
) -> dict:
    exam = _active_exam(db, school_id, exam_id)
    if require_published and not exam.publish:
        raise AcademicError(404, "Record not found")
    page, page_size = _page(page, page_size)
    query = db.query(OfflineExamResult).filter(
        OfflineExamResult.school_id == school_id,
        OfflineExamResult.exam_id == exam_id,
        OfflineExamResult.deleted_at.is_(None),
    )
    total = query.count()
    rows = (
        query.order_by(OfflineExamResult.student_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_result_item(db, r) for r in rows], total, page, page_size)


def class_result_summary(db: Session, school_id: int, exam_id: int) -> dict:
    exam = _active_exam(db, school_id, exam_id)
    if exam.class_section_id is None:
        raise AcademicError(422, "Exam must have class_section_id")
    enrolled = _enrolled(db, school_id, exam.class_section_id, exam.session_year_id)
    results = (
        db.query(OfflineExamResult)
        .filter(
            OfflineExamResult.school_id == school_id,
            OfflineExamResult.exam_id == exam_id,
            OfflineExamResult.deleted_at.is_(None),
        )
        .all()
    )
    by_id = {r.student_id: r for r in results}
    passed = sum(1 for r in results if r.passed)
    return {
        "exam_id": exam_id,
        "publish": bool(exam.publish),
        "enrolled_students": len(enrolled),
        "processed_students": len(results),
        "pending_students": len(enrolled) - len([s for s in enrolled if s.id in by_id]),
        "passed_count": passed,
        "failed_count": len(results) - passed,
        "denominator": "enrolled admitted|active students in exam class_section + session",
    }


def _student_for_user(db: Session, user: User, school_id: int) -> Student:
    student = (
        db.query(Student)
        .filter(
            Student.user_id == user.id,
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .first()
    )
    if student is None:
        raise AcademicError(404, "Student profile not found")
    if student.enrollment_status not in ENROLLED:
        raise AcademicError(403, "Student enrollment is not active")
    return student


def get_student_result(db: Session, school_id: int, user: User, exam_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    exam = _active_exam(db, school_id, exam_id)
    if not exam.publish:
        raise AcademicError(404, "Record not found")
    if (
        exam.class_section_id != student.class_section_id
        or exam.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    row = (
        db.query(OfflineExamResult)
        .filter(
            OfflineExamResult.school_id == school_id,
            OfflineExamResult.exam_id == exam_id,
            OfflineExamResult.student_id == student.id,
            OfflineExamResult.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise AcademicError(404, "Result not found")
    data = _result_item(db, row)
    data["exam"] = _exam_item(exam)
    return data


def list_student_exams(db: Session, school_id: int, user: User, *, page: int, page_size: int) -> dict:
    student = _student_for_user(db, user, school_id)
    page, page_size = _page(page, page_size)
    query = db.query(Exam).filter(
        Exam.school_id == school_id,
        Exam.class_section_id == student.class_section_id,
        Exam.session_year_id == student.session_year_id,
        Exam.deleted_at.is_(None),
        Exam.publish == 1,
    )
    total = query.count()
    rows = query.order_by(Exam.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_exam_item(r) for r in rows], total, page, page_size)


def _guardian_children(db: Session, guardian: User, school_id: int) -> list[Student]:
    # Prefer multi-guardian table; fall back to legacy students.guardian_id.
    via_table = (
        db.query(Student)
        .join(StudentGuardian, StudentGuardian.student_id == Student.id)
        .filter(
            StudentGuardian.guardian_user_id == guardian.id,
            StudentGuardian.deleted_at.is_(None),
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .all()
    )
    if via_table:
        return via_table
    return (
        db.query(Student)
        .filter(
            Student.guardian_id == guardian.id,
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .all()
    )


def get_parent_child_result(
    db: Session, school_id: int, guardian: User, exam_id: int, child_student_id: int
) -> dict:
    children = _guardian_children(db, guardian, school_id)
    child_ids = {c.id for c in children}
    if child_student_id not in child_ids:
        raise AcademicError(404, "Record not found")
    exam = _active_exam(db, school_id, exam_id)
    if not exam.publish:
        raise AcademicError(404, "Record not found")
    row = (
        db.query(OfflineExamResult)
        .filter(
            OfflineExamResult.school_id == school_id,
            OfflineExamResult.exam_id == exam_id,
            OfflineExamResult.student_id == child_student_id,
            OfflineExamResult.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        raise AcademicError(404, "Result not found")
    data = _result_item(db, row)
    data["exam"] = _exam_item(exam)
    return data
