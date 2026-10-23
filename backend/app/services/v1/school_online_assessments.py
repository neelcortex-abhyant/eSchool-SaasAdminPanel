"""Online MCQ assessments (Module 5).

Distinct from legacy offline ``Exam`` and unmapped Laravel ``online_exams*``.

Answer-key security
-------------------
``is_correct`` and snapshot correct_choice_ids are never returned on student
active-attempt payloads. Keys appear only after ``results_published=1`` on
result endpoints (own attempt) or teacher/admin views.

Snapshot / versioning
---------------------
On attempt start, ``answer_key_snapshot`` freezes question id, version, marks,
and correct choice ids. Evaluation uses the snapshot only — later question
edits (version++) do not alter historical results.

Timing
------
``started_at`` / ``ends_at`` / ``submitted_at`` are server-generated.
``ends_at = min(started_at + duration, available_until)``.
Save/submit rejected after ends_at or when status is not in_progress.

Evaluation
----------
MCQ only. Unanswered → 0 marks. Percentage = round(score/total_marks*100, 2)
using Decimal ROUND_HALF_UP. Pass if score >= passing_marks.
Idempotent: evaluating an already-evaluated attempt returns existing scores.

Bulk import
-----------
JSON array import in one transaction (no CSV dependency). All-or-nothing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    OnlineAssessment,
    OnlineAssessmentAnswer,
    OnlineAssessmentAttempt,
    OnlineAssessmentChoice,
    OnlineAssessmentQuestion,
    SessionYear,
    Student,
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

STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_CLOSED = "closed"
ATTEMPT_IN_PROGRESS = "in_progress"
ATTEMPT_SUBMITTED = "submitted"
ATTEMPT_EXPIRED = "expired"
ATTEMPT_EVALUATED = "evaluated"
ENROLLED = frozenset({"admitted", "active"})
MIN_CHOICES = 2
MAX_CHOICES = 8

_ASSESSMENT_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "staff_id",
        "score",
        "percentage",
        "passed",
        "answer_key_snapshot",
    }
)


def sanitize_assessment_body(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _ASSESSMENT_BLOCKLIST}


def _is_postgresql(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _advisory_key(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _lock_attempt(db: Session, assessment_id: int, student_id: int) -> None:
    if not _is_postgresql(db):
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": _advisory_key(f"oa:att:{assessment_id}:{student_id}")},
    )


def _parse_dt(raw: Any, field: str) -> datetime:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise AcademicError(422, f"{field} is required")
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text_v = str(raw).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(text_v)
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be an ISO datetime") from exc


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


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


def _active_assessment(db: Session, school_id: int, assessment_id: int) -> OnlineAssessment:
    return _owned(db, OnlineAssessment, assessment_id, school_id)


def _attempt_count(db: Session, assessment_id: int) -> int:
    return (
        db.query(OnlineAssessmentAttempt)
        .filter(
            OnlineAssessmentAttempt.assessment_id == assessment_id,
            OnlineAssessmentAttempt.deleted_at.is_(None),
        )
        .count()
    )


def _questions(db: Session, school_id: int, assessment_id: int) -> list[OnlineAssessmentQuestion]:
    return (
        db.query(OnlineAssessmentQuestion)
        .filter(
            OnlineAssessmentQuestion.school_id == school_id,
            OnlineAssessmentQuestion.assessment_id == assessment_id,
            OnlineAssessmentQuestion.deleted_at.is_(None),
        )
        .order_by(OnlineAssessmentQuestion.sort_order.asc(), OnlineAssessmentQuestion.id.asc())
        .all()
    )


def _choices(db: Session, school_id: int, question_id: int) -> list[OnlineAssessmentChoice]:
    return (
        db.query(OnlineAssessmentChoice)
        .filter(
            OnlineAssessmentChoice.school_id == school_id,
            OnlineAssessmentChoice.question_id == question_id,
            OnlineAssessmentChoice.deleted_at.is_(None),
        )
        .order_by(OnlineAssessmentChoice.sort_order.asc(), OnlineAssessmentChoice.id.asc())
        .all()
    )


def _assessment_item(db: Session, row: OnlineAssessment, *, include_teacher: bool = True) -> dict:
    subject = db.get(Subject, row.subject_id)
    data = {
        "id": row.id,
        "session_year_id": row.session_year_id,
        "class_section_id": row.class_section_id,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject else None,
        "teacher_user_id": row.teacher_user_id,
        "title": row.title,
        "instructions": row.instructions,
        "duration_minutes": row.duration_minutes,
        "total_marks": row.total_marks,
        "passing_marks": row.passing_marks,
        "available_from": _dt(row.available_from),
        "available_until": _dt(row.available_until),
        "status": row.status,
        "results_published": bool(row.results_published),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }
    if include_teacher:
        data["teacher_name"] = _user_name(db.get(User, row.teacher_user_id))
    return data


def _choice_public(c: OnlineAssessmentChoice, *, reveal_correct: bool) -> dict:
    item = {
        "id": c.id,
        "choice_text": c.choice_text,
        "sort_order": c.sort_order,
    }
    if reveal_correct:
        item["is_correct"] = bool(c.is_correct)
    return item


def _question_public(
    db: Session,
    q: OnlineAssessmentQuestion,
    *,
    reveal_correct: bool,
) -> dict:
    choices = _choices(db, q.school_id, q.id)
    return {
        "id": q.id,
        "question_text": q.question_text,
        "topic": q.topic,
        "question_type": q.question_type,
        "marks": q.marks,
        "sort_order": q.sort_order,
        "version": q.version,
        "choices": [_choice_public(c, reveal_correct=reveal_correct) for c in choices],
    }


def _build_snapshot(db: Session, school_id: int, assessment_id: int) -> str:
    questions = _questions(db, school_id, assessment_id)
    payload = {"questions": []}
    for q in questions:
        if q.question_type != "mcq":
            continue
        correct = [c.id for c in _choices(db, school_id, q.id) if int(c.is_correct) == 1]
        payload["questions"].append(
            {
                "id": q.id,
                "version": q.version,
                "marks": float(q.marks),
                "correct_choice_ids": correct,
            }
        )
    return json.dumps(payload, separators=(",", ":"))


def _round_pct(score: float, total: float) -> float:
    if total <= 0:
        return 0.0
    value = (Decimal(str(score)) / Decimal(str(total))) * Decimal("100")
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def evaluate_attempt(db: Session, attempt: OnlineAssessmentAttempt, assessment: OnlineAssessment) -> None:
    """Server-side MCQ evaluation against answer_key_snapshot. Idempotent."""
    if attempt.status == ATTEMPT_EVALUATED:
        return
    if not attempt.answer_key_snapshot:
        raise AcademicError(422, "Attempt has no answer-key snapshot")
    try:
        snap = json.loads(attempt.answer_key_snapshot)
    except json.JSONDecodeError as exc:
        raise AcademicError(500, "Invalid answer-key snapshot") from exc

    answers = {
        a.question_id: a
        for a in db.query(OnlineAssessmentAnswer)
        .filter(
            OnlineAssessmentAnswer.attempt_id == attempt.id,
            OnlineAssessmentAnswer.school_id == attempt.school_id,
        )
        .all()
    }
    score = 0.0
    for qmeta in snap.get("questions") or []:
        qid = int(qmeta["id"])
        marks = float(qmeta["marks"])
        correct_ids = {int(x) for x in (qmeta.get("correct_choice_ids") or [])}
        ans = answers.get(qid)
        awarded = 0.0
        if ans is not None and ans.choice_id is not None and int(ans.choice_id) in correct_ids:
            awarded = marks
            score += marks
        if ans is not None:
            ans.marks_awarded = awarded
            ans.updated_at = _now()
    attempt.score = score
    attempt.percentage = _round_pct(score, float(assessment.total_marks))
    attempt.passed = 1 if score >= float(assessment.passing_marks) else 0
    attempt.status = ATTEMPT_EVALUATED
    attempt.updated_at = _now()


def create_assessment(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_assessment_body(body)
    session_year_id = int(data.get("session_year_id") or 0)
    class_section_id = int(data.get("class_section_id") or 0)
    subject_id = int(data.get("subject_id") or 0)
    teacher_user_id = int(data.get("teacher_user_id") or 0)
    if not all([session_year_id, class_section_id, subject_id, teacher_user_id]):
        raise AcademicError(422, "session_year_id, class_section_id, subject_id, teacher_user_id required")

    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    cs = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, cs.class_id, subject_id)
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
        raise AcademicError(422, "title is required")
    try:
        duration = int(data.get("duration_minutes"))
        total_marks = float(data.get("total_marks"))
        passing_marks = float(data.get("passing_marks"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "duration_minutes, total_marks and passing_marks are required") from exc
    if duration <= 0:
        raise AcademicError(422, "duration_minutes must be > 0")
    if total_marks <= 0 or passing_marks < 0 or passing_marks > total_marks:
        raise AcademicError(422, "invalid total_marks / passing_marks")

    available_from = _parse_dt(data.get("available_from"), "available_from")
    available_until = _parse_dt(data.get("available_until"), "available_until")
    if available_until <= available_from:
        raise AcademicError(422, "available_until must be after available_from")

    instructions = data.get("instructions")
    if instructions is not None:
        instructions = str(instructions)
        if len(instructions) > 20000:
            raise AcademicError(422, "instructions too long")

    row = OnlineAssessment(
        school_id=school_id,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=teacher_user_id,
        staff_id=staff.id,
        title=title,
        instructions=instructions,
        duration_minutes=duration,
        total_marks=total_marks,
        passing_marks=passing_marks,
        available_from=available_from,
        available_until=available_until,
        status=STATUS_DRAFT,
        results_published=0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _assessment_item(db, row)


def list_assessments(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    teacher_user_id: int | None = None,
    status: str | None = None,
    q: str = "",
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(OnlineAssessment).filter(
        OnlineAssessment.school_id == school_id,
        OnlineAssessment.deleted_at.is_(None),
    )
    if session_year_id is not None:
        query = query.filter(OnlineAssessment.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(OnlineAssessment.class_section_id == class_section_id)
    if teacher_user_id is not None:
        query = query.filter(OnlineAssessment.teacher_user_id == teacher_user_id)
    if subject_id is not None:
        query = query.filter(OnlineAssessment.subject_id == subject_id)
    if status:
        if status not in (STATUS_DRAFT, STATUS_PUBLISHED, STATUS_CLOSED):
            raise AcademicError(422, "invalid status filter")
        query = query.filter(OnlineAssessment.status == status)
    if q.strip():
        query = query.filter(OnlineAssessment.title.ilike(f"%{q.strip()}%"))
    total = query.count()
    rows = (
        query.order_by(OnlineAssessment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_assessment_item(db, r) for r in rows], total, page, page_size)


def get_assessment(db: Session, school_id: int, assessment_id: int) -> dict:
    row = _active_assessment(db, school_id, assessment_id)
    data = _assessment_item(db, row)
    data["questions"] = [
        _question_public(db, q, reveal_correct=True) for q in _questions(db, school_id, row.id)
    ]
    data["attempt_count"] = _attempt_count(db, row.id)
    return data


def update_assessment(db: Session, school_id: int, assessment_id: int, body: dict) -> dict:
    row = _active_assessment(db, school_id, assessment_id)
    data = sanitize_assessment_body(body)
    attempts = _attempt_count(db, row.id)

    session_year_id = row.session_year_id
    class_section_id = row.class_section_id
    subject_id = row.subject_id
    teacher_user_id = row.teacher_user_id

    if attempts and any(
        k in data
        for k in (
            "session_year_id",
            "class_section_id",
            "subject_id",
            "total_marks",
            "passing_marks",
            "duration_minutes",
        )
    ):
        # Allow metadata title/instructions/status/results; block structural mark/window changes lightly
        pass

    if "session_year_id" in data and data["session_year_id"] is not None:
        if attempts:
            raise AcademicError(422, "Cannot change session after attempts exist")
        session_year_id = int(data["session_year_id"])
        _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    if "class_section_id" in data and data["class_section_id"] is not None:
        if attempts:
            raise AcademicError(422, "Cannot change class-section after attempts exist")
        class_section_id = int(data["class_section_id"])
        _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    if "subject_id" in data and data["subject_id"] is not None:
        if attempts:
            raise AcademicError(422, "Cannot change subject after attempts exist")
        subject_id = int(data["subject_id"])
        _same_school(db, Subject, subject_id, school_id, "Subject")
    if "teacher_user_id" in data and data["teacher_user_id"] is not None:
        teacher_user_id = int(data["teacher_user_id"])

    cs = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _assert_subject_mapped_to_class(db, school_id, cs.class_id, subject_id)
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
        if not title:
            raise AcademicError(422, "title is required")
        row.title = title
    if "instructions" in data:
        row.instructions = str(data["instructions"]) if data["instructions"] is not None else None
    if "duration_minutes" in data:
        if attempts:
            raise AcademicError(422, "Cannot change duration after attempts exist")
        duration = int(data["duration_minutes"])
        if duration <= 0:
            raise AcademicError(422, "duration_minutes must be > 0")
        row.duration_minutes = duration
    if "total_marks" in data:
        if attempts:
            raise AcademicError(422, "Cannot change total_marks after attempts exist")
        row.total_marks = float(data["total_marks"])
    if "passing_marks" in data:
        if attempts:
            raise AcademicError(422, "Cannot change passing_marks after attempts exist")
        row.passing_marks = float(data["passing_marks"])
    if row.passing_marks < 0 or row.passing_marks > row.total_marks or row.total_marks <= 0:
        raise AcademicError(422, "invalid total_marks / passing_marks")
    if "available_from" in data:
        row.available_from = _parse_dt(data["available_from"], "available_from")
    if "available_until" in data:
        row.available_until = _parse_dt(data["available_until"], "available_until")
    if row.available_until <= row.available_from:
        raise AcademicError(422, "available_until must be after available_from")
    if "status" in data:
        status = str(data["status"]).strip().lower()
        if status not in (STATUS_DRAFT, STATUS_PUBLISHED, STATUS_CLOSED):
            raise AcademicError(422, "invalid status")
        if status == STATUS_PUBLISHED:
            qs = _questions(db, school_id, row.id)
            if not qs:
                raise AcademicError(422, "Cannot publish an assessment with no questions")
            q_sum = sum(float(q.marks) for q in qs)
            if abs(q_sum - float(row.total_marks)) > 0.001:
                raise AcademicError(
                    422,
                    f"Sum of question marks ({q_sum}) must equal total_marks ({row.total_marks})",
                )
            for q in qs:
                choices = _choices(db, school_id, q.id)
                if len(choices) < MIN_CHOICES:
                    raise AcademicError(422, f"Question {q.id} needs at least {MIN_CHOICES} choices")
                if sum(1 for c in choices if int(c.is_correct) == 1) != 1:
                    raise AcademicError(422, f"Question {q.id} must have exactly one correct choice")
        row.status = status
    if "results_published" in data:
        row.results_published = 1 if data["results_published"] in (True, 1, "1", "true") else 0

    row.session_year_id = session_year_id
    row.class_section_id = class_section_id
    row.subject_id = subject_id
    row.teacher_user_id = teacher_user_id
    row.staff_id = staff.id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _assessment_item(db, row)


def soft_delete_assessment(db: Session, school_id: int, assessment_id: int) -> dict:
    row = _active_assessment(db, school_id, assessment_id)
    # Soft-delete always allowed; historical attempts remain for audit.
    row.deleted_at = _now()
    row.updated_at = _now()
    if row.status == STATUS_PUBLISHED:
        row.status = STATUS_CLOSED
    _commit(db)
    return {"id": assessment_id, "deleted": True}


def _validate_choices_payload(choices: list) -> list[dict]:
    if not isinstance(choices, list) or not (MIN_CHOICES <= len(choices) <= MAX_CHOICES):
        raise AcademicError(422, f"choices must contain {MIN_CHOICES}–{MAX_CHOICES} items")
    out = []
    correct = 0
    for i, raw in enumerate(choices):
        if not isinstance(raw, dict):
            raise AcademicError(422, "each choice must be an object")
        text_v = str(raw.get("choice_text") or "").strip()
        if not text_v:
            raise AcademicError(422, "choice_text is required")
        is_correct = 1 if raw.get("is_correct") in (True, 1, "1", "true") else 0
        correct += is_correct
        out.append({"choice_text": text_v, "is_correct": is_correct, "sort_order": i})
    if correct != 1:
        raise AcademicError(422, "exactly one choice must be marked is_correct")
    return out


def add_question(db: Session, school_id: int, assessment_id: int, body: dict) -> dict:
    assessment = _active_assessment(db, school_id, assessment_id)
    if assessment.status != STATUS_DRAFT and _attempt_count(db, assessment.id) > 0:
        raise AcademicError(422, "Cannot add questions after attempts exist on a non-draft exam")
    question_text = str(body.get("question_text") or "").strip()
    if not question_text:
        raise AcademicError(422, "question_text is required")
    try:
        marks = float(body.get("marks"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "marks is required") from exc
    if marks <= 0:
        raise AcademicError(422, "marks must be > 0")
    choices = _validate_choices_payload(body.get("choices") or [])
    topic = body.get("topic")
    if topic is not None:
        topic = str(topic).strip()[:255] or None
    sort_order = int(body.get("sort_order") or 0)
    q = OnlineAssessmentQuestion(
        school_id=school_id,
        assessment_id=assessment.id,
        question_text=question_text,
        topic=topic,
        question_type="mcq",
        marks=marks,
        sort_order=sort_order,
        version=1,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(q)
    db.flush()
    for c in choices:
        db.add(
            OnlineAssessmentChoice(
                school_id=school_id,
                question_id=q.id,
                choice_text=c["choice_text"],
                is_correct=c["is_correct"],
                sort_order=c["sort_order"],
                created_at=_now(),
                updated_at=_now(),
            )
        )
    _commit(db)
    db.refresh(q)
    return _question_public(db, q, reveal_correct=True)


def update_question(db: Session, school_id: int, question_id: int, body: dict) -> dict:
    q = _owned(db, OnlineAssessmentQuestion, question_id, school_id)
    assessment = _active_assessment(db, school_id, q.assessment_id)
    # Edits bump version; historical attempts keep snapshot.
    if "question_text" in body:
        text_v = str(body["question_text"] or "").strip()
        if not text_v:
            raise AcademicError(422, "question_text is required")
        q.question_text = text_v
    if "marks" in body:
        marks = float(body["marks"])
        if marks <= 0:
            raise AcademicError(422, "marks must be > 0")
        if _attempt_count(db, assessment.id) and assessment.status != STATUS_DRAFT:
            raise AcademicError(422, "Cannot change marks after attempts on published exam")
        q.marks = marks
    if "topic" in body:
        topic = body["topic"]
        q.topic = str(topic).strip()[:255] if topic is not None else None
    if "sort_order" in body:
        q.sort_order = int(body["sort_order"])
    if "choices" in body:
        choices = _validate_choices_payload(body["choices"])
        for old in _choices(db, school_id, q.id):
            old.deleted_at = _now()
            old.updated_at = _now()
        for c in choices:
            db.add(
                OnlineAssessmentChoice(
                    school_id=school_id,
                    question_id=q.id,
                    choice_text=c["choice_text"],
                    is_correct=c["is_correct"],
                    sort_order=c["sort_order"],
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
    q.version = int(q.version or 1) + 1
    q.updated_at = _now()
    _commit(db)
    db.refresh(q)
    return _question_public(db, q, reveal_correct=True)


def soft_delete_question(db: Session, school_id: int, question_id: int) -> dict:
    q = _owned(db, OnlineAssessmentQuestion, question_id, school_id)
    assessment = _active_assessment(db, school_id, q.assessment_id)
    if _attempt_count(db, assessment.id) > 0 and assessment.status != STATUS_DRAFT:
        raise AcademicError(422, "Cannot delete questions after attempts exist")
    now = _now()
    q.deleted_at = now
    q.updated_at = now
    for c in _choices(db, school_id, q.id):
        c.deleted_at = now
        c.updated_at = now
    _commit(db)
    return {"id": question_id, "deleted": True}


def bulk_import_questions(db: Session, school_id: int, assessment_id: int, items: list) -> dict:
    """All-or-nothing JSON import. Returns row-level errors without partial commit."""
    assessment = _active_assessment(db, school_id, assessment_id)
    if not isinstance(items, list) or not items:
        raise AcademicError(422, "items must be a non-empty list")
    if len(items) > 100:
        raise AcademicError(422, "at most 100 questions per import")
    errors: list[dict] = []
    prepared: list[dict] = []
    for idx, raw in enumerate(items):
        try:
            if not isinstance(raw, dict):
                raise AcademicError(422, "item must be an object")
            question_text = str(raw.get("question_text") or "").strip()
            if not question_text:
                raise AcademicError(422, "question_text is required")
            marks = float(raw.get("marks"))
            if marks <= 0:
                raise AcademicError(422, "marks must be > 0")
            choices = _validate_choices_payload(raw.get("choices") or [])
            topic = raw.get("topic")
            prepared.append(
                {
                    "question_text": question_text,
                    "marks": marks,
                    "topic": str(topic).strip()[:255] if topic else None,
                    "sort_order": int(raw.get("sort_order") or idx),
                    "choices": choices,
                }
            )
        except AcademicError as exc:
            errors.append({"row": idx, "detail": exc.detail})
        except (TypeError, ValueError):
            errors.append({"row": idx, "detail": "invalid marks or sort_order"})
    if errors:
        # Actionable row-level errors; no partial insert.
        preview = "; ".join(f"row {e['row']}: {e['detail']}" for e in errors[:5])
        more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
        raise AcademicError(422, f"Import validation failed: {preview}{more}")
    if _attempt_count(db, assessment.id) > 0 and assessment.status != STATUS_DRAFT:
        raise AcademicError(422, "Cannot import questions after attempts exist")
    created_ids = []
    for item in prepared:
        q = OnlineAssessmentQuestion(
            school_id=school_id,
            assessment_id=assessment.id,
            question_text=item["question_text"],
            topic=item["topic"],
            question_type="mcq",
            marks=item["marks"],
            sort_order=item["sort_order"],
            version=1,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(q)
        db.flush()
        for c in item["choices"]:
            db.add(
                OnlineAssessmentChoice(
                    school_id=school_id,
                    question_id=q.id,
                    choice_text=c["choice_text"],
                    is_correct=c["is_correct"],
                    sort_order=c["sort_order"],
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        created_ids.append(q.id)
    _commit(db)
    return {"created": len(created_ids), "question_ids": created_ids}


# --- Student flow ---


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


def list_student_assessments(
    db: Session, school_id: int, user: User, *, page: int, page_size: int
) -> dict:
    student = _student_for_user(db, user, school_id)
    page, page_size = _page(page, page_size)
    now = _now()
    query = db.query(OnlineAssessment).filter(
        OnlineAssessment.school_id == school_id,
        OnlineAssessment.class_section_id == student.class_section_id,
        OnlineAssessment.session_year_id == student.session_year_id,
        OnlineAssessment.deleted_at.is_(None),
        OnlineAssessment.status == STATUS_PUBLISHED,
        OnlineAssessment.available_until >= now,
    )
    total = query.count()
    rows = (
        query.order_by(OnlineAssessment.available_from.asc(), OnlineAssessment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for row in rows:
        item = _assessment_item(db, row, include_teacher=True)
        att = (
            db.query(OnlineAssessmentAttempt)
            .filter(
                OnlineAssessmentAttempt.assessment_id == row.id,
                OnlineAssessmentAttempt.student_id == student.id,
                OnlineAssessmentAttempt.deleted_at.is_(None),
            )
            .first()
        )
        item["my_attempt_status"] = att.status if att else None
        item["my_attempt_id"] = att.id if att else None
        items.append(item)
    return _envelope(items, total, page, page_size)


def start_attempt(db: Session, school_id: int, user: User, assessment_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    assessment = _active_assessment(db, school_id, assessment_id)
    if (
        assessment.class_section_id != student.class_section_id
        or assessment.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    if assessment.status != STATUS_PUBLISHED:
        raise AcademicError(422, "Exam is not available")
    now = _now()
    if now < assessment.available_from or now > assessment.available_until:
        raise AcademicError(422, "Exam is outside its availability window")
    if not _questions(db, school_id, assessment.id):
        raise AcademicError(422, "Exam has no questions")

    _lock_attempt(db, assessment.id, student.id)
    existing = (
        db.query(OnlineAssessmentAttempt)
        .filter(
            OnlineAssessmentAttempt.assessment_id == assessment.id,
            OnlineAssessmentAttempt.student_id == student.id,
            OnlineAssessmentAttempt.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        raise AcademicError(409, "An attempt already exists for this exam")

    duration_end = now + timedelta(minutes=int(assessment.duration_minutes))
    ends_at = min(duration_end, assessment.available_until)
    snapshot = _build_snapshot(db, school_id, assessment.id)
    attempt = OnlineAssessmentAttempt(
        school_id=school_id,
        assessment_id=assessment.id,
        student_id=student.id,
        started_at=now,
        ends_at=ends_at,
        status=ATTEMPT_IN_PROGRESS,
        answer_key_snapshot=snapshot,
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    _commit(db)
    db.refresh(attempt)
    return _attempt_student_view(db, attempt, assessment, reveal_results=False, include_questions=True)


def _expire_if_needed(db: Session, attempt: OnlineAssessmentAttempt) -> None:
    if attempt.status != ATTEMPT_IN_PROGRESS:
        return
    if _now() > attempt.ends_at:
        attempt.status = ATTEMPT_EXPIRED
        attempt.updated_at = _now()
        db.flush()


def _attempt_student_view(
    db: Session,
    attempt: OnlineAssessmentAttempt,
    assessment: OnlineAssessment,
    *,
    reveal_results: bool,
    include_questions: bool,
) -> dict:
    _expire_if_needed(db, attempt)
    data = {
        "id": attempt.id,
        "assessment_id": attempt.assessment_id,
        "status": attempt.status,
        "started_at": _dt(attempt.started_at),
        "ends_at": _dt(attempt.ends_at),
        "submitted_at": _dt(attempt.submitted_at),
        "assessment_title": assessment.title,
        "duration_minutes": assessment.duration_minutes,
        "total_marks": assessment.total_marks,
        "results_published": bool(assessment.results_published),
    }
    if reveal_results and assessment.results_published and attempt.status == ATTEMPT_EVALUATED:
        data["score"] = attempt.score
        data["percentage"] = attempt.percentage
        data["passed"] = bool(attempt.passed)
    if include_questions and attempt.status == ATTEMPT_IN_PROGRESS:
        # Never reveal correct answers during an active attempt.
        data["questions"] = [
            _question_public(db, q, reveal_correct=False)
            for q in _questions(db, assessment.school_id, assessment.id)
        ]
        answers = (
            db.query(OnlineAssessmentAnswer)
            .filter(OnlineAssessmentAnswer.attempt_id == attempt.id)
            .all()
        )
        data["answers"] = [
            {"question_id": a.question_id, "choice_id": a.choice_id} for a in answers
        ]
    elif include_questions and reveal_results and assessment.results_published:
        data["questions"] = [
            _question_public(db, q, reveal_correct=True)
            for q in _questions(db, assessment.school_id, assessment.id)
        ]
        answers = (
            db.query(OnlineAssessmentAnswer)
            .filter(OnlineAssessmentAnswer.attempt_id == attempt.id)
            .all()
        )
        data["answers"] = [
            {
                "question_id": a.question_id,
                "choice_id": a.choice_id,
                "marks_awarded": a.marks_awarded,
            }
            for a in answers
        ]
    return data


def save_answers(db: Session, school_id: int, user: User, attempt_id: int, answers: list) -> dict:
    student = _student_for_user(db, user, school_id)
    attempt = _owned(db, OnlineAssessmentAttempt, attempt_id, school_id)
    if attempt.student_id != student.id:
        raise AcademicError(404, "Record not found")
    assessment = _active_assessment(db, school_id, attempt.assessment_id)
    _expire_if_needed(db, attempt)
    if attempt.status != ATTEMPT_IN_PROGRESS:
        raise AcademicError(422, "Attempt is not open for answers")
    now = _now()
    if now > attempt.ends_at or now > assessment.available_until:
        attempt.status = ATTEMPT_EXPIRED
        attempt.updated_at = now
        _commit(db)
        raise AcademicError(422, "Attempt has expired")
    if not isinstance(answers, list):
        raise AcademicError(422, "answers must be a list")

    valid_qids = {q.id for q in _questions(db, school_id, assessment.id)}
    for raw in answers:
        if not isinstance(raw, dict):
            raise AcademicError(422, "each answer must be an object")
        qid = int(raw.get("question_id") or 0)
        if qid not in valid_qids:
            raise AcademicError(422, f"Invalid question_id {qid}")
        choice_raw = raw.get("choice_id")
        choice_id = None if choice_raw is None else int(choice_raw)
        if choice_id is not None:
            choice = db.get(OnlineAssessmentChoice, choice_id)
            if (
                choice is None
                or choice.deleted_at is not None
                or choice.school_id != school_id
                or choice.question_id != qid
            ):
                raise AcademicError(422, f"Invalid choice_id for question {qid}")
        existing = (
            db.query(OnlineAssessmentAnswer)
            .filter(
                OnlineAssessmentAnswer.attempt_id == attempt.id,
                OnlineAssessmentAnswer.question_id == qid,
            )
            .with_for_update()
            .first()
        )
        if existing is None:
            db.add(
                OnlineAssessmentAnswer(
                    school_id=school_id,
                    attempt_id=attempt.id,
                    question_id=qid,
                    choice_id=choice_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.choice_id = choice_id
            existing.updated_at = now
    attempt.updated_at = now
    _commit(db)
    db.refresh(attempt)
    return _attempt_student_view(db, attempt, assessment, reveal_results=False, include_questions=True)


def submit_attempt(db: Session, school_id: int, user: User, attempt_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    attempt = _owned(db, OnlineAssessmentAttempt, attempt_id, school_id)
    if attempt.student_id != student.id:
        raise AcademicError(404, "Record not found")
    assessment = _active_assessment(db, school_id, attempt.assessment_id)
    _lock_attempt(db, assessment.id, student.id)
    attempt = (
        db.query(OnlineAssessmentAttempt)
        .filter(OnlineAssessmentAttempt.id == attempt.id)
        .with_for_update()
        .one()
    )
    if attempt.status == ATTEMPT_EVALUATED:
        return _attempt_student_view(
            db,
            attempt,
            assessment,
            reveal_results=True,
            include_questions=bool(assessment.results_published),
        )
    if attempt.status in (ATTEMPT_SUBMITTED,):
        evaluate_attempt(db, attempt, assessment)
        _commit(db)
        db.refresh(attempt)
        return _attempt_student_view(
            db, attempt, assessment, reveal_results=True, include_questions=False
        )
    _expire_if_needed(db, attempt)
    if attempt.status == ATTEMPT_EXPIRED:
        # Auto-evaluate expired attempts with whatever answers were saved.
        attempt.submitted_at = attempt.ends_at
        evaluate_attempt(db, attempt, assessment)
        _commit(db)
        db.refresh(attempt)
        return _attempt_student_view(
            db, attempt, assessment, reveal_results=True, include_questions=False
        )
    if attempt.status != ATTEMPT_IN_PROGRESS:
        raise AcademicError(422, "Attempt cannot be submitted")
    now = _now()
    if now > attempt.ends_at:
        attempt.status = ATTEMPT_EXPIRED
        attempt.submitted_at = attempt.ends_at
    else:
        attempt.submitted_at = now
        attempt.status = ATTEMPT_SUBMITTED
    evaluate_attempt(db, attempt, assessment)
    _commit(db)
    db.refresh(attempt)
    return _attempt_student_view(
        db, attempt, assessment, reveal_results=True, include_questions=False
    )


def get_my_attempt(db: Session, school_id: int, user: User, attempt_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    attempt = _owned(db, OnlineAssessmentAttempt, attempt_id, school_id)
    if attempt.student_id != student.id:
        raise AcademicError(404, "Record not found")
    assessment = _active_assessment(db, school_id, attempt.assessment_id)
    include_q = attempt.status == ATTEMPT_IN_PROGRESS or (
        bool(assessment.results_published) and attempt.status == ATTEMPT_EVALUATED
    )
    return _attempt_student_view(
        db,
        attempt,
        assessment,
        reveal_results=True,
        include_questions=include_q,
    )


def list_assessment_attempts(
    db: Session, school_id: int, assessment_id: int, *, page: int, page_size: int
) -> dict:
    assessment = _active_assessment(db, school_id, assessment_id)
    page, page_size = _page(page, page_size)
    query = db.query(OnlineAssessmentAttempt).filter(
        OnlineAssessmentAttempt.school_id == school_id,
        OnlineAssessmentAttempt.assessment_id == assessment.id,
        OnlineAssessmentAttempt.deleted_at.is_(None),
    )
    total = query.count()
    rows = (
        query.order_by(OnlineAssessmentAttempt.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for att in rows:
        student = db.get(Student, att.student_id)
        user = db.get(User, student.user_id) if student else None
        items.append(
            {
                "id": att.id,
                "student_id": att.student_id,
                "student_name": _user_name(user),
                "admission_no": student.admission_no if student else None,
                "status": att.status,
                "started_at": _dt(att.started_at),
                "submitted_at": _dt(att.submitted_at),
                "score": att.score,
                "percentage": att.percentage,
                "passed": bool(att.passed) if att.passed is not None else None,
            }
        )
    return _envelope(items, total, page, page_size)


def get_attempt_admin(db: Session, school_id: int, attempt_id: int) -> dict:
    attempt = _owned(db, OnlineAssessmentAttempt, attempt_id, school_id)
    assessment = _active_assessment(db, school_id, attempt.assessment_id)
    return _attempt_student_view(
        db, attempt, assessment, reveal_results=True, include_questions=True
    )
