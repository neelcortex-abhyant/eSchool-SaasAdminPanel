"""Student online assessment flow (Module 5).

Identity from ``require_student_user``. Answer keys never returned on active attempts.
"""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_student_user
from app.models.tables import School, User
from app.services.v1 import school_online_assessments as oa_svc
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["student-online-assessments"])


class SaveAnswersBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[dict] = Field(default_factory=list)


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/student/online-assessments")
def student_list_online_assessments(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    db, user, school = tenant
    return _run(
        lambda: oa_svc.list_student_assessments(
            db, school.id, user, page=page, page_size=page_size
        )
    )


@router.post("/student/online-assessments/{assessment_id}/attempts", status_code=201)
def student_start_attempt(
    assessment_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: oa_svc.start_attempt(db, school.id, user, assessment_id))


@router.post("/student/online-assessment-attempts/{attempt_id}/answers")
def student_save_answers(
    attempt_id: int,
    body: SaveAnswersBody,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(
        lambda: oa_svc.save_answers(db, school.id, user, attempt_id, body.answers)
    )


@router.post("/student/online-assessment-attempts/{attempt_id}/submit")
def student_submit_attempt(
    attempt_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: oa_svc.submit_attempt(db, school.id, user, attempt_id))


@router.get("/student/online-assessment-attempts/{attempt_id}")
def student_get_attempt(
    attempt_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: oa_svc.get_my_attempt(db, school.id, user, attempt_id))
