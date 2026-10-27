"""School-admin academic management wave (grading, fees, transport, reports, etc.)."""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import (
    AcademicSemester,
    AcademicShift,
    AcademicStream,
    Addon,
    AdmissionInquiry,
    Announcement,
    CertificateIssue,
    CertificateTemplate,
    ClassSection,
    DiaryCategory,
    Exam,
    Expense,
    ExpenseCategory,
    FeeAssignment,
    FeeConcession,
    FeePayment,
    FeeStructure,
    FeeStructureAmount,
    FeeType,
    GradingScale,
    GradingScaleBand,
    Holiday,
    IdCardSetting,
    IncomeCategory,
    IncomeRecord,
    Notification,
    OfflineExamResult,
    OnlineAssessment,
    OnlineAssessmentAttempt,
    OnlineAssessmentChoice,
    OnlineAssessmentQuestion,
    OnlineClass,
    Package,
    PayrollItem,
    PayrollRun,
    PayrollSetting,
    QuestionBankChoice,
    QuestionBankQuestion,
    ReportCard,
    SchoolGalleryItem,
    SchoolSlider,
    SessionYear,
    Staff,
    StaffAttendanceRecord,
    StaffQrAttendanceSetting,
    StaffTask,
    Student,
    StudentDiaryEntry,
    StudentElective,
    StudentPromotion,
    StudentTransfer,
    StudentTransportAssignment,
    Subject,
    Syllabus,
    TransportRoute,
    TransportStop,
    TransportVehicle,
    User,
)
from app.services.v1.school_academics import (
    AcademicError,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
    _same_school,
)

_WRITE_BLOCKLIST = frozenset(
    {"school_id", "id", "deleted_at", "created_at", "updated_at"}
)


def sanitize_body(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _WRITE_BLOCKLIST}


def _row_dict(row, extra: dict | None = None) -> dict:
    data: dict[str, Any] = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, datetime):
            data[col.name] = val.isoformat()
        elif isinstance(val, date):
            data[col.name] = val.isoformat()
        elif isinstance(val, time):
            data[col.name] = val.strftime("%H:%M:%S")
        elif isinstance(val, Decimal):
            data[col.name] = float(val)
        else:
            data[col.name] = val
    if extra:
        data.update(extra)
    return data


def _parse_date(value, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, f"{field} must be YYYY-MM-DD") from exc


def _parse_time(value, field: str) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise AcademicError(422, f"{field} must be HH:MM or HH:MM:SS")


