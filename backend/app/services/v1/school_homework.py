"""School homework & assignment submissions (Module 3).

Late-submission policy — per-homework only (not school-wide)
------------------------------------------------------------
No ``school_settings`` / late-rules ORM exists in this repository (catalog name
``school_settings`` is unmapped). Policy is therefore **per homework**:

- Default ``allow_late=1``: submissions after ``deadline_at`` are accepted with
  ``is_late=1`` and ``status='submitted'``.
- ``allow_late=0``: post-deadline submissions are rejected (422).
- Clients never set ``submitted_at``, ``is_late``, evaluation fields, or status.
- Timestamps use naive UTC via ``_now()`` (project convention).

Attachment storage
------------------
- JSON ``attachments`` on create/update are **metadata only**. Client
  ``storage_key`` / path / url values are rejected.
- Binary uploads (homework brief + student submission) reuse ``document_storage``
  when ``DOCUMENT_STORAGE_BACKEND=local`` and ``DOCUMENT_STORAGE_PATH`` are set;
  otherwise upload endpoints return **503**. Metadata-only text submissions still work.

Evaluator identity
------------------
Evaluation routes use school-admin JWT (``teachers.manage``).
``evaluated_by_user_id`` stores the authenticated **v1 user UUID**
(``str(auth.user.id)``), not legacy ``users.id`` / ``teacher_user_id``.

Concurrency
-----------
First-submit races take a transaction-scoped PostgreSQL advisory lock keyed by
``homework_id`` + ``student_id``, then ``SELECT … FOR UPDATE``. The partial
unique index ``uq_homework_submissions_active`` is the final duplicate guard
(IntegrityError → 409). Soft-deleted rows do not block a new active submission.

Assignment status (student-facing, mutually exclusive)
------------------------------------------------------
- pending: no active submission
- submitted: status=submitted and is_late=0
- late: status=submitted and is_late=1
- graded: status=graded (includes late-then-graded)

Summary counts (teacher)
------------------------
- assigned_students: enrolled admitted|active in homework class-section+session
- pending_count: enrolled without active submission
- submitted_count: status=submitted and is_late=0
- late_count: status=submitted and is_late=1 (ungraded late only)
- graded_count: status=graded
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    Homework,
    HomeworkSubmission,
    SessionYear,
    Student,
    Subject,
    TeacherAssignment,
    User,
)
from app.services.v1.document_storage import (
    ALLOWED_TYPES,
    require_storage,
    sanitize_filename,
    validate_upload,
    discard,
    get_storage,
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

ENROLLED_STATUSES = frozenset({"admitted", "active"})
SUBMISSION_STATUS_SUBMITTED = "submitted"
SUBMISSION_STATUS_GRADED = "graded"
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_DECLARED_BYTES = 25 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = ALLOWED_TYPES | frozenset(
    {
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

_HOMEWORK_WRITE_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "staff_id",
    }
)


def sanitize_homework_body(body: dict) -> dict:
    data = {k: v for k, v in body.items() if k not in _HOMEWORK_WRITE_BLOCKLIST}
    for key in (
        "submitted_at",
        "is_late",
        "status",
        "marks",
        "grade",
        "feedback",
        "evaluated_by_user_id",
        "evaluated_at",
        "student_id",
        "evaluator_id",
    ):
        data.pop(key, None)
    return data


def _is_postgresql(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _advisory_lock_key(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _acquire_submission_advisory_lock(db: Session, homework_id: int, student_id: int) -> None:
    """Serialize create/resubmit for one student+homework (Postgres only)."""
    if not _is_postgresql(db):
        return
    label = f"hw:sub:{homework_id}:{student_id}"
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": _advisory_lock_key(label)},
    )


def _load_attachments_raw(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _parse_date(raw: Any, field: str) -> date:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise AcademicError(422, f"{field} is required")
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    text = str(raw).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be YYYY-MM-DD") from exc


def _parse_datetime(raw: Any, field: str) -> datetime:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise AcademicError(422, f"{field} is required")
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw).strip().replace("Z", "")
    try:
        if "T" in text:
            return datetime.fromisoformat(text)
        if len(text) == 10:
            return datetime.fromisoformat(f"{text}T23:59:59")
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be an ISO datetime") from exc


def _dt(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _validate_attachments_meta(raw: Any) -> list[dict]:
    """Validate client attachment metadata. Rejects storage_key / path injection."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AcademicError(422, "attachments must be a list")
    if len(raw) > MAX_ATTACHMENTS:
        raise AcademicError(422, f"at most {MAX_ATTACHMENTS} attachments allowed")
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            raise AcademicError(422, "each attachment must be an object")
        if "storage_key" in item or "path" in item or "url" in item:
            raise AcademicError(
                422,
                "attachment storage_key/path/url cannot be set by clients; use upload when storage is configured",
            )
        filename = sanitize_filename(item.get("original_filename") or item.get("filename"))
        if not filename:
            raise AcademicError(422, "attachment original_filename is required")
        content_type = str(item.get("content_type") or "").strip().lower()
        if content_type not in ALLOWED_ATTACHMENT_TYPES:
            raise AcademicError(
                422,
                "unsupported attachment content_type; allowed: images, PDF, plain text, Word",
            )
        try:
            size_bytes = int(item.get("size_bytes"))
        except (TypeError, ValueError) as exc:
            raise AcademicError(422, "attachment size_bytes must be an integer") from exc
        if size_bytes < 0 or size_bytes > MAX_ATTACHMENT_DECLARED_BYTES:
            raise AcademicError(422, "attachment size_bytes out of allowed range")
        entry: dict[str, Any] = {
            "original_filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
        }
        # Preserve server-set storage_key only when already present on existing rows
        # merged by callers — never accept from client (blocked above).
        out.append(entry)
    return out


