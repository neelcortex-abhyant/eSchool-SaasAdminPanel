"""Report card PDF + student/parent portal reads (Exam.publish gated)."""

from __future__ import annotations

import json
from typing import Any

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.models.tables import Exam, ReportCard, School, Student, User
from app.services.v1.school_academics import AcademicError, _owned
from app.services.v1.school_offline_exams import _guardian_children


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
    return student


def _assert_portal_access(db: Session, school_id: int, user: User, student_id: int) -> Student:
    """Student owns via Student.user_id; parent via StudentGuardian / legacy guardian_id."""
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .first()
    )
    if student is None:
        raise AcademicError(404, "Record not found")
    if student.user_id == user.id:
        return student
    children = _guardian_children(db, user, school_id)
    if student.id in {c.id for c in children}:
        return student
    raise AcademicError(404, "Record not found")


def _published_report(db: Session, school_id: int, report: ReportCard) -> ReportCard:
    exam = _owned(db, Exam, report.exam_id, school_id)
    if not exam.publish:
        raise AcademicError(404, "Record not found")
    return report


def get_report_card_for_portal(
    db: Session,
    school_id: int,
    user: User,
    *,
    report_id: int | None = None,
    student_id: int | None = None,
    exam_id: int | None = None,
) -> dict:
    if report_id is not None:
        report = (
            db.query(ReportCard)
            .filter(
                ReportCard.id == report_id,
                ReportCard.school_id == school_id,
                ReportCard.deleted_at.is_(None),
            )
            .first()
        )
        if report is None:
            raise AcademicError(404, "Record not found")
        _assert_portal_access(db, school_id, user, report.student_id)
        _published_report(db, school_id, report)
        return _report_dict(db, report)

    if student_id is None or exam_id is None:
        raise AcademicError(422, "report_id or student_id+exam_id required")
    _assert_portal_access(db, school_id, user, student_id)
    exam = _owned(db, Exam, exam_id, school_id)
    if not exam.publish:
        raise AcademicError(404, "Record not found")
    report = (
        db.query(ReportCard)
        .filter(
            ReportCard.school_id == school_id,
            ReportCard.exam_id == exam_id,
            ReportCard.student_id == student_id,
            ReportCard.deleted_at.is_(None),
        )
        .first()
    )
    if report is None:
        raise AcademicError(404, "Record not found")
    return _report_dict(db, report)


def list_report_cards_for_student(db: Session, school_id: int, user: User) -> dict:
    student = _student_for_user(db, user, school_id)
    return list_report_cards_for_child(db, school_id, user, student.id)


def list_report_cards_for_child(
    db: Session, school_id: int, user: User, student_id: int
) -> dict:
    _assert_portal_access(db, school_id, user, student_id)
    rows = (
        db.query(ReportCard)
        .join(Exam, Exam.id == ReportCard.exam_id)
        .filter(
            ReportCard.school_id == school_id,
            ReportCard.student_id == student_id,
            ReportCard.deleted_at.is_(None),
            Exam.deleted_at.is_(None),
            Exam.publish == 1,
        )
        .order_by(ReportCard.id.desc())
        .all()
    )
    return {"items": [_report_dict(db, r) for r in rows], "total": len(rows)}


def _report_dict(db: Session, report: ReportCard) -> dict[str, Any]:
    subjects: Any = []
    if report.subjects_json:
        try:
            subjects = json.loads(report.subjects_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            subjects = []
    exam = db.get(Exam, report.exam_id)
    student = db.get(Student, report.student_id)
    student_user = db.get(User, student.user_id) if student else None
    name = ""
    if student_user:
        name = f"{student_user.first_name or ''} {student_user.last_name or ''}".strip()
    return {
        "id": report.id,
        "school_id": report.school_id,
        "exam_id": report.exam_id,
        "exam_name": getattr(exam, "name", None) if exam else None,
        "student_id": report.student_id,
        "student_name": name,
        "grading_scale_id": report.grading_scale_id,
        "percentage": float(report.percentage or 0),
        "letter_grade": report.letter_grade,
        "passed": int(report.passed or 0),
        "subjects": subjects,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


def render_report_card_pdf(db: Session, school_id: int, report_id: int) -> bytes:
    report = _owned(db, ReportCard, report_id, school_id)
    school = db.get(School, school_id)
    data = _report_dict(db, report)

    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    school_name = (school.name if school else None) or "School"
    pdf.cell(0, 10, str(school_name)[:80], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 8, "Report Card", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, f"Student: {data.get('student_name') or data['student_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Exam: {data.get('exam_name') or data['exam_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Percentage: {data['percentage']:.2f}%", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Grade: {data.get('letter_grade') or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Pass: {'Yes' if data.get('passed') else 'No'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Subjects", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    subjects = data.get("subjects") or []
    if isinstance(subjects, list):
        for subj in subjects:
            if isinstance(subj, dict):
                label = subj.get("name") or subj.get("subject") or subj.get("subject_name") or "Subject"
                obtained = subj.get("obtained") or subj.get("marks") or subj.get("obtained_marks")
                maximum = subj.get("max") or subj.get("max_marks") or subj.get("total")
                line = f"{label}: {obtained}/{maximum}" if maximum is not None else f"{label}: {obtained}"
            else:
                line = str(subj)
            pdf.cell(0, 6, line[:90], new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, "(no subject breakdown)", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def render_portal_report_card_pdf(
    db: Session, school_id: int, user: User, report_id: int
) -> bytes:
    get_report_card_for_portal(db, school_id, user, report_id=report_id)
    return render_report_card_pdf(db, school_id, report_id)