def _parse_datetime(value, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be an ISO datetime") from exc


def _soft_delete(db: Session, row) -> dict:
    row.deleted_at = _now()
    if hasattr(row, "updated_at"):
        row.updated_at = _now()
    _commit(db)
    return {"id": row.id, "deleted": True}


def _list_active(
    db: Session,
    model,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    filters: Callable | None = None,
    order_by=None,
    serialize: Callable | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(model).filter(model.school_id == school_id)
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    if filters:
        query = filters(query)
    total = query.count()
    order = order_by if order_by is not None else model.id.desc()
    rows = query.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    ser = serialize or _row_dict
    return _envelope([ser(r) for r in rows], total, page, page_size)


# ---------------------------------------------------------------------------
# Grading scales + bands
# ---------------------------------------------------------------------------


def letter_for_percentage(bands: list[dict], pct: float) -> str | None:
    """Pure band lookup. Inclusive min/max; first matching band wins (highest sort)."""
    rounded = round(float(pct), 2)
    for band in bands:
        lo = float(band["min_percent"])
        hi = float(band["max_percent"])
        if lo <= rounded <= hi:
            return str(band["letter"])
    return None


def _bands_for_scale(db: Session, school_id: int, scale_id: int) -> list[GradingScaleBand]:
    return (
        db.query(GradingScaleBand)
        .filter(
            GradingScaleBand.school_id == school_id,
            GradingScaleBand.grading_scale_id == scale_id,
            GradingScaleBand.deleted_at.is_(None),
        )
        .order_by(GradingScaleBand.sort_order.asc(), GradingScaleBand.min_percent.desc())
        .all()
    )


def _scale_item(db: Session, row: GradingScale) -> dict:
    bands = _bands_for_scale(db, row.school_id, row.id)
    return _row_dict(
        row,
        {
            "bands": [
                {
                    "id": b.id,
                    "letter": b.letter,
                    "min_percent": b.min_percent,
                    "max_percent": b.max_percent,
                    "grade_point": b.grade_point,
                    "remark": b.remark,
                    "is_pass": b.is_pass,
                    "sort_order": b.sort_order,
                }
                for b in bands
            ]
        },
    )


def _replace_bands(db: Session, school_id: int, scale_id: int, bands: list) -> None:
    if not isinstance(bands, list) or not bands:
        raise AcademicError(422, "bands must be a non-empty list")
    now = _now()
    for old in _bands_for_scale(db, school_id, scale_id):
        old.deleted_at = now
        old.updated_at = now
    for i, raw in enumerate(bands):
        if not isinstance(raw, dict):
            raise AcademicError(422, "each band must be an object")
        letter = str(raw.get("letter") or raw.get("grade") or "").strip()
        if not letter:
            raise AcademicError(422, "band letter is required")
        try:
            lo = float(raw["min_percent"])
            hi = float(raw["max_percent"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AcademicError(422, "band min_percent and max_percent are required") from exc
        if not (0 <= lo <= hi <= 100):
            raise AcademicError(422, "band percent range must satisfy 0 <= min <= max <= 100")
        db.add(
            GradingScaleBand(
                school_id=school_id,
                grading_scale_id=scale_id,
                letter=letter,
                min_percent=lo,
                max_percent=hi,
                grade_point=float(raw["grade_point"]) if raw.get("grade_point") is not None else None,
                remark=(str(raw["remark"]).strip()[:255] if raw.get("remark") else None),
                is_pass=1 if raw.get("is_pass", True) in (True, 1, "1", "true") else 0,
                sort_order=int(raw.get("sort_order", i)),
                created_at=now,
                updated_at=now,
            )
        )


def list_grading_scales(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(
        db,
        GradingScale,
        school_id,
        page=page,
        page_size=page_size,
        serialize=lambda r: _scale_item(db, r),
    )


def get_grading_scale(db: Session, school_id: int, scale_id: int) -> dict:
    return _scale_item(db, _owned(db, GradingScale, scale_id, school_id))


def create_grading_scale(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    is_default = 1 if body.get("is_default") in (True, 1, "1", "true") else 0
    if is_default:
        db.query(GradingScale).filter(
            GradingScale.school_id == school_id, GradingScale.deleted_at.is_(None)
        ).update({GradingScale.is_default: 0}, synchronize_session=False)
    row = GradingScale(
        school_id=school_id,
        name=name,
        description=body.get("description"),
        is_default=is_default,
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    bands = body.get("bands") or body.get("ranges") or []
    _replace_bands(db, school_id, row.id, bands)
    _commit(db)
    db.refresh(row)
    return _scale_item(db, row)


def update_grading_scale(db: Session, school_id: int, scale_id: int, body: dict) -> dict:
    row = _owned(db, GradingScale, scale_id, school_id)
    if "name" in body:
        name = str(body["name"] or "").strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name
    if "description" in body:
        row.description = body["description"]
    if "status" in body:
        row.status = int(body["status"])
    if "is_default" in body:
        is_default = 1 if body["is_default"] in (True, 1, "1", "true") else 0
        if is_default:
            db.query(GradingScale).filter(
                GradingScale.school_id == school_id, GradingScale.deleted_at.is_(None)
            ).update({GradingScale.is_default: 0}, synchronize_session=False)
        row.is_default = is_default
    if "bands" in body or "ranges" in body:
        _replace_bands(db, school_id, row.id, body.get("bands") or body.get("ranges") or [])
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _scale_item(db, row)


def soft_delete_grading_scale(db: Session, school_id: int, scale_id: int) -> dict:
    row = _owned(db, GradingScale, scale_id, school_id)
    if row.is_default:
        raise AcademicError(409, "Choose another default scale before deleting this one")
    now = _now()
    for b in _bands_for_scale(db, school_id, scale_id):
        b.deleted_at = now
        b.updated_at = now
    return _soft_delete(db, row)


def letter_for_scale(db: Session, school_id: int, scale_id: int, pct: float) -> str | None:
    bands = [
        {"letter": b.letter, "min_percent": b.min_percent, "max_percent": b.max_percent}
        for b in _bands_for_scale(db, school_id, scale_id)
    ]
    return letter_for_percentage(bands, pct)


# ---------------------------------------------------------------------------
# Report cards
# ---------------------------------------------------------------------------


def _default_scale_id(db: Session, school_id: int) -> int | None:
    row = (
        db.query(GradingScale)
        .filter(
            GradingScale.school_id == school_id,
            GradingScale.deleted_at.is_(None),
            GradingScale.is_default == 1,
        )
        .first()
    )
    return row.id if row else None


def generate_report_cards(
    db: Session,
    school_id: int,
    exam_id: int,
    grading_scale_id: int | None = None,
) -> dict:
    exam = _owned(db, Exam, exam_id, school_id)
    scale_id = grading_scale_id or _default_scale_id(db, school_id)
    if scale_id is not None:
        _owned(db, GradingScale, scale_id, school_id)
    results = (
        db.query(OfflineExamResult)
        .filter(
            OfflineExamResult.school_id == school_id,
            OfflineExamResult.exam_id == exam.id,
            OfflineExamResult.deleted_at.is_(None),
        )
        .all()
    )
    if not results:
        raise AcademicError(422, "No processed offline exam results for this exam")
    now = _now()
    created = 0
    items = []
    for res in results:
        letter = letter_for_scale(db, school_id, scale_id, res.percentage) if scale_id else None
        existing = (
            db.query(ReportCard)
            .filter(
                ReportCard.school_id == school_id,
                ReportCard.exam_id == exam.id,
                ReportCard.student_id == res.student_id,
                ReportCard.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            existing.grading_scale_id = scale_id
            existing.percentage = res.percentage
            existing.letter_grade = letter
            existing.passed = res.passed
            existing.subjects_json = res.subjects_json
            existing.generated_at = now
            existing.updated_at = now
            row = existing
        else:
            row = ReportCard(
                school_id=school_id,
                exam_id=exam.id,
                student_id=res.student_id,
                grading_scale_id=scale_id,
                percentage=res.percentage,
                letter_grade=letter,
                passed=res.passed,
                subjects_json=res.subjects_json,
                generated_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            created += 1
        db.flush()
        items.append(_row_dict(row))
    _commit(db)
    return {"exam_id": exam.id, "created": created, "items": items, "total": len(items)}


def list_report_cards(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    exam_id: int | None = None,
    student_id: int | None = None,
) -> dict:
    def filt(q):
        if exam_id is not None:
            q = q.filter(ReportCard.exam_id == exam_id)
        if student_id is not None:
            q = q.filter(ReportCard.student_id == student_id)
        return q

    return _list_active(db, ReportCard, school_id, page=page, page_size=page_size, filters=filt)


def get_report_card(db: Session, school_id: int, report_id: int) -> dict:
    return _row_dict(_owned(db, ReportCard, report_id, school_id))


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------


def _qb_choices(db: Session, school_id: int, question_id: int) -> list[QuestionBankChoice]:
    return (
        db.query(QuestionBankChoice)
        .filter(
            QuestionBankChoice.school_id == school_id,
            QuestionBankChoice.question_id == question_id,
            QuestionBankChoice.deleted_at.is_(None),
        )
        .order_by(QuestionBankChoice.sort_order.asc(), QuestionBankChoice.id.asc())
        .all()
    )


def _qb_item(db: Session, row: QuestionBankQuestion) -> dict:
    choices = _qb_choices(db, row.school_id, row.id)
    return _row_dict(
        row,
        {
            "choices": [
                {
                    "id": c.id,
                    "choice_text": c.choice_text,
                    "is_correct": c.is_correct,
                    "sort_order": c.sort_order,
                }
                for c in choices
            ]
        },
    )


def _validate_qb_choices(choices: list) -> list[dict]:
    if not isinstance(choices, list) or not (2 <= len(choices) <= 8):
        raise AcademicError(422, "choices must contain 2–8 items")
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


def list_question_bank(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    subject_id: int | None = None,
    q: str = "",
) -> dict:
    def filt(query):
        if subject_id is not None:
            query = query.filter(QuestionBankQuestion.subject_id == subject_id)
        if q.strip():
            like = f"%{q.strip()}%"
            query = query.filter(QuestionBankQuestion.question_text.ilike(like))
        return query

    return _list_active(
        db,
        QuestionBankQuestion,
        school_id,
        page=page,
        page_size=page_size,
        filters=filt,
        serialize=lambda r: _qb_item(db, r),
    )


def get_question_bank(db: Session, school_id: int, question_id: int) -> dict:
    return _qb_item(db, _owned(db, QuestionBankQuestion, question_id, school_id))


def create_question_bank(db: Session, school_id: int, body: dict) -> dict:
    text_v = str(body.get("question_text") or "").strip()
    if not text_v:
        raise AcademicError(422, "question_text is required")
    try:
        marks = float(body.get("marks"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "marks is required") from exc
    if marks <= 0:
        raise AcademicError(422, "marks must be > 0")
    subject_id = body.get("subject_id")
    if subject_id is not None:
        _same_school(db, Subject, int(subject_id), school_id, "Subject")
    choices = _validate_qb_choices(body.get("choices") or [])
    row = QuestionBankQuestion(
        school_id=school_id,
        subject_id=int(subject_id) if subject_id is not None else None,
        question_text=text_v,
        topic=(str(body["topic"]).strip()[:255] if body.get("topic") else None),
        question_type="mcq",
        marks=marks,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    for c in choices:
        db.add(
            QuestionBankChoice(
                school_id=school_id,
                question_id=row.id,
                choice_text=c["choice_text"],
                is_correct=c["is_correct"],
                sort_order=c["sort_order"],
                created_at=_now(),
                updated_at=_now(),
            )
        )
    _commit(db)
    db.refresh(row)
    return _qb_item(db, row)


def update_question_bank(db: Session, school_id: int, question_id: int, body: dict) -> dict:
    row = _owned(db, QuestionBankQuestion, question_id, school_id)
    if "question_text" in body:
        text_v = str(body["question_text"] or "").strip()
        if not text_v:
            raise AcademicError(422, "question_text is required")
        row.question_text = text_v
    if "marks" in body:
        marks = float(body["marks"])
        if marks <= 0:
            raise AcademicError(422, "marks must be > 0")
        row.marks = marks
    if "topic" in body:
        row.topic = str(body["topic"]).strip()[:255] if body["topic"] is not None else None
    if "subject_id" in body:
        sid = body["subject_id"]
        if sid is not None:
            _same_school(db, Subject, int(sid), school_id, "Subject")
            row.subject_id = int(sid)
        else:
            row.subject_id = None
    if "choices" in body:
        choices = _validate_qb_choices(body["choices"])
        now = _now()
        for old in _qb_choices(db, school_id, row.id):
            old.deleted_at = now
            old.updated_at = now
        for c in choices:
            db.add(
                QuestionBankChoice(
                    school_id=school_id,
                    question_id=row.id,
                    choice_text=c["choice_text"],
                    is_correct=c["is_correct"],
                    sort_order=c["sort_order"],
                    created_at=now,
                    updated_at=now,
                )
            )
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _qb_item(db, row)


def soft_delete_question_bank(db: Session, school_id: int, question_id: int) -> dict:
    row = _owned(db, QuestionBankQuestion, question_id, school_id)
    now = _now()
    for c in _qb_choices(db, school_id, row.id):
        c.deleted_at = now
        c.updated_at = now
    return _soft_delete(db, row)


def copy_questions_to_assessment(
    db: Session, school_id: int, assessment_id: int, question_ids: list[int]
) -> dict:
    assessment = _owned(db, OnlineAssessment, assessment_id, school_id)
    if not question_ids:
        raise AcademicError(422, "question_ids is required")
    attempts = (
        db.query(func.count(OnlineAssessmentAttempt.id))
        .filter(
            OnlineAssessmentAttempt.school_id == school_id,
            OnlineAssessmentAttempt.assessment_id == assessment.id,
            OnlineAssessmentAttempt.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    if assessment.status != "draft" and int(attempts) > 0:
        raise AcademicError(422, "Cannot add questions after attempts exist on a non-draft exam")

    max_sort = (
        db.query(func.max(OnlineAssessmentQuestion.sort_order))
        .filter(
            OnlineAssessmentQuestion.school_id == school_id,
            OnlineAssessmentQuestion.assessment_id == assessment.id,
            OnlineAssessmentQuestion.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )
    copied = []
    for qid in question_ids:
        src = _owned(db, QuestionBankQuestion, int(qid), school_id)
        max_sort += 1
        q = OnlineAssessmentQuestion(
            school_id=school_id,
            assessment_id=assessment.id,
            question_text=src.question_text,
            topic=src.topic,
            question_type="mcq",
            marks=src.marks,
            sort_order=max_sort,
            version=1,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(q)
        db.flush()
        for c in _qb_choices(db, school_id, src.id):
            db.add(
                OnlineAssessmentChoice(
                    school_id=school_id,
                    question_id=q.id,
                    choice_text=c.choice_text,
                    is_correct=c.is_correct,
                    sort_order=c.sort_order,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        copied.append(q.id)
    _commit(db)
    return {"assessment_id": assessment.id, "copied_question_ids": copied, "count": len(copied)}


# ---------------------------------------------------------------------------
# Admission inquiries + holidays
# ---------------------------------------------------------------------------


def list_admission_inquiries(db: Session, school_id: int, page: int = 1, page_size: int = 20, status: str | None = None) -> dict:
    def filt(q):
        if status:
            q = q.filter(AdmissionInquiry.status == status)
        return q

    return _list_active(db, AdmissionInquiry, school_id, page=page, page_size=page_size, filters=filt)


def create_admission_inquiry(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("student_name") or "").strip()
    if not name:
        raise AcademicError(422, "student_name is required")
    row = AdmissionInquiry(
        school_id=school_id,
        student_name=name,
        parent_name=(str(body["parent_name"]).strip() if body.get("parent_name") else None),
        email=(str(body["email"]).strip().lower() if body.get("email") else None),
        mobile=(str(body["mobile"]).strip() if body.get("mobile") else None),
        class_interested=(str(body["class_interested"]).strip() if body.get("class_interested") else None),
        message=body.get("message"),
        status=str(body.get("status") or "open"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_admission_inquiry(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, AdmissionInquiry, row_id, school_id)
    for key in ("student_name", "parent_name", "email", "mobile", "class_interested", "message", "status"):
        if key in body:
            val = body[key]
            if key == "student_name":
                val = str(val or "").strip()
                if not val:
                    raise AcademicError(422, "student_name is required")
            setattr(row, key, val)
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_admission_inquiry(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, AdmissionInquiry, row_id, school_id))


def list_holidays(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(
        db, Holiday, school_id, page=page, page_size=page_size, order_by=Holiday.holiday_date.asc()
    )


def create_holiday(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    if not body.get("holiday_date") and not body.get("date"):
        raise AcademicError(422, "holiday_date is required")
    row = Holiday(
        school_id=school_id,
        title=title,
        holiday_date=_parse_date(body.get("holiday_date") or body.get("date"), "holiday_date"),
        end_date=_parse_date(body["end_date"], "end_date") if body.get("end_date") else None,
        description=body.get("description"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_holiday(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, Holiday, row_id, school_id)
    if "title" in body:
        title = str(body["title"] or "").strip()
        if not title:
            raise AcademicError(422, "title is required")
        row.title = title
    if "holiday_date" in body or "date" in body:
        row.holiday_date = _parse_date(body.get("holiday_date") or body.get("date"), "holiday_date")
    if "end_date" in body:
        row.end_date = _parse_date(body["end_date"], "end_date") if body["end_date"] else None
    if "description" in body:
        row.description = body["description"]
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_holiday(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, Holiday, row_id, school_id))


# ---------------------------------------------------------------------------
# Students: electives, transfer, promote, reset password, bulk import
# ---------------------------------------------------------------------------


def list_student_electives(db: Session, school_id: int, student_id: int) -> dict:
    _owned(db, Student, student_id, school_id)
    rows = (
        db.query(StudentElective)
        .filter(
            StudentElective.school_id == school_id,
            StudentElective.student_id == student_id,
            StudentElective.deleted_at.is_(None),
        )
        .order_by(StudentElective.id.desc())
        .all()
    )
    return {"items": [_row_dict(r) for r in rows], "total": len(rows)}


def assign_student_elective(db: Session, school_id: int, student_id: int, body: dict) -> dict:
    _owned(db, Student, student_id, school_id)
    subject_id = int(body.get("subject_id") or 0)
    session_year_id = int(body.get("session_year_id") or 0)
    if not subject_id or not session_year_id:
        raise AcademicError(422, "subject_id and session_year_id are required")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    row = StudentElective(
        school_id=school_id,
        student_id=student_id,
        subject_id=subject_id,
        session_year_id=session_year_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def remove_student_elective(db: Session, school_id: int, student_id: int, elective_id: int) -> dict:
    _owned(db, Student, student_id, school_id)
    row = _owned(db, StudentElective, elective_id, school_id)
    if row.student_id != student_id:
        raise AcademicError(404, "Record not found")
    return _soft_delete(db, row)


def transfer_student(db: Session, school_id: int, student_id: int, body: dict) -> dict:
    student = _owned(db, Student, student_id, school_id)
    transfer_date = _parse_date(body.get("transfer_date") or date.today().isoformat(), "transfer_date")
    hist = StudentTransfer(
        school_id=school_id,
        student_id=student.id,
        from_class_section_id=student.class_section_id,
        to_school_name=(str(body["to_school_name"]).strip() if body.get("to_school_name") else None),
        reason=body.get("reason"),
        transfer_date=transfer_date,
        created_at=_now(),
        updated_at=_now(),
    )
    student.enrollment_status = "transferred"
    student.updated_at = _now()
    db.add(hist)
    _commit(db)
    db.refresh(hist)
    return _row_dict(hist, {"enrollment_status": student.enrollment_status})


def promote_students(db: Session, school_id: int, body: dict) -> dict:
    student_ids = body.get("student_ids") or []
    to_cs = int(body.get("to_class_section_id") or 0)
    if not student_ids or not to_cs:
        raise AcademicError(422, "student_ids and to_class_section_id are required")
    _same_school(db, ClassSection, to_cs, school_id, "Class section")
    to_session = body.get("to_session_year_id")
    if to_session is not None:
        _same_school(db, SessionYear, int(to_session), school_id, "Session year")
    now = _now()
    promoted = []
    for sid in student_ids:
        student = _owned(db, Student, int(sid), school_id)
        hist = StudentPromotion(
            school_id=school_id,
            student_id=student.id,
            from_class_section_id=student.class_section_id,
            to_class_section_id=to_cs,
            from_session_year_id=student.session_year_id,
            to_session_year_id=int(to_session) if to_session is not None else student.session_year_id,
            promoted_at=now,
            created_at=now,
            updated_at=now,
        )
        student.class_section_id = to_cs
        if to_session is not None:
            student.session_year_id = int(to_session)
        student.updated_at = now
        db.add(hist)
        promoted.append(student.id)
    _commit(db)
    return {"promoted": promoted, "count": len(promoted)}


def reset_student_password(db: Session, school_id: int, student_id: int, body: dict) -> dict:
    student = _owned(db, Student, student_id, school_id)
    password = str(body.get("password") or "").strip()
    if len(password) < 8:
        raise AcademicError(422, "password must be at least 8 characters")
    user = db.get(User, student.user_id)
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(404, "Student user not found")
    user.password = hash_password(password)
    user.updated_at = _now()
    _commit(db)
    return {"student_id": student.id, "user_id": user.id, "reset": True}


def bulk_import_students(db: Session, school_id: int, rows: list[dict]) -> dict:
    if not isinstance(rows, list) or not rows:
        raise AcademicError(422, "rows must be a non-empty list")
    if len(rows) > 500:
        raise AcademicError(422, "at most 500 students per import")
    errors: list[dict] = []
    prepared: list[dict] = []
    for idx, raw in enumerate(rows):
        try:
            if not isinstance(raw, dict):
                raise AcademicError(422, "row must be an object")
            for req in ("first_name", "last_name", "email", "admission_no", "class_section_id", "session_year_id", "guardian_id", "admission_date"):
                if raw.get(req) in (None, ""):
                    raise AcademicError(422, f"{req} is required")
            _same_school(db, ClassSection, int(raw["class_section_id"]), school_id, "Class section")
            _same_school(db, SessionYear, int(raw["session_year_id"]), school_id, "Session year")
            _same_school(db, User, int(raw["guardian_id"]), school_id, "Guardian")
            prepared.append(
                {
                    "first_name": str(raw["first_name"]).strip(),
                    "last_name": str(raw["last_name"]).strip(),
                    "email": str(raw["email"]).strip().lower(),
                    "admission_no": str(raw["admission_no"]).strip(),
                    "roll_number": raw.get("roll_number"),
                    "admission_date": _parse_date(raw["admission_date"], "admission_date"),
                    "class_section_id": int(raw["class_section_id"]),
                    "session_year_id": int(raw["session_year_id"]),
                    "guardian_id": int(raw["guardian_id"]),
                    "password": str(raw["password"]).strip() if raw.get("password") else secrets.token_urlsafe(18),
                }
            )
        except AcademicError as exc:
            errors.append({"row": idx, "detail": exc.detail})
    if errors:
        raise AcademicError(422, json.dumps({"errors": errors}))
    created = 0
    try:
        for item in prepared:
            user = User(
                first_name=item["first_name"],
                last_name=item["last_name"],
                email=item["email"],
                password=hash_password(item["password"]),
                status=1,
                school_id=school_id,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(user)
            db.flush()
            db.add(
                Student(
                    user_id=user.id,
                    class_section_id=item["class_section_id"],
                    admission_no=item["admission_no"],
                    roll_number=item["roll_number"],
                    admission_date=item["admission_date"],
                    school_id=school_id,
                    guardian_id=item["guardian_id"],
                    session_year_id=item["session_year_id"],
                    enrollment_status="admitted",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            created += 1
        _commit(db)
    except AcademicError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise AcademicError(409, "A record with these details already exists")
    return {"created": created}


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------


def list_fee_types(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, FeeType, school_id, page=page, page_size=page_size)


def create_fee_type(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = FeeType(
        school_id=school_id,
        name=name,
        category=str(body.get("category") or "other"),
        description=body.get("description"),
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_fee_type(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, FeeType, row_id, school_id)
    if "name" in body:
        name = str(body["name"] or "").strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name
    if "category" in body:
        row.category = str(body["category"])
    if "description" in body:
        row.description = body["description"]
    if "status" in body:
        row.status = int(body["status"])
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_fee_type(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, FeeType, row_id, school_id))


def _structure_amounts(db: Session, school_id: int, structure_id: int) -> list[FeeStructureAmount]:
    return (
        db.query(FeeStructureAmount)
        .filter(
            FeeStructureAmount.school_id == school_id,
            FeeStructureAmount.structure_id == structure_id,
            FeeStructureAmount.deleted_at.is_(None),
        )
        .all()
    )


def _structure_item(db: Session, row: FeeStructure) -> dict:
    amounts = _structure_amounts(db, row.school_id, row.id)
    total = sum(float(a.amount) for a in amounts)
    return _row_dict(
        row,
        {
            "amounts": [_row_dict(a) for a in amounts],
            "total": total,
        },
    )


def list_fee_structures(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(
        db, FeeStructure, school_id, page=page, page_size=page_size, serialize=lambda r: _structure_item(db, r)
    )


def get_fee_structure(db: Session, school_id: int, row_id: int) -> dict:
    return _structure_item(db, _owned(db, FeeStructure, row_id, school_id))


def create_fee_structure(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    session_year_id = int(body.get("session_year_id") or 0)
    if not name or not session_year_id:
        raise AcademicError(422, "name and session_year_id are required")
    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    class_id = body.get("class_id")
    if class_id is not None:
        from app.models.tables import SchoolClass

        _same_school(db, SchoolClass, int(class_id), school_id, "Class")
    amounts = body.get("amounts") or body.get("items") or []
    if not isinstance(amounts, list) or not amounts:
        raise AcademicError(422, "amounts must be a non-empty list")
    row = FeeStructure(
        school_id=school_id,
        name=name,
        session_year_id=session_year_id,
        class_id=int(class_id) if class_id is not None else None,
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    for raw in amounts:
        fee_type_id = int(raw.get("fee_type_id") or 0)
        amount = float(raw.get("amount") or 0)
        if not fee_type_id or amount <= 0:
            raise AcademicError(422, "each amount needs fee_type_id and amount > 0")
        _owned(db, FeeType, fee_type_id, school_id)
        db.add(
            FeeStructureAmount(
                school_id=school_id,
                structure_id=row.id,
                fee_type_id=fee_type_id,
                amount=amount,
                created_at=_now(),
                updated_at=_now(),
            )
        )
    _commit(db)
    db.refresh(row)
    return _structure_item(db, row)


def update_fee_structure(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, FeeStructure, row_id, school_id)
    if "name" in body:
        name = str(body["name"] or "").strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name
    if "status" in body:
        row.status = int(body["status"])
    if "amounts" in body or "items" in body:
        amounts = body.get("amounts") or body.get("items") or []
        if not isinstance(amounts, list) or not amounts:
            raise AcademicError(422, "amounts must be a non-empty list")
        now = _now()
        for old in _structure_amounts(db, school_id, row.id):
            old.deleted_at = now
            old.updated_at = now
        for raw in amounts:
            fee_type_id = int(raw.get("fee_type_id") or 0)
            amount = float(raw.get("amount") or 0)
            if not fee_type_id or amount <= 0:
                raise AcademicError(422, "each amount needs fee_type_id and amount > 0")
            _owned(db, FeeType, fee_type_id, school_id)
            db.add(
                FeeStructureAmount(
                    school_id=school_id,
                    structure_id=row.id,
                    fee_type_id=fee_type_id,
                    amount=amount,
                    created_at=now,
                    updated_at=now,
                )
            )
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _structure_item(db, row)


def soft_delete_fee_structure(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, FeeStructure, row_id, school_id)
    now = _now()
    for a in _structure_amounts(db, school_id, row.id):
        a.deleted_at = now
        a.updated_at = now
    return _soft_delete(db, row)


def list_fee_assignments(db: Session, school_id: int, page: int = 1, page_size: int = 20, student_id: int | None = None, structure_id: int | None = None) -> dict:
    def filt(q):
        if student_id is not None:
            q = q.filter(FeeAssignment.student_id == student_id)
        if structure_id is not None:
            q = q.filter(FeeAssignment.structure_id == structure_id)
        return q

    return _list_active(db, FeeAssignment, school_id, page=page, page_size=page_size, filters=filt)


def create_fee_assignment(db: Session, school_id: int, body: dict) -> dict:
    structure_id = int(body.get("structure_id") or 0)
    student_id = int(body.get("student_id") or 0)
    if not structure_id or not student_id:
        raise AcademicError(422, "structure_id and student_id are required")
    _owned(db, FeeStructure, structure_id, school_id)
    _owned(db, Student, student_id, school_id)
    row = FeeAssignment(
        school_id=school_id,
        structure_id=structure_id,
        student_id=student_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_fee_assignment(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, FeeAssignment, row_id, school_id))


def list_fee_concessions(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, FeeConcession, school_id, page=page, page_size=page_size)


def create_fee_concession(db: Session, school_id: int, body: dict) -> dict:
    student_id = int(body.get("student_id") or 0)
    structure_id = int(body.get("structure_id") or 0)
    kind = str(body.get("kind") or "").strip()
    reason = str(body.get("reason") or "").strip()
    try:
        value = float(body.get("value"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "value is required") from exc
    if not student_id or not structure_id or kind not in ("percent", "amount") or not reason or value <= 0:
        raise AcademicError(422, "student_id, structure_id, kind (percent|amount), value > 0, reason required")
    if kind == "percent" and value > 100:
        raise AcademicError(422, "percent concession cannot exceed 100")
    _owned(db, Student, student_id, school_id)
    _owned(db, FeeStructure, structure_id, school_id)
    row = FeeConcession(
        school_id=school_id,
        student_id=student_id,
        structure_id=structure_id,
        kind=kind,
        value=value,
        reason=reason,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_fee_concession(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, FeeConcession, row_id, school_id))


def list_fee_payments(db: Session, school_id: int, page: int = 1, page_size: int = 20, student_id: int | None = None) -> dict:
    def filt(q):
        if student_id is not None:
            q = q.filter(FeePayment.student_id == student_id)
        return q

    return _list_active(db, FeePayment, school_id, page=page, page_size=page_size, filters=filt)


def _structure_total(db: Session, school_id: int, structure_id: int) -> float:
    return sum(float(a.amount) for a in _structure_amounts(db, school_id, structure_id))


def _paid_for_assignment(db: Session, school_id: int, assignment_id: int) -> float:
    total = (
        db.query(func.coalesce(func.sum(FeePayment.amount), 0))
        .filter(
            FeePayment.school_id == school_id,
            FeePayment.assignment_id == assignment_id,
            FeePayment.deleted_at.is_(None),
            FeePayment.status == "success",
        )
        .scalar()
    )
    return float(total or 0)


def _concession_amount(db: Session, school_id: int, student_id: int, structure_id: int, total: float) -> float:
    conc = (
        db.query(FeeConcession)
        .filter(
            FeeConcession.school_id == school_id,
            FeeConcession.student_id == student_id,
            FeeConcession.structure_id == structure_id,
            FeeConcession.deleted_at.is_(None),
        )
        .first()
    )
    if conc is None:
        return 0.0
    if conc.kind == "percent":
        return round(total * float(conc.value) / 100.0, 2)
    return min(float(conc.value), total)


def collect_fee(db: Session, school_id: int, body: dict) -> dict:
    assignment_id = int(body.get("assignment_id") or 0)
    if not assignment_id:
        raise AcademicError(422, "assignment_id is required")
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "amount is required") from exc
    if amount <= 0:
        raise AcademicError(422, "amount must be > 0")
    assignment = _owned(db, FeeAssignment, assignment_id, school_id)
    idem = body.get("idempotency_key")
    if idem:
        existing = (
            db.query(FeePayment)
            .filter(
                FeePayment.school_id == school_id,
                FeePayment.idempotency_key == str(idem),
                FeePayment.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            return _row_dict(existing)
    total = _structure_total(db, school_id, assignment.structure_id)
    concession = _concession_amount(db, school_id, assignment.student_id, assignment.structure_id, total)
    payable = max(total - concession, 0)
    already = _paid_for_assignment(db, school_id, assignment.id)
    balance = round(payable - already, 2)
    if amount > balance + 0.001:
        raise AcademicError(422, "amount exceeds outstanding balance")
    receipt = body.get("receipt_no") or f"RCPT-{_now().strftime('%Y%m%d%H%M%S')}-{assignment.id}"
    row = FeePayment(
        school_id=school_id,
        assignment_id=assignment.id,
        student_id=assignment.student_id,
        amount=amount,
        method=str(body.get("method") or "cash"),
        receipt_no=str(receipt),
        reference=body.get("reference"),
        remarks=body.get("remarks"),
        paid_on=_parse_date(body.get("paid_on") or date.today().isoformat(), "paid_on"),
        status="success",
        idempotency_key=str(idem) if idem else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def fees_outstanding(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    assignments = (
        db.query(FeeAssignment)
        .filter(FeeAssignment.school_id == school_id, FeeAssignment.deleted_at.is_(None))
        .order_by(FeeAssignment.id.desc())
        .all()
    )
    items = []
    summary = {"payable": 0.0, "collected": 0.0, "outstanding": 0.0}
    for a in assignments:
        total = _structure_total(db, school_id, a.structure_id)
        concession = _concession_amount(db, school_id, a.student_id, a.structure_id, total)
        payable = max(total - concession, 0)
        paid = _paid_for_assignment(db, school_id, a.id)
        balance = round(payable - paid, 2)
        if balance <= 0:
            continue
        items.append(
            {
                "assignment_id": a.id,
                "student_id": a.student_id,
                "structure_id": a.structure_id,
                "payable": payable,
                "concession": concession,
                "paid": paid,
                "balance": balance,
            }
        )
        summary["payable"] += payable
        summary["collected"] += paid
        summary["outstanding"] += balance
    total_n = len(items)
    slice_items = items[(page - 1) * page_size : page * page_size]
    return {**_envelope(slice_items, total_n, page, page_size), "summary": summary}


# ---------------------------------------------------------------------------
# Semesters / streams / shifts / syllabus / online classes
# ---------------------------------------------------------------------------


def list_semesters(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, AcademicSemester, school_id, page=page, page_size=page_size)


def create_semester(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    session_year_id = int(body.get("session_year_id") or 0)
    if not name or not session_year_id:
        raise AcademicError(422, "name and session_year_id are required")
    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    row = AcademicSemester(
        school_id=school_id,
        name=name,
        session_year_id=session_year_id,
        start_date=_parse_date(body["start_date"], "start_date") if body.get("start_date") else None,
        end_date=_parse_date(body["end_date"], "end_date") if body.get("end_date") else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_semester(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, AcademicSemester, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "start_date" in body:
        row.start_date = _parse_date(body["start_date"], "start_date") if body["start_date"] else None
    if "end_date" in body:
        row.end_date = _parse_date(body["end_date"], "end_date") if body["end_date"] else None
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_semester(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, AcademicSemester, row_id, school_id))


def list_streams(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, AcademicStream, school_id, page=page, page_size=page_size)


def create_stream(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = AcademicStream(
        school_id=school_id,
        name=name,
        description=body.get("description"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_stream(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, AcademicStream, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "description" in body:
        row.description = body["description"]
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_stream(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, AcademicStream, row_id, school_id))


def list_shifts(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, AcademicShift, school_id, page=page, page_size=page_size)


def create_shift(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = AcademicShift(
        school_id=school_id,
        name=name,
        start_time=_parse_time(body.get("start_time"), "start_time"),
        end_time=_parse_time(body.get("end_time"), "end_time"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_shift(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, AcademicShift, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "start_time" in body:
        row.start_time = _parse_time(body.get("start_time"), "start_time")
    if "end_time" in body:
        row.end_time = _parse_time(body.get("end_time"), "end_time")
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_shift(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, AcademicShift, row_id, school_id))


def list_syllabi(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, Syllabus, school_id, page=page, page_size=page_size)


def create_syllabus(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    row = Syllabus(
        school_id=school_id,
        title=title,
        class_id=int(body["class_id"]) if body.get("class_id") else None,
        subject_id=int(body["subject_id"]) if body.get("subject_id") else None,
        session_year_id=int(body["session_year_id"]) if body.get("session_year_id") else None,
        content=body.get("content"),
        created_at=_now(),
        updated_at=_now(),
    )
    if row.class_id:
        from app.models.tables import SchoolClass

        _same_school(db, SchoolClass, row.class_id, school_id, "Class")
    if row.subject_id:
        _same_school(db, Subject, row.subject_id, school_id, "Subject")
    if row.session_year_id:
        _same_school(db, SessionYear, row.session_year_id, school_id, "Session year")
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_syllabus(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, Syllabus, row_id, school_id)
    if "title" in body:
        row.title = str(body["title"] or "").strip()
    if "content" in body:
        row.content = body["content"]
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_syllabus(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, Syllabus, row_id, school_id))


def list_online_classes(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, OnlineClass, school_id, page=page, page_size=page_size)


def create_online_class(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    row = OnlineClass(
        school_id=school_id,
        title=title,
        class_section_id=int(body["class_section_id"]) if body.get("class_section_id") else None,
        subject_id=int(body["subject_id"]) if body.get("subject_id") else None,
        teacher_user_id=int(body["teacher_user_id"]) if body.get("teacher_user_id") else None,
        meeting_url=body.get("meeting_url"),
        scheduled_at=_parse_datetime(body.get("scheduled_at"), "scheduled_at"),
        duration_minutes=int(body["duration_minutes"]) if body.get("duration_minutes") is not None else None,
        created_at=_now(),
        updated_at=_now(),
    )
    if row.class_section_id:
        _same_school(db, ClassSection, row.class_section_id, school_id, "Class section")
    if row.subject_id:
        _same_school(db, Subject, row.subject_id, school_id, "Subject")
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_online_class(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, OnlineClass, row_id, school_id)
    if "title" in body:
        row.title = str(body["title"] or "").strip()
    if "meeting_url" in body:
        row.meeting_url = body["meeting_url"]
    if "scheduled_at" in body:
        row.scheduled_at = _parse_datetime(body.get("scheduled_at"), "scheduled_at")
    if "duration_minutes" in body:
        row.duration_minutes = int(body["duration_minutes"]) if body["duration_minutes"] is not None else None
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_online_class(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, OnlineClass, row_id, school_id))


# ---------------------------------------------------------------------------
# Staff attendance / QR / tasks
# ---------------------------------------------------------------------------


def mark_staff_attendance(db: Session, school_id: int, body: dict) -> dict:
    staff_id = int(body.get("staff_id") or 0)
    if not staff_id:
        raise AcademicError(422, "staff_id is required")
    _same_school(db, Staff, staff_id, school_id, "Staff")
    att_date = _parse_date(body.get("attendance_date") or body.get("date") or date.today().isoformat(), "attendance_date")
    status_v = str(body.get("status") or "present")
    existing = (
        db.query(StaffAttendanceRecord)
        .filter(
            StaffAttendanceRecord.school_id == school_id,
            StaffAttendanceRecord.staff_id == staff_id,
            StaffAttendanceRecord.attendance_date == att_date,
            StaffAttendanceRecord.deleted_at.is_(None),
        )
        .first()
    )
    if existing:
        existing.status = status_v
        existing.check_in = _parse_time(body.get("check_in"), "check_in") if "check_in" in body else existing.check_in
        existing.check_out = _parse_time(body.get("check_out"), "check_out") if "check_out" in body else existing.check_out
        existing.remark = body.get("remark", existing.remark)
        existing.updated_at = _now()
        row = existing
    else:
        row = StaffAttendanceRecord(
            school_id=school_id,
            staff_id=staff_id,
            attendance_date=att_date,
            status=status_v,
            check_in=_parse_time(body.get("check_in"), "check_in"),
            check_out=_parse_time(body.get("check_out"), "check_out"),
            remark=body.get("remark"),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def staff_attendance_today(db: Session, school_id: int) -> dict:
    today = date.today()
    rows = (
        db.query(StaffAttendanceRecord)
        .filter(
            StaffAttendanceRecord.school_id == school_id,
            StaffAttendanceRecord.attendance_date == today,
            StaffAttendanceRecord.deleted_at.is_(None),
        )
        .all()
    )
    return {"date": today.isoformat(), "items": [_row_dict(r) for r in rows], "total": len(rows)}


def staff_attendance_register(db: Session, school_id: int, attendance_date: date | None = None) -> dict:
    day = attendance_date or date.today()
    staff = db.query(Staff).filter(Staff.school_id == school_id).all()
    marked = {
        r.staff_id: r
        for r in db.query(StaffAttendanceRecord)
        .filter(
            StaffAttendanceRecord.school_id == school_id,
            StaffAttendanceRecord.attendance_date == day,
            StaffAttendanceRecord.deleted_at.is_(None),
        )
        .all()
    }
    items = []
    for s in staff:
        att = marked.get(s.id)
        items.append(
            {
                "staff_id": s.id,
                "attendance": _row_dict(att) if att else None,
            }
        )
    return {"date": day.isoformat(), "items": items, "total": len(items)}


def staff_attendance_report(
    db: Session,
    school_id: int,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    query = db.query(StaffAttendanceRecord).filter(
        StaffAttendanceRecord.school_id == school_id,
        StaffAttendanceRecord.deleted_at.is_(None),
    )
    if from_date:
        query = query.filter(StaffAttendanceRecord.attendance_date >= from_date)
    if to_date:
        query = query.filter(StaffAttendanceRecord.attendance_date <= to_date)
    rows = query.order_by(StaffAttendanceRecord.attendance_date.desc()).limit(500).all()
    present = sum(1 for r in rows if r.status == "present")
    absent = sum(1 for r in rows if r.status == "absent")
    return {
        "items": [_row_dict(r) for r in rows],
        "total": len(rows),
        "summary": {"present": present, "absent": absent},
    }


def get_staff_qr_settings(db: Session, school_id: int) -> dict:
    row = (
        db.query(StaffQrAttendanceSetting)
        .filter(StaffQrAttendanceSetting.school_id == school_id, StaffQrAttendanceSetting.deleted_at.is_(None))
        .first()
    )
    if row is None:
        return {"school_id": school_id, "enabled": 0, "token": None}
    return _row_dict(row)


def put_staff_qr_settings(db: Session, school_id: int, body: dict) -> dict:
    row = (
        db.query(StaffQrAttendanceSetting)
        .filter(StaffQrAttendanceSetting.school_id == school_id, StaffQrAttendanceSetting.deleted_at.is_(None))
        .first()
    )
    enabled = 1 if body.get("enabled") in (True, 1, "1", "true") else 0
    token = body.get("token")
    if enabled and not token:
        token = secrets.token_urlsafe(24)
    if row is None:
        row = StaffQrAttendanceSetting(
            school_id=school_id,
            enabled=enabled,
            token=str(token) if token else None,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
    else:
        row.enabled = enabled
        if token is not None:
            row.token = str(token)
        row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def list_staff_tasks(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, StaffTask, school_id, page=page, page_size=page_size)


def create_staff_task(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    staff_id = body.get("assigned_to_staff_id")
    if staff_id is not None:
        _same_school(db, Staff, int(staff_id), school_id, "Staff")
    row = StaffTask(
        school_id=school_id,
        title=title,
        description=body.get("description"),
        assigned_to_staff_id=int(staff_id) if staff_id is not None else None,
        due_date=_parse_date(body["due_date"], "due_date") if body.get("due_date") else None,
        status=str(body.get("status") or "open"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_staff_task(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, StaffTask, row_id, school_id)
    if "title" in body:
        row.title = str(body["title"] or "").strip()
    if "description" in body:
        row.description = body["description"]
    if "status" in body:
        row.status = str(body["status"])
    if "due_date" in body:
        row.due_date = _parse_date(body["due_date"], "due_date") if body["due_date"] else None
    if "assigned_to_staff_id" in body:
        sid = body["assigned_to_staff_id"]
        if sid is not None:
            _same_school(db, Staff, int(sid), school_id, "Staff")
            row.assigned_to_staff_id = int(sid)
        else:
            row.assigned_to_staff_id = None
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_staff_task(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, StaffTask, row_id, school_id))


# ---------------------------------------------------------------------------
# Expense / income / payroll
# ---------------------------------------------------------------------------


def list_expense_categories(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, ExpenseCategory, school_id, page=page, page_size=page_size)


def create_expense_category(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = ExpenseCategory(
        school_id=school_id, name=name, description=body.get("description"), created_at=_now(), updated_at=_now()
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_expense_category(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, ExpenseCategory, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "description" in body:
        row.description = body["description"]
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_expense_category(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, ExpenseCategory, row_id, school_id))


def list_income_categories(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, IncomeCategory, school_id, page=page, page_size=page_size)


def create_income_category(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = IncomeCategory(
        school_id=school_id, name=name, description=body.get("description"), created_at=_now(), updated_at=_now()
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_income_category(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, IncomeCategory, row_id, school_id))


def list_incomes(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, IncomeRecord, school_id, page=page, page_size=page_size)


def create_income(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "amount is required") from exc
    if not title or amount <= 0:
        raise AcademicError(422, "title and amount > 0 are required")
    cat = body.get("category_id")
    if cat is not None:
        _owned(db, IncomeCategory, int(cat), school_id)
    row = IncomeRecord(
        school_id=school_id,
        category_id=int(cat) if cat is not None else None,
        title=title,
        amount=amount,
        income_date=_parse_date(body.get("income_date") or body.get("date") or date.today().isoformat(), "income_date"),
        session_year_id=int(body["session_year_id"]) if body.get("session_year_id") else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_income(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, IncomeRecord, row_id, school_id)
    if "title" in body:
        row.title = str(body["title"] or "").strip()
    if "amount" in body:
        row.amount = float(body["amount"])
    if "income_date" in body or "date" in body:
        row.income_date = _parse_date(body.get("income_date") or body.get("date"), "income_date")
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_income(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, IncomeRecord, row_id, school_id))


def incomes_dashboard(db: Session, school_id: int) -> dict:
    income_total = (
        db.query(func.coalesce(func.sum(IncomeRecord.amount), 0))
        .filter(IncomeRecord.school_id == school_id, IncomeRecord.deleted_at.is_(None))
        .scalar()
    )
    expense_total = (
        db.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(Expense.school_id == school_id)
        .scalar()
    )
    return {
        "income_total": float(income_total or 0),
        "expense_total": float(expense_total or 0),
        "net": float(income_total or 0) - float(expense_total or 0),
    }


def get_payroll_settings(db: Session, school_id: int) -> dict:
    row = (
        db.query(PayrollSetting)
        .filter(PayrollSetting.school_id == school_id, PayrollSetting.deleted_at.is_(None))
        .first()
    )
    if row is None:
        return {"school_id": school_id, "pay_day": None, "currency": "INR", "notes": None}
    return _row_dict(row)


def put_payroll_settings(db: Session, school_id: int, body: dict) -> dict:
    row = (
        db.query(PayrollSetting)
        .filter(PayrollSetting.school_id == school_id, PayrollSetting.deleted_at.is_(None))
        .first()
    )
    if row is None:
        row = PayrollSetting(
            school_id=school_id,
            pay_day=int(body["pay_day"]) if body.get("pay_day") is not None else None,
            currency=str(body.get("currency") or "INR"),
            notes=body.get("notes"),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
    else:
        if "pay_day" in body:
            row.pay_day = int(body["pay_day"]) if body["pay_day"] is not None else None
        if "currency" in body:
            row.currency = str(body["currency"] or "INR")
        if "notes" in body:
            row.notes = body["notes"]
        row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def list_payroll_runs(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, PayrollRun, school_id, page=page, page_size=page_size)


def create_payroll_run(db: Session, school_id: int, body: dict) -> dict:
    period = str(body.get("period_label") or "").strip()
    if not period:
        raise AcademicError(422, "period_label is required")
    items = body.get("items") or []
    if not isinstance(items, list) or not items:
        raise AcademicError(422, "items must be a non-empty list")
    total = 0.0
    prepared = []
    for raw in items:
        staff_id = int(raw.get("staff_id") or 0)
        if not staff_id:
            raise AcademicError(422, "each item needs staff_id")
        _same_school(db, Staff, staff_id, school_id, "Staff")
        gross = float(raw.get("gross") or 0)
        deductions = float(raw.get("deductions") or 0)
        net = float(raw.get("net") if raw.get("net") is not None else gross - deductions)
        total += net
        prepared.append({"staff_id": staff_id, "gross": gross, "deductions": deductions, "net": net, "notes": raw.get("notes")})
    run = PayrollRun(
        school_id=school_id,
        period_label=period,
        run_date=_parse_date(body.get("run_date") or date.today().isoformat(), "run_date"),
        status=str(body.get("status") or "draft"),
        total_amount=total,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(run)
    db.flush()
    for item in prepared:
        db.add(
            PayrollItem(
                school_id=school_id,
                run_id=run.id,
                staff_id=item["staff_id"],
                gross=item["gross"],
                deductions=item["deductions"],
                net=item["net"],
                notes=item["notes"],
                created_at=_now(),
                updated_at=_now(),
            )
        )
    _commit(db)
    db.refresh(run)
    return _row_dict(run, {"items_count": len(prepared)})


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def list_vehicles(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, TransportVehicle, school_id, page=page, page_size=page_size)


def create_vehicle(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    reg = str(body.get("registration_no") or "").strip()
    if not name or not reg:
        raise AcademicError(422, "name and registration_no are required")
    row = TransportVehicle(
        school_id=school_id,
        name=name,
        registration_no=reg,
        capacity=int(body["capacity"]) if body.get("capacity") is not None else None,
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_vehicle(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, TransportVehicle, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "registration_no" in body:
        row.registration_no = str(body["registration_no"] or "").strip()
    if "capacity" in body:
        row.capacity = int(body["capacity"]) if body["capacity"] is not None else None
    if "status" in body:
        row.status = int(body["status"])
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_vehicle(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, TransportVehicle, row_id, school_id))


def _route_stops(db: Session, school_id: int, route_id: int) -> list[TransportStop]:
    return (
        db.query(TransportStop)
        .filter(
            TransportStop.school_id == school_id,
            TransportStop.route_id == route_id,
            TransportStop.deleted_at.is_(None),
        )
        .order_by(TransportStop.stop_order.asc())
        .all()
    )


def _route_item(db: Session, row: TransportRoute) -> dict:
    return _row_dict(row, {"stops": [_row_dict(s) for s in _route_stops(db, row.school_id, row.id)]})


def list_transport_routes(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(
        db, TransportRoute, school_id, page=page, page_size=page_size, serialize=lambda r: _route_item(db, r)
    )


def create_transport_route(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    vehicle_id = body.get("vehicle_id")
    if vehicle_id is not None:
        _owned(db, TransportVehicle, int(vehicle_id), school_id)
    row = TransportRoute(
        school_id=school_id,
        name=name,
        vehicle_id=int(vehicle_id) if vehicle_id is not None else None,
        description=body.get("description"),
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _route_item(db, row)


def update_transport_route(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, TransportRoute, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "description" in body:
        row.description = body["description"]
    if "status" in body:
        row.status = int(body["status"])
    if "vehicle_id" in body:
        vid = body["vehicle_id"]
        if vid is not None:
            _owned(db, TransportVehicle, int(vid), school_id)
            row.vehicle_id = int(vid)
        else:
            row.vehicle_id = None
    row.updated_at = _now()
    _commit(db)
    return _route_item(db, row)


def soft_delete_transport_route(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, TransportRoute, row_id, school_id)
    now = _now()
    for s in _route_stops(db, school_id, row.id):
        s.deleted_at = now
        s.updated_at = now
    return _soft_delete(db, row)


def list_transport_stops(db: Session, school_id: int, page: int = 1, page_size: int = 20, route_id: int | None = None) -> dict:
    def filt(q):
        if route_id is not None:
            q = q.filter(TransportStop.route_id == route_id)
        return q

    return _list_active(db, TransportStop, school_id, page=page, page_size=page_size, filters=filt)


def create_transport_stop(db: Session, school_id: int, body: dict) -> dict:
    route_id = int(body.get("route_id") or 0)
    name = str(body.get("name") or "").strip()
    if not route_id or not name:
        raise AcademicError(422, "route_id and name are required")
    _owned(db, TransportRoute, route_id, school_id)
    row = TransportStop(
        school_id=school_id,
        route_id=route_id,
        name=name,
        stop_order=int(body.get("stop_order") or 0),
        pickup_time=_parse_time(body.get("pickup_time"), "pickup_time"),
        drop_time=_parse_time(body.get("drop_time"), "drop_time"),
        landmark=body.get("landmark"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_transport_stop(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, TransportStop, row_id, school_id))


def list_student_transport_assignments(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, StudentTransportAssignment, school_id, page=page, page_size=page_size)


def create_student_transport_assignment(db: Session, school_id: int, body: dict) -> dict:
    student_id = int(body.get("student_id") or 0)
    route_id = int(body.get("route_id") or 0)
    if not student_id or not route_id:
        raise AcademicError(422, "student_id and route_id are required")
    _owned(db, Student, student_id, school_id)
    _owned(db, TransportRoute, route_id, school_id)
    stop_id = body.get("stop_id")
    if stop_id is not None:
        stop = _owned(db, TransportStop, int(stop_id), school_id)
        if stop.route_id != route_id:
            raise AcademicError(422, "stop does not belong to route")
    row = StudentTransportAssignment(
        school_id=school_id,
        student_id=student_id,
        route_id=route_id,
        stop_id=int(stop_id) if stop_id is not None else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_student_transport_assignment(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, StudentTransportAssignment, row_id, school_id))


# ---------------------------------------------------------------------------
# Certificates / ID cards
# ---------------------------------------------------------------------------


def list_certificate_templates(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, CertificateTemplate, school_id, page=page, page_size=page_size)


def create_certificate_template(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = CertificateTemplate(
        school_id=school_id,
        name=name,
        template_type=str(body.get("template_type") or "general"),
        body_text=body.get("body_text"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_certificate_template(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, CertificateTemplate, row_id, school_id)
    if "name" in body:
        row.name = str(body["name"] or "").strip()
    if "body_text" in body:
        row.body_text = body["body_text"]
    if "template_type" in body:
        row.template_type = str(body["template_type"])
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_certificate_template(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, CertificateTemplate, row_id, school_id))


def issue_certificate(db: Session, school_id: int, body: dict) -> dict:
    template_id = int(body.get("template_id") or 0)
    student_id = int(body.get("student_id") or 0)
    if not template_id or not student_id:
        raise AcademicError(422, "template_id and student_id are required")
    _owned(db, CertificateTemplate, template_id, school_id)
    student = _owned(db, Student, student_id, school_id)
    cert_no = str(body.get("certificate_no") or f"CERT-{school_id}-{student_id}-{int(_now().timestamp())}")
    row = CertificateIssue(
        school_id=school_id,
        template_id=template_id,
        student_id=student.id,
        certificate_no=cert_no,
        issued_at=_now(),
        data_json=json.dumps(body.get("data") or {}) if body.get("data") is not None else None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def get_id_card_settings(db: Session, school_id: int) -> dict:
    row = (
        db.query(IdCardSetting)
        .filter(IdCardSetting.school_id == school_id, IdCardSetting.deleted_at.is_(None))
        .first()
    )
    if row is None:
        return {"school_id": school_id, "front_template": None, "back_template": None, "show_fields_json": None}
    return _row_dict(row)


def put_id_card_settings(db: Session, school_id: int, body: dict) -> dict:
    row = (
        db.query(IdCardSetting)
        .filter(IdCardSetting.school_id == school_id, IdCardSetting.deleted_at.is_(None))
        .first()
    )
    if row is None:
        row = IdCardSetting(
            school_id=school_id,
            front_template=body.get("front_template"),
            back_template=body.get("back_template"),
            show_fields_json=json.dumps(body["show_fields"]) if isinstance(body.get("show_fields"), (dict, list)) else body.get("show_fields_json"),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
    else:
        if "front_template" in body:
            row.front_template = body["front_template"]
        if "back_template" in body:
            row.back_template = body["back_template"]
        if "show_fields" in body:
            row.show_fields_json = json.dumps(body["show_fields"])
        if "show_fields_json" in body:
            row.show_fields_json = body["show_fields_json"]
        row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def student_id_card_payload(db: Session, school_id: int, student_id: int) -> dict:
    student = _owned(db, Student, student_id, school_id)
    user = db.get(User, student.user_id)
    settings = get_id_card_settings(db, school_id)
    return {
        "type": "student",
        "student_id": student.id,
        "admission_no": student.admission_no,
        "roll_number": student.roll_number,
        "class_section_id": student.class_section_id,
        "session_year_id": student.session_year_id,
        "first_name": user.first_name if user else "",
        "last_name": user.last_name if user else "",
        "image": user.image if user else None,
        "settings": settings,
    }


def staff_id_card_payload(db: Session, school_id: int, staff_id: int) -> dict:
    staff = _same_school(db, Staff, staff_id, school_id, "Staff")
    user = db.get(User, staff.user_id)
    settings = get_id_card_settings(db, school_id)
    return {
        "type": "staff",
        "staff_id": staff.id,
        "employee_id": staff.employee_id,
        "department": staff.department,
        "designation": staff.designation,
        "first_name": user.first_name if user else "",
        "last_name": user.last_name if user else "",
        "image": user.image if user else None,
        "settings": settings,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def report_students(db: Session, school_id: int) -> dict:
    total = db.query(func.count(Student.id)).filter(Student.school_id == school_id, Student.deleted_at.is_(None)).scalar() or 0
    by_status = (
        db.query(Student.enrollment_status, func.count(Student.id))
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
        .group_by(Student.enrollment_status)
        .all()
    )
    return {
        "total": int(total),
        "by_enrollment_status": {s or "unknown": int(c) for s, c in by_status},
    }


def report_teachers(db: Session, school_id: int) -> dict:
    # Teachers are staff with Spatie Teacher role — approximate via Staff rows used as teachers.
    total = db.query(func.count(Staff.id)).filter(Staff.school_id == school_id).scalar() or 0
    return {"total_staff": int(total)}


def report_staff(db: Session, school_id: int) -> dict:
    total = db.query(func.count(Staff.id)).filter(Staff.school_id == school_id).scalar() or 0
    by_status = (
        db.query(Staff.employment_status, func.count(Staff.id))
        .filter(Staff.school_id == school_id)
        .group_by(Staff.employment_status)
        .all()
    )
    return {"total": int(total), "by_employment_status": {s or "unknown": int(c) for s, c in by_status}}


def report_exams(db: Session, school_id: int) -> dict:
    exams = db.query(func.count(Exam.id)).filter(Exam.school_id == school_id, Exam.deleted_at.is_(None)).scalar() or 0
    results = (
        db.query(func.count(OfflineExamResult.id))
        .filter(OfflineExamResult.school_id == school_id, OfflineExamResult.deleted_at.is_(None))
        .scalar()
        or 0
    )
    return {"exams": int(exams), "processed_results": int(results)}


def report_expenses(db: Session, school_id: int) -> dict:
    total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(Expense.school_id == school_id).scalar()
    count = db.query(func.count(Expense.id)).filter(Expense.school_id == school_id).scalar() or 0
    return {"total_amount": float(total or 0), "count": int(count)}


def report_income(db: Session, school_id: int) -> dict:
    total = (
        db.query(func.coalesce(func.sum(IncomeRecord.amount), 0))
        .filter(IncomeRecord.school_id == school_id, IncomeRecord.deleted_at.is_(None))
        .scalar()
    )
    count = (
        db.query(func.count(IncomeRecord.id))
        .filter(IncomeRecord.school_id == school_id, IncomeRecord.deleted_at.is_(None))
        .scalar()
        or 0
    )
    return {"total_amount": float(total or 0), "count": int(count)}


def report_financial_summary(db: Session, school_id: int) -> dict:
    income = report_income(db, school_id)
    expense = report_expenses(db, school_id)
    fees_collected = (
        db.query(func.coalesce(func.sum(FeePayment.amount), 0))
        .filter(
            FeePayment.school_id == school_id,
            FeePayment.deleted_at.is_(None),
            FeePayment.status == "success",
        )
        .scalar()
    )
    return {
        "income_total": income["total_amount"],
        "expense_total": expense["total_amount"],
        "fees_collected": float(fees_collected or 0),
        "net": income["total_amount"] - expense["total_amount"],
    }


# ---------------------------------------------------------------------------
# Diary / notifications / announcements / sliders / gallery
# ---------------------------------------------------------------------------


def list_diary_categories(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, DiaryCategory, school_id, page=page, page_size=page_size)


def create_diary_category(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    row = DiaryCategory(school_id=school_id, name=name, created_at=_now(), updated_at=_now())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_diary_category(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, DiaryCategory, row_id, school_id))


def list_student_diaries(db: Session, school_id: int, page: int = 1, page_size: int = 20, student_id: int | None = None) -> dict:
    def filt(q):
        if student_id is not None:
            q = q.filter(StudentDiaryEntry.student_id == student_id)
        return q

    return _list_active(db, StudentDiaryEntry, school_id, page=page, page_size=page_size, filters=filt)


def create_student_diary(db: Session, school_id: int, body: dict) -> dict:
    student_id = int(body.get("student_id") or 0)
    title = str(body.get("title") or "").strip()
    if not student_id or not title:
        raise AcademicError(422, "student_id and title are required")
    _owned(db, Student, student_id, school_id)
    cat = body.get("category_id")
    if cat is not None:
        _owned(db, DiaryCategory, int(cat), school_id)
    row = StudentDiaryEntry(
        school_id=school_id,
        category_id=int(cat) if cat is not None else None,
        student_id=student_id,
        title=title,
        body=body.get("body"),
        entry_date=_parse_date(body.get("entry_date") or date.today().isoformat(), "entry_date"),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_student_diary(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, StudentDiaryEntry, row_id, school_id))


def list_notifications(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(Notification).filter(
        Notification.school_id == school_id, Notification.deleted_at.is_(None)
    )
    total = query.count()
    rows = query.order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_row_dict(r) for r in rows], total, page, page_size)


def create_notification(db: Session, school_id: int, body: dict, *, created_by: str | None = None) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    row = Notification(
        title=title,
        body=body.get("body"),
        status=int(body.get("status", 1)),
        school_id=school_id,
        created_by=created_by,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def list_announcements(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(Announcement).filter(Announcement.school_id == school_id)
    total = query.count()
    rows = query.order_by(Announcement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_row_dict(r) for r in rows], total, page, page_size)


def create_announcement(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    session_year_id = int(body.get("session_year_id") or 0)
    if not title or not session_year_id:
        raise AcademicError(422, "title and session_year_id are required")
    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    row = Announcement(
        title=title,
        description=body.get("description") or body.get("body"),
        session_year_id=session_year_id,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def list_sliders(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, SchoolSlider, school_id, page=page, page_size=page_size)


def create_slider(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    row = SchoolSlider(
        school_id=school_id,
        title=title,
        image_url=body.get("image_url"),
        link_url=body.get("link_url"),
        sort_order=int(body.get("sort_order") or 0),
        status=int(body.get("status", 1)),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def update_slider(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SchoolSlider, row_id, school_id)
    for key in ("title", "image_url", "link_url"):
        if key in body:
            setattr(row, key, body[key] if key != "title" else str(body[key] or "").strip())
    if "sort_order" in body:
        row.sort_order = int(body["sort_order"])
    if "status" in body:
        row.status = int(body["status"])
    row.updated_at = _now()
    _commit(db)
    return _row_dict(row)


def soft_delete_slider(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, SchoolSlider, row_id, school_id))


def list_gallery(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    return _list_active(db, SchoolGalleryItem, school_id, page=page, page_size=page_size)


def create_gallery_item(db: Session, school_id: int, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AcademicError(422, "title is required")
    row = SchoolGalleryItem(
        school_id=school_id,
        title=title,
        image_url=body.get("image_url"),
        sort_order=int(body.get("sort_order") or 0),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _row_dict(row)


def soft_delete_gallery_item(db: Session, school_id: int, row_id: int) -> dict:
    return _soft_delete(db, _owned(db, SchoolGalleryItem, row_id, school_id))


# ---------------------------------------------------------------------------
# Subscription catalog (read-only)
# ---------------------------------------------------------------------------


def list_subscription_plans(db: Session, school_id: int) -> dict:
    del school_id  # catalog is global; auth still school-scoped at router
    rows = (
        db.query(Package)
        .filter(Package.deleted_at.is_(None), Package.status == 1)
        .order_by(Package.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "monthly_price": p.monthly_price,
                "yearly_price": p.yearly_price,
                "student_limit": p.student_limit,
                "staff_limit": p.staff_limit,
                "status": p.status,
            }
            for p in rows
        ],
        "total": len(rows),
    }


def list_subscription_addons(db: Session, school_id: int) -> dict:
    del school_id
    rows = (
        db.query(Addon)
        .filter(Addon.deleted_at.is_(None), Addon.status == 1)
        .order_by(Addon.id.asc())
        .all()
    )
    return {
        "items": [
            {"id": a.id, "name": a.name, "description": a.description, "price": a.price, "status": a.status}
            for a in rows
        ],
        "total": len(rows),
    }


# ---- Staff bulk upload + Spatie role permissions (school-scoped) ----


def list_staff_roles(db: Session, school_id: int) -> dict:
    """List Spatie web roles for this school (Teacher/Staff and any custom roles)."""
    from app.models.tables import Role

    rows = (
        db.query(Role)
        .filter(Role.school_id == school_id, Role.guard_name == "web")
        .order_by(Role.name.asc())
        .all()
    )
    return {
        "items": [{"id": r.id, "name": r.name, "school_id": r.school_id} for r in rows],
        "total": len(rows),
    }


def get_staff_user_roles(db: Session, school_id: int, user_id: int) -> dict:
    from app.models.tables import USER_MODEL, ModelHasRole, Role

    user = db.get(User, user_id)
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(404, "Staff user not found")
    roles = (
        db.query(Role)
        .join(ModelHasRole, ModelHasRole.role_id == Role.id)
        .filter(
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
        .order_by(Role.name.asc())
        .all()
    )
    return {
        "user_id": user_id,
        "roles": [{"id": r.id, "name": r.name} for r in roles],
    }


def set_staff_user_roles(db: Session, school_id: int, user_id: int, role_names: list[str]) -> dict:
    """Replace school-scoped Spatie roles for a staff/teacher user.

    Allowed names are existing school roles or Teacher/Staff (auto-created).
    Does not change v1 school-admin RBAC keys (those stay Super Admin).
    """
    from app.models.tables import USER_MODEL, ModelHasRole, Role
    from app.services.v1.school_academics import _assign_user_role, _ensure_school_role

    user = db.get(User, user_id)
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(404, "Staff user not found")
    if not role_names:
        raise AcademicError(422, "roles must be a non-empty list")

    cleaned = [str(n).strip() for n in role_names if str(n).strip()]
    if not cleaned:
        raise AcademicError(422, "roles must be a non-empty list")

    # Clear existing school web roles for this user.
    existing = (
        db.query(ModelHasRole)
        .join(Role, Role.id == ModelHasRole.role_id)
        .filter(
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
        .all()
    )
    for link in existing:
        db.delete(link)
    db.flush()

    for name in cleaned:
        role = _ensure_school_role(db, school_id, name)
        _assign_user_role(db, user_id, role)
    _commit(db)
    return get_staff_user_roles(db, school_id, user_id)


def bulk_import_staff(db: Session, school_id: int, rows: list[dict]) -> dict:
    """All-or-nothing non-teaching staff create (single commit)."""
    from app.models.tables import Staff
    from app.services.v1.school_academics import (
        _assert_unique_school_email,
        _assign_user_role,
        _ensure_school_role,
    )
    from app.services.v1.school_staff import STAFF_ROLE_NAME, _parse_employment_body, _require_password
    from app.services.v1.school_teachers import _assert_unique_employee_id

    if not rows:
        raise AcademicError(422, "rows must be a non-empty list")
    if len(rows) > 500:
        raise AcademicError(422, "At most 500 staff rows per import")

    created: list[dict] = []
    try:
        for idx, raw in enumerate(rows):
            body = sanitize_body(dict(raw))
            for field in ("first_name", "last_name", "email"):
                if field not in body or not str(body.get(field) or "").strip():
                    raise AcademicError(422, f"row {idx}: {field} is required")
            password = _require_password(body)
            email = str(body["email"]).strip().lower()
            _assert_unique_school_email(db, school_id, email)
            emp = _parse_employment_body(body, school_id=school_id, db=db)
            _assert_unique_employee_id(db, school_id, emp["employee_id"])

            user = User(
                first_name=str(body["first_name"]).strip(),
                last_name=str(body["last_name"]).strip(),
                email=email,
                mobile=(str(body["mobile"]).strip()[:255] if body.get("mobile") else None),
                password=hash_password(password),
                status=1,
                school_id=school_id,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(user)
            db.flush()
            staff = Staff(
                user_id=user.id,
                school_id=school_id,
                qualification=emp["qualification"],
                salary=emp["salary"],
                employee_id=emp["employee_id"],
                joining_date=emp["joining_date"],
                employment_status=emp["employment_status"],
                department=emp["department"],
                designation=emp["designation"],
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(staff)
            role = _ensure_school_role(db, school_id, STAFF_ROLE_NAME)
            _assign_user_role(db, user.id, role)
            created.append({"row": idx, "user_id": user.id, "staff_id": staff.id, "email": email})
        _commit(db)
    except AcademicError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AcademicError(422, f"Staff import failed: {exc}") from exc

    return {"created": len(created), "items": created}
