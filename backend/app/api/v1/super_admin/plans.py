"""Super Admin plan (Package) management — /api/v1/super-admin/plans."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.plans import (
    PlanCreateRequest,
    PlanListResponse,
    PlanResponse,
    PlanStatusRequest,
    PlanUpdateRequest,
)
from app.services.v1 import audit_service, plan_service

router = APIRouter(prefix="/plans", tags=["v1-super-admin-plans"])


def _http(exc: plan_service.PlanServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> PlanResponse:
    try:
        plan = plan_service.create_plan(
            db,
            name=body.name,
            description=body.description,
            monthly_price=body.monthly_price,
            yearly_price=body.yearly_price,
            student_limit=body.student_limit,
            staff_limit=body.staff_limit,
        )
    except plan_service.PlanServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="plan.create",
        entity_type="plan",
        entity_id=plan.id,
        metadata={"name": plan.name},
    )
    return PlanResponse.model_validate(plan)


@router.get("", response_model=PlanListResponse)
def list_plans(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
    name: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> PlanListResponse:
    try:
        rows, total = plan_service.list_plans(
            db,
            page=page,
            page_size=page_size,
            status=status_filter,
            name=name,
            include_deleted=include_deleted,
        )
    except plan_service.PlanServiceError as exc:
        raise _http(exc) from exc
    return PlanListResponse(
        items=[PlanResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> PlanResponse:
    try:
        plan = plan_service.get_plan(db, plan_id)
    except plan_service.PlanServiceError as exc:
        raise _http(exc) from exc
    return PlanResponse.model_validate(plan)


@router.patch("/{plan_id}", response_model=PlanResponse)
def patch_plan(
    plan_id: int,
    body: PlanUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> PlanResponse:
    fields = body.model_fields_set
    try:
        plan = plan_service.update_plan(
            db,
            plan_id,
            name=body.name,
            description=body.description,
            monthly_price=body.monthly_price,
            yearly_price=body.yearly_price,
            student_limit=body.student_limit,
            student_limit_set="student_limit" in fields,
            staff_limit=body.staff_limit,
            staff_limit_set="staff_limit" in fields,
        )
    except plan_service.PlanServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="plan.update",
        entity_type="plan",
        entity_id=plan.id,
        metadata={"name": plan.name},
    )
    return PlanResponse.model_validate(plan)


@router.patch("/{plan_id}/status", response_model=PlanResponse)
def patch_plan_status(
    plan_id: int,
    body: PlanStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> PlanResponse:
    try:
        plan = plan_service.set_plan_status(db, plan_id, status=body.status)
    except plan_service.PlanServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="plan.status",
        entity_type="plan",
        entity_id=plan.id,
        metadata={"status": plan.status},
    )
    return PlanResponse.model_validate(plan)