def _dump_attachments(items: list[dict], *, keep_storage_key: bool = False) -> str | None:
    if not items:
        return None
    out: list[dict] = []
    for item in items:
        entry = {
            "original_filename": item.get("original_filename"),
            "content_type": item.get("content_type"),
            "size_bytes": item.get("size_bytes"),
        }
        if keep_storage_key and item.get("storage_key"):
            entry["storage_key"] = item["storage_key"]
        out.append(entry)
    return json.dumps(out, separators=(",", ":"))


def _load_attachments(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    safe: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "original_filename": item.get("original_filename"),
                "content_type": item.get("content_type"),
                "size_bytes": item.get("size_bytes"),
                # Expose presence of stored file without leaking absolute paths.
                "stored": bool(item.get("storage_key")),
            }
        )
    return safe


def _assert_teacher_assignment(
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


def _active_homework(db: Session, school_id: int, homework_id: int) -> Homework:
    return _owned(db, Homework, homework_id, school_id)


def _assignment_status(sub: HomeworkSubmission | None) -> str:
    if sub is None:
        return "pending"
    if sub.status == SUBMISSION_STATUS_GRADED:
        return "graded"
    if int(sub.is_late or 0) == 1:
        return "late"
    return "submitted"


def _homework_item(
    db: Session,
    row: Homework,
    *,
    my_submission: HomeworkSubmission | None = None,
    include_submission: bool = False,
) -> dict:
    teacher = db.get(User, row.teacher_user_id)
    subject = db.get(Subject, row.subject_id)
    data = {
        "id": row.id,
        "session_year_id": row.session_year_id,
        "class_section_id": row.class_section_id,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject else None,
        "teacher_user_id": row.teacher_user_id,
        "teacher_name": _user_name(teacher),
        "title": row.title,
        "instructions": row.instructions,
        "assigned_date": _dt(row.assigned_date),
        "deadline_at": _dt(row.deadline_at),
        "max_marks": row.max_marks,
        "allow_late": bool(row.allow_late),
        "attachments": _load_attachments(row.attachments_json),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }
    if include_submission:
        data["my_submission_status"] = _assignment_status(my_submission)
        data["my_submission"] = (
            _submission_item(db, my_submission, student_safe=True) if my_submission else None
        )
    return data


def _submission_item(
    db: Session,
    row: HomeworkSubmission,
    *,
    student_safe: bool = False,
) -> dict:
    student = db.get(Student, row.student_id)
    student_user = db.get(User, student.user_id) if student else None
    data = {
        "id": row.id,
        "homework_id": row.homework_id,
        "student_id": row.student_id,
        "student_name": _user_name(student_user),
        "admission_no": student.admission_no if student else None,
        "text_response": row.text_response,
        "submitted_at": _dt(row.submitted_at),
        "status": row.status,
        "is_late": bool(row.is_late),
        "assignment_status": _assignment_status(row),
        "attachments": _load_attachments(row.attachments_json),
        "marks": row.marks,
        "grade": row.grade,
        "feedback": row.feedback,
        "evaluated_at": _dt(row.evaluated_at),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }
    if not student_safe:
        # Authenticated v1 school-admin actor UUID (not legacy users.id).
        data["evaluated_by_user_id"] = row.evaluated_by_user_id
        data["evaluated_by_actor"] = "v1_user"
    return data


def _enrolled_students(
    db: Session, school_id: int, class_section_id: int, session_year_id: int
) -> list[Student]:
    return (
        db.query(Student)
        .filter(
            Student.school_id == school_id,
            Student.class_section_id == class_section_id,
            Student.session_year_id == session_year_id,
            Student.deleted_at.is_(None),
            Student.enrollment_status.in_(tuple(ENROLLED_STATUSES)),
        )
        .order_by(Student.id.asc())
        .all()
    )


def create_homework(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_homework_body(body)
    session_year_id = int(data.get("session_year_id") or 0)
    class_section_id = int(data.get("class_section_id") or 0)
    subject_id = int(data.get("subject_id") or 0)
    teacher_user_id = int(data.get("teacher_user_id") or 0)
    if not session_year_id:
        raise AcademicError(422, "session_year_id is required")
    if not class_section_id:
        raise AcademicError(422, "class_section_id is required")
    if not subject_id:
        raise AcademicError(422, "subject_id is required")
    if not teacher_user_id:
        raise AcademicError(422, "teacher_user_id is required")

    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    class_section = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, class_section.class_id, subject_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )

    title = str(data.get("title") or "").strip()
    if not title or len(title) > 255:
        raise AcademicError(422, "title is required and must be at most 255 characters")
    instructions = data.get("instructions")
    if instructions is not None:
        instructions = str(instructions)
        if len(instructions) > 20000:
            raise AcademicError(422, "instructions too long")

    assigned_date = _parse_date(data.get("assigned_date"), "assigned_date")
    deadline_at = _parse_datetime(data.get("deadline_at"), "deadline_at")
    if deadline_at.date() < assigned_date:
        raise AcademicError(422, "deadline_at must be on or after assigned_date")

    max_marks = data.get("max_marks")
    if max_marks is not None:
        try:
            max_marks = float(max_marks)
        except (TypeError, ValueError) as exc:
            raise AcademicError(422, "max_marks must be a number") from exc
        if max_marks < 0:
            raise AcademicError(422, "max_marks must be >= 0")

    allow_late_raw = data.get("allow_late", True)
    allow_late = 1 if allow_late_raw in (True, 1, "1", "true", "True") else 0
    attachments = _validate_attachments_meta(data.get("attachments"))

    row = Homework(
        school_id=school_id,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=teacher_user_id,
        staff_id=staff.id,
        title=title,
        instructions=instructions,
        assigned_date=assigned_date,
        deadline_at=deadline_at,
        max_marks=max_marks,
        allow_late=allow_late,
        attachments_json=_dump_attachments(attachments),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    try:
        from app.services.v1 import notification_delivery as notif

        notif.enqueue_event(
            db,
            school_id,
            event_type="homework_created",
            title=f"New homework: {title[:80]}",
            body=f"Homework assigned (deadline {deadline_at.isoformat()}).",
            audience=["students", "parents"],
            idempotency_key=f"homework_created:{school_id}:{row.id}",
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "homework_notification_enqueue_failed homework_id=%s", row.id
        )
    return _homework_item(db, row)


def list_homework(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    teacher_user_id: int | None = None,
    q: str = "",
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(Homework).filter(
        Homework.school_id == school_id,
        Homework.deleted_at.is_(None),
    )
    if session_year_id is not None:
        query = query.filter(Homework.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(Homework.class_section_id == class_section_id)
    if subject_id is not None:
        query = query.filter(Homework.subject_id == subject_id)
    if teacher_user_id is not None:
        query = query.filter(Homework.teacher_user_id == teacher_user_id)
    if q.strip():
        query = query.filter(Homework.title.ilike(f"%{q.strip()}%"))
    total = query.count()
    rows = (
        query.order_by(Homework.deadline_at.desc(), Homework.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_homework_item(db, r) for r in rows], total, page, page_size)


def get_homework(db: Session, school_id: int, homework_id: int) -> dict:
    return _homework_item(db, _active_homework(db, school_id, homework_id))


def update_homework(db: Session, school_id: int, homework_id: int, body: dict) -> dict:
    row = _active_homework(db, school_id, homework_id)
    data = sanitize_homework_body(body)

    session_year_id = row.session_year_id
    class_section_id = row.class_section_id
    subject_id = row.subject_id
    teacher_user_id = row.teacher_user_id

    if "session_year_id" in data and data["session_year_id"] is not None:
        session_year_id = int(data["session_year_id"])
        _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    if "class_section_id" in data and data["class_section_id"] is not None:
        class_section_id = int(data["class_section_id"])
        _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    if "subject_id" in data and data["subject_id"] is not None:
        subject_id = int(data["subject_id"])
        _same_school(db, Subject, subject_id, school_id, "Subject")
    if "teacher_user_id" in data and data["teacher_user_id"] is not None:
        teacher_user_id = int(data["teacher_user_id"])

    class_section = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _assert_subject_mapped_to_class(db, school_id, class_section.class_id, subject_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )

    if "title" in data:
        title = str(data["title"] or "").strip()
        if not title or len(title) > 255:
            raise AcademicError(422, "title is required and must be at most 255 characters")
        row.title = title
    if "instructions" in data:
        instructions = data["instructions"]
        if instructions is not None:
            instructions = str(instructions)
            if len(instructions) > 20000:
                raise AcademicError(422, "instructions too long")
        row.instructions = instructions
    if "assigned_date" in data:
        row.assigned_date = _parse_date(data["assigned_date"], "assigned_date")
    if "deadline_at" in data:
        row.deadline_at = _parse_datetime(data["deadline_at"], "deadline_at")
    if row.deadline_at.date() < row.assigned_date:
        raise AcademicError(422, "deadline_at must be on or after assigned_date")
    if "max_marks" in data:
        max_marks = data["max_marks"]
        if max_marks is not None:
            try:
                max_marks = float(max_marks)
            except (TypeError, ValueError) as exc:
                raise AcademicError(422, "max_marks must be a number") from exc
            if max_marks < 0:
                raise AcademicError(422, "max_marks must be >= 0")
        row.max_marks = max_marks
    if "allow_late" in data:
        allow_late_raw = data["allow_late"]
        row.allow_late = 1 if allow_late_raw in (True, 1, "1", "true", "True") else 0
    if "attachments" in data:
        row.attachments_json = _dump_attachments(_validate_attachments_meta(data["attachments"]))

    row.session_year_id = session_year_id
    row.class_section_id = class_section_id
    row.subject_id = subject_id
    row.teacher_user_id = teacher_user_id
    row.staff_id = staff.id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _homework_item(db, row)


def soft_delete_homework(db: Session, school_id: int, homework_id: int) -> dict:
    row = _active_homework(db, school_id, homework_id)
    now = _now()
    row.deleted_at = now
    row.updated_at = now
    _commit(db)
    return {"id": homework_id, "deleted": True}


def list_submissions(
    db: Session,
    school_id: int,
    homework_id: int,
    *,
    page: int,
    page_size: int,
    status_filter: str | None = None,
    is_late: bool | None = None,
) -> dict:
    hw = _active_homework(db, school_id, homework_id)
    page, page_size = _page(page, page_size)
    query = db.query(HomeworkSubmission).filter(
        HomeworkSubmission.school_id == school_id,
        HomeworkSubmission.homework_id == hw.id,
        HomeworkSubmission.deleted_at.is_(None),
    )
    if status_filter:
        if status_filter not in (SUBMISSION_STATUS_SUBMITTED, SUBMISSION_STATUS_GRADED):
            raise AcademicError(422, "status must be submitted or graded")
        query = query.filter(HomeworkSubmission.status == status_filter)
    if is_late is not None:
        query = query.filter(HomeworkSubmission.is_late == (1 if is_late else 0))
    total = query.count()
    rows = (
        query.order_by(HomeworkSubmission.submitted_at.desc(), HomeworkSubmission.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_submission_item(db, r) for r in rows], total, page, page_size)


def get_submission(db: Session, school_id: int, submission_id: int) -> dict:
    row = _owned(db, HomeworkSubmission, submission_id, school_id)
    _active_homework(db, school_id, row.homework_id)
    return _submission_item(db, row)


def homework_summary(db: Session, school_id: int, homework_id: int) -> dict:
    hw = _active_homework(db, school_id, homework_id)
    enrolled = _enrolled_students(db, school_id, hw.class_section_id, hw.session_year_id)
    enrolled_ids = {s.id for s in enrolled}
    if enrolled_ids:
        subs = (
            db.query(HomeworkSubmission)
            .filter(
                HomeworkSubmission.school_id == school_id,
                HomeworkSubmission.homework_id == hw.id,
                HomeworkSubmission.deleted_at.is_(None),
                HomeworkSubmission.student_id.in_(enrolled_ids),
            )
            .all()
        )
    else:
        subs = []
    # One submission per student enforced by unique index; still de-dupe defensively.
    by_student: dict[int, HomeworkSubmission] = {}
    for sub in subs:
        by_student[sub.student_id] = sub

    submitted_count = 0
    late_count = 0
    graded_count = 0
    for sub in by_student.values():
        if sub.status == SUBMISSION_STATUS_GRADED:
            graded_count += 1
        elif int(sub.is_late or 0) == 1:
            late_count += 1
        else:
            submitted_count += 1

    assigned = len(enrolled)
    pending_count = assigned - len(by_student)
    return {
        "homework_id": hw.id,
        "assigned_students": assigned,
        "pending_count": pending_count,
        "submitted_count": submitted_count,
        "late_count": late_count,
        "graded_count": graded_count,
        "notes": {
            "denominator": "enrolled students with enrollment_status admitted|active "
            "in the homework class_section_id and session_year_id",
            "late_count": "ungraded submissions with is_late=1 only; graded late work is in graded_count",
            "submitted_count": "ungraded on-time submissions (status=submitted, is_late=0)",
        },
    }


def evaluate_submission(
    db: Session,
    school_id: int,
    submission_id: int,
    body: dict,
    *,
    evaluator_user_id: str | None,
) -> dict:
    row = _owned(db, HomeworkSubmission, submission_id, school_id)
    hw = _active_homework(db, school_id, row.homework_id)

    # Evaluator must be the assigned teacher (or school-admin acting with teachers.manage —
    # route already requires permission; still require teacher assignment coverage).
    staff = _staff_for_teacher_user(db, school_id, hw.teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=hw.subject_id,
        class_section_id=hw.class_section_id,
        session_year_id=hw.session_year_id,
    )

    data = dict(body or {})
    for blocked in (
        "school_id",
        "student_id",
        "homework_id",
        "submitted_at",
        "is_late",
        "status",
        "evaluated_by_user_id",
        "evaluated_at",
        "deleted_at",
        "id",
    ):
        data.pop(blocked, None)

    if "marks" in data:
        marks = data["marks"]
        if marks is None:
            row.marks = None
        else:
            try:
                marks = float(marks)
            except (TypeError, ValueError) as exc:
                raise AcademicError(422, "marks must be a number") from exc
            if marks < 0:
                raise AcademicError(422, "marks must be >= 0")
            if hw.max_marks is not None and marks > float(hw.max_marks):
                raise AcademicError(422, "marks cannot exceed homework max_marks")
            row.marks = marks
    if "grade" in data:
        grade = data["grade"]
        if grade is not None:
            grade = str(grade).strip()[:64] or None
        row.grade = grade
    if "feedback" in data:
        feedback = data["feedback"]
        if feedback is not None:
            feedback = str(feedback)
            if len(feedback) > 20000:
                raise AcademicError(422, "feedback too long")
        row.feedback = feedback

    if not evaluator_user_id or not str(evaluator_user_id).strip():
        raise AcademicError(422, "Evaluator identity is required")

    # Reevaluation allowed: overwriting marks/feedback updates evaluated_at.
    # Identity is the authenticated v1 principal (school-admin JWT), not a
    # client-supplied id and not legacy teacher_user_id.
    row.status = SUBMISSION_STATUS_GRADED
    row.evaluated_by_user_id = str(evaluator_user_id).strip()[:36]
    row.evaluated_at = _now()
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _submission_item(db, row)


# --- Student-facing (identity from authenticated principal) ---


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
    if student.enrollment_status not in ENROLLED_STATUSES:
        raise AcademicError(403, "Student enrollment is not active")
    return student


def list_student_homework(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    subject_id: int | None = None,
    status_filter: str | None = None,
) -> dict:
    student = _student_for_user(db, user, school_id)
    page, page_size = _page(page, page_size)
    query = db.query(Homework).filter(
        Homework.school_id == school_id,
        Homework.class_section_id == student.class_section_id,
        Homework.session_year_id == student.session_year_id,
        Homework.deleted_at.is_(None),
    )
    if subject_id is not None:
        query = query.filter(Homework.subject_id == subject_id)
    rows = query.order_by(Homework.deadline_at.desc(), Homework.id.desc()).all()

    # Load this student's submissions for these homeworks.
    hw_ids = [r.id for r in rows]
    subs = []
    if hw_ids:
        subs = (
            db.query(HomeworkSubmission)
            .filter(
                HomeworkSubmission.school_id == school_id,
                HomeworkSubmission.student_id == student.id,
                HomeworkSubmission.homework_id.in_(hw_ids),
                HomeworkSubmission.deleted_at.is_(None),
            )
            .all()
        )
    by_hw = {s.homework_id: s for s in subs}

    items = []
    for hw in rows:
        sub = by_hw.get(hw.id)
        asg = _assignment_status(sub)
        if status_filter and asg != status_filter:
            continue
        items.append(_homework_item(db, hw, my_submission=sub, include_submission=True))

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return _envelope(page_items, total, page, page_size)


def get_student_homework(db: Session, school_id: int, user: User, homework_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    hw = _active_homework(db, school_id, homework_id)
    if (
        hw.class_section_id != student.class_section_id
        or hw.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    sub = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == school_id,
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .first()
    )
    return _homework_item(db, hw, my_submission=sub, include_submission=True)


def get_my_submission(db: Session, school_id: int, user: User, homework_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    hw = _active_homework(db, school_id, homework_id)
    if (
        hw.class_section_id != student.class_section_id
        or hw.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    sub = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.school_id == school_id,
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .first()
    )
    if sub is None:
        raise AcademicError(404, "Submission not found")
    return _submission_item(db, sub, student_safe=True)


def submit_homework(
    db: Session,
    school_id: int,
    user: User,
    homework_id: int,
    body: dict,
) -> dict:
    student = _student_for_user(db, user, school_id)
    hw = _active_homework(db, school_id, homework_id)
    if (
        hw.class_section_id != student.class_section_id
        or hw.session_year_id != student.session_year_id
        or hw.school_id != school_id
    ):
        raise AcademicError(404, "Record not found")

    data = dict(body or {})
    for blocked in (
        "school_id",
        "student_id",
        "homework_id",
        "submitted_at",
        "is_late",
        "status",
        "marks",
        "grade",
        "feedback",
        "evaluated_by_user_id",
        "evaluated_at",
        "id",
        "deleted_at",
    ):
        data.pop(blocked, None)

    now = _now()
    is_late = 1 if now > hw.deadline_at else 0
    if is_late and int(hw.allow_late or 0) != 1:
        raise AcademicError(422, "Deadline has passed; late submissions are not allowed")

    text_response = data.get("text_response")
    if text_response is not None:
        text_response = str(text_response)
        if len(text_response) > 50000:
            raise AcademicError(422, "text_response too long")
    attachments_provided = "attachments" in data
    attachments = (
        _validate_attachments_meta(data.get("attachments")) if attachments_provided else None
    )
    if (
        not (text_response and str(text_response).strip())
        and not (attachments_provided and attachments)
    ):
        raise AcademicError(422, "Provide text_response and/or attachments")

    _acquire_submission_advisory_lock(db, hw.id, student.id)
    existing = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )

    if existing is not None:
        if existing.status == SUBMISSION_STATUS_GRADED:
            raise AcademicError(422, "Graded submissions cannot be modified by students")
        # Resubmission allowed while not graded.
        if text_response is not None:
            existing.text_response = text_response
        if attachments_provided:
            # Metadata-only replace; does not carry storage_key (use binary upload).
            existing.attachments_json = _dump_attachments(attachments or [])
        existing.submitted_at = now
        existing.is_late = is_late
        existing.status = SUBMISSION_STATUS_SUBMITTED
        existing.updated_at = now
        _commit(db)
        db.refresh(existing)
        return _submission_item(db, existing, student_safe=True)

    row = HomeworkSubmission(
        school_id=school_id,
        homework_id=hw.id,
        student_id=student.id,
        text_response=text_response,
        submitted_at=now,
        status=SUBMISSION_STATUS_SUBMITTED,
        is_late=is_late,
        attachments_json=_dump_attachments(attachments or []),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _submission_item(db, row, student_safe=True)


def student_assignment_status(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    status_filter: str | None = None,
) -> dict:
    """Flat status list for the authenticated student's current class/session."""
    return list_student_homework(
        db,
        school_id,
        user,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )


def append_stored_attachment_to_homework(
    db: Session,
    school_id: int,
    homework_id: int,
    *,
    file_bytes: bytes,
    claimed_filename: str | None,
) -> dict:
    """Optional binary upload when document_storage is configured."""
    require_storage()
    hw = _active_homework(db, school_id, homework_id)
    content_type, ext, filename = validate_upload(
        file_bytes, category="other", claimed_filename=claimed_filename
    )
    current = _load_attachments_raw(hw.attachments_json)
    if len(current) >= MAX_ATTACHMENTS:
        raise AcademicError(422, f"at most {MAX_ATTACHMENTS} attachments allowed")
    storage = get_storage()
    key = storage.build_key(school_id, hw.teacher_user_id, ext)
    storage.put(key, file_bytes)
    try:
        current.append(
            {
                "original_filename": filename,
                "content_type": content_type,
                "size_bytes": len(file_bytes),
                "storage_key": key,
            }
        )
        hw.attachments_json = _dump_attachments(current, keep_storage_key=True)
        hw.updated_at = _now()
        _commit(db)
    except Exception:
        db.rollback()
        discard(storage, key)
        raise
    db.refresh(hw)
    return _homework_item(db, hw)


def append_stored_attachment_to_submission(
    db: Session,
    school_id: int,
    user: User,
    homework_id: int,
    *,
    file_bytes: bytes,
    claimed_filename: str | None,
) -> dict:
    """Student binary attachment upload for their own submission.

    Prerequisite: ``DOCUMENT_STORAGE_BACKEND=local`` and ``DOCUMENT_STORAGE_PATH``.
    Creates an ungraded submission if none exists; refuses graded submissions.
    """
    require_storage()
    student = _student_for_user(db, user, school_id)
    hw = _active_homework(db, school_id, homework_id)
    if (
        hw.class_section_id != student.class_section_id
        or hw.session_year_id != student.session_year_id
        or hw.school_id != school_id
    ):
        raise AcademicError(404, "Record not found")

    now = _now()
    is_late = 1 if now > hw.deadline_at else 0
    if is_late and int(hw.allow_late or 0) != 1:
        raise AcademicError(422, "Deadline has passed; late submissions are not allowed")

    content_type, ext, filename = validate_upload(
        file_bytes, category="other", claimed_filename=claimed_filename
    )
    _acquire_submission_advisory_lock(db, hw.id, student.id)
    existing = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw.id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    current: list = []
    if existing is not None:
        if existing.status == SUBMISSION_STATUS_GRADED:
            raise AcademicError(422, "Graded submissions cannot be modified by students")
        current = _load_attachments_raw(existing.attachments_json)
        if len(current) >= MAX_ATTACHMENTS:
            raise AcademicError(422, f"at most {MAX_ATTACHMENTS} attachments allowed")

    # Write the file only after every check passes; remove it if the row is not saved.
    storage = get_storage()
    key = storage.build_key(school_id, student.user_id, ext)
    storage.put(key, file_bytes)
    entry = {
        "original_filename": filename,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "storage_key": key,
    }
    try:
        if existing is not None:
            current.append(entry)
            existing.attachments_json = _dump_attachments(current, keep_storage_key=True)
            existing.submitted_at = now
            existing.is_late = is_late
            existing.status = SUBMISSION_STATUS_SUBMITTED
            existing.updated_at = now
            _commit(db)
            saved = existing
        else:
            saved = HomeworkSubmission(
                school_id=school_id,
                homework_id=hw.id,
                student_id=student.id,
                text_response=None,
                submitted_at=now,
                status=SUBMISSION_STATUS_SUBMITTED,
                is_late=is_late,
                attachments_json=_dump_attachments([entry], keep_storage_key=True),
                created_at=now,
                updated_at=now,
            )
            db.add(saved)
            _commit(db)
    except Exception:
        db.rollback()
        discard(storage, key)
        raise
    db.refresh(saved)
    return _submission_item(db, saved, student_safe=True)
