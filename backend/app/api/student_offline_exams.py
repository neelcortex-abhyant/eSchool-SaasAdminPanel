"""Student and parent offline exam result reads (Module 6).

Publication gated by ``Exam.publish``. Parent access uses ``require_guardian_user``
and linked children (StudentGuardian / legacy guardian_id).
"""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_guardian_user, require_student_user
from app.models.tables import School, User
from app.services.v1 import school_offline_exams as offline_svc
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["student-offline-exams"])


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/student/offline-exams")
def student_list_offline_exams(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    db, user, school = tenant
    return _run(
        lambda: offline_svc.list_student_exams(
            db, school.id, user, page=page, page_size=page_size
        )
    )


@router.get("/student/offline-exams/{exam_id}/result")
def student_offline_exam_result(
    exam_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: offline_svc.get_student_result(db, school.id, user, exam_id))


@router.get("/parent/offline-exams/{exam_id}/children/{student_id}/result")
def parent_offline_exam_child_result(
    exam_id: int,
    student_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant
    return _run(
        lambda: offline_svc.get_parent_child_result(
            db, school.id, user, exam_id, student_id
        )
    )
