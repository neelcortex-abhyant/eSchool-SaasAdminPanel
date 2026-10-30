"""School Admin payroll: salary structures, assignments, preview/process, payslips.

Formula (deterministic, no statutory tax/PF invented):
  gross = basic + sum(earning lines)
  deductions = sum(deduction lines)
  attendance_adjustment = 0 by default; when payroll_settings.apply_unpaid_leave_adjustment=1:
    unpaid_days = approved leave days in month where leave type is_paid=0
    attendance_adjustment = -(gross / working_days_per_month) * unpaid_days  (2dp)
  net = gross - deductions + attendance_adjustment

Jurisdiction limitation: amounts are structure-driven only — not India PF/ESI/TDS.
Legacy ``POST /payroll-runs`` with client amounts remains for compatibility but is
non-authoritative; ``POST /payroll/process`` is the authoritative path.
"""

from __future__ import annotations

import calendar
import json
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.models.tables import (
    Leave,
    LeaveType,
    PayrollAuditEvent,
    PayrollItem,
    PayrollRun,
    PayrollSetting,
    SalaryAssignment,
    SalaryStructure,
    SalaryStructureLine,
    Staff,
    User,
)
from app.services.v1.school_academics import (
    LEAVE_STATUS_APPROVED,
    AcademicError,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
    _same_school,
    _user_name,
)

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_MONEY_Q = Decimal("0.01")


def _money(value) -> float:
    return float(Decimal(str(value or 0)).quantize(_MONEY_Q, rounding=ROUND_HALF_UP))


def _parse_month(month: str | None) -> str:
    label = str(month or "").strip()
    if not _MONTH_RE.match(label):
        raise AcademicError(422, "month must be YYYY-MM")
    return label


def _month_bounds(period: str) -> tuple[date, date]:
    y, m = map(int, period.split("-"))
    last = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last)


def _structure_lines(db: Session, school_id: int, structure_id: int) -> list[SalaryStructureLine]:
    return (
        db.query(SalaryStructureLine)
        .filter(
            SalaryStructureLine.school_id == school_id,
            SalaryStructureLine.structure_id == structure_id,
            SalaryStructureLine.deleted_at.is_(None),
        )
        .order_by(SalaryStructureLine.id.asc())
        .all()
    )


def _calc_from_structure(
    structure: SalaryStructure,
    lines: list[SalaryStructureLine],
    *,
    attendance_adjustment: float = 0.0,
) -> dict:
    basic = _money(structure.basic or 0)
    earnings = []
    deductions = []
    earn_sum = Decimal("0")
    ded_sum = Decimal("0")
    for line in lines:
        amount = _money(line.amount or 0)
        item = {"name": line.name, "amount": amount, "kind": line.kind}
        if line.kind == "deduction":
            if amount < 0:
                raise AcademicError(422, "Deduction amounts must be non-negative")
            deductions.append(item)
            ded_sum += Decimal(str(amount))
        else:
            if amount < 0:
                raise AcademicError(422, "Earning amounts must be non-negative")
            earnings.append(item)
            earn_sum += Decimal(str(amount))
    adj = _money(attendance_adjustment)
    gross = _money(Decimal(str(basic)) + earn_sum)
    if basic < 0:
        raise AcademicError(422, "basic must be non-negative")
    net = _money(Decimal(str(gross)) - ded_sum + Decimal(str(adj)))
    if net < 0:
        raise AcademicError(422, "Net payable cannot be negative")
    return {
        "basic": basic,
        "allowances": earnings,
        "allowances_total": _money(earn_sum),
        "deductions": deductions,
        "deductions_total": _money(ded_sum),
        "attendance_adjustment": adj,
        "gross": gross,
        "net": net,
    }


def _structure_item(db: Session, school_id: int, row: SalaryStructure) -> dict:
    lines = _structure_lines(db, school_id, row.id)
    calc = _calc_from_structure(row, lines)
    assigned = (
        db.query(SalaryAssignment)
        .filter(
            SalaryAssignment.school_id == school_id,
            SalaryAssignment.structure_id == row.id,
            SalaryAssignment.deleted_at.is_(None),
        )
        .count()
    )
    return {
        "id": row.id,
        "name": row.name,
        "basic": calc["basic"],
        "allowances": calc["allowances"],
        "deductions": calc["deductions"],
        "gross": calc["gross"],
        "net": calc["net"],
        "assigned": int(assigned),
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_salary_structures(db: Session, school_id: int, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(SalaryStructure).filter(
        SalaryStructure.school_id == school_id,
        SalaryStructure.deleted_at.is_(None),
    )
    total = query.count()
    rows = query.order_by(SalaryStructure.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_structure_item(db, school_id, r) for r in rows], total, page, page_size)


def get_salary_structure(db: Session, school_id: int, row_id: int) -> dict:
    return _structure_item(db, school_id, _owned(db, SalaryStructure, row_id, school_id))


def _replace_structure_lines(
    db: Session,
    school_id: int,
    structure_id: int,
    allowances: list | None,
    deductions: list | None,
) -> None:
    now = _now()
    existing = _structure_lines(db, school_id, structure_id)
    for line in existing:
        line.deleted_at = now
        line.updated_at = now
    for raw in allowances or []:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        db.add(
            SalaryStructureLine(
                school_id=school_id,
                structure_id=structure_id,
                component_id=int(raw["component_id"]) if raw.get("component_id") else None,
                name=name[:255],
                kind="earning",
                amount=float(raw.get("amount") or 0),
                created_at=now,
                updated_at=now,
            )
        )
    for raw in deductions or []:
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        db.add(
            SalaryStructureLine(
                school_id=school_id,
                structure_id=structure_id,
                component_id=int(raw["component_id"]) if raw.get("component_id") else None,
                name=name[:255],
                kind="deduction",
                amount=float(raw.get("amount") or 0),
                created_at=now,
                updated_at=now,
            )
        )


def create_salary_structure(db: Session, school_id: int, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    if not name:
        raise AcademicError(422, "name is required")
    now = _now()
    row = SalaryStructure(
        school_id=school_id,
        name=name[:255],
        basic=float(body.get("basic") or 0),
        is_active=1 if body.get("is_active", True) else 0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    _replace_structure_lines(
        db, school_id, row.id, body.get("allowances") or [], body.get("deductions") or []
    )
    _commit(db)
    db.refresh(row)
    return _structure_item(db, school_id, row)


def update_salary_structure(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SalaryStructure, row_id, school_id)
    if "name" in body and body["name"] is not None:
        name = str(body["name"]).strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name[:255]
    if "basic" in body and body["basic"] is not None:
        row.basic = float(body["basic"])
    if "is_active" in body and body["is_active"] is not None:
        row.is_active = 1 if body["is_active"] else 0
    if "allowances" in body or "deductions" in body:
        current = _structure_lines(db, school_id, row.id)
        keep_allowances = [
            {"name": l.name, "amount": float(l.amount or 0), "component_id": l.component_id}
            for l in current
            if l.kind != "deduction"
        ]
        keep_deductions = [
            {"name": l.name, "amount": float(l.amount or 0), "component_id": l.component_id}
            for l in current
            if l.kind == "deduction"
        ]
        allowances = body.get("allowances") if "allowances" in body else keep_allowances
        deductions = body.get("deductions") if "deductions" in body else keep_deductions
        _replace_structure_lines(db, school_id, row.id, allowances, deductions)
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _structure_item(db, school_id, row)


def soft_delete_salary_structure(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, SalaryStructure, row_id, school_id)
    assigned = (
        db.query(SalaryAssignment)
        .filter(
            SalaryAssignment.school_id == school_id,
            SalaryAssignment.structure_id == row.id,
            SalaryAssignment.deleted_at.is_(None),
        )
        .count()
    )
    if assigned:
        raise AcademicError(409, "Cannot delete salary structure while employees are assigned")
    row.deleted_at = _now()
    row.updated_at = row.deleted_at
    _commit(db)
    return {"id": row_id, "deleted": True}


def _assignment_item(db: Session, row: SalaryAssignment) -> dict:
    staff = db.get(Staff, row.staff_id)
    user = db.get(User, staff.user_id) if staff else None
    structure = db.get(SalaryStructure, row.structure_id)
    return {
        "id": row.id,
        "staff_id": row.staff_id,
        "staff_name": _user_name(user) if user else None,
        "structure_id": row.structure_id,
        "structure_name": structure.name if structure else None,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if getattr(row, "effective_to", None) else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_salary_assignments(
    db: Session,
    school_id: int,
    page: int = 1,
    page_size: int = 20,
    *,
    include_history: bool = False,
    staff_id: int | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(SalaryAssignment).filter(SalaryAssignment.school_id == school_id)
    if not include_history:
        query = query.filter(
            SalaryAssignment.deleted_at.is_(None),
            SalaryAssignment.effective_to.is_(None),
        )
    if staff_id is not None:
        query = query.filter(SalaryAssignment.staff_id == int(staff_id))
    total = query.count()
    rows = query.order_by(SalaryAssignment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_assignment_item(db, r) for r in rows], total, page, page_size)


def create_salary_assignments(db: Session, school_id: int, body: dict) -> dict:
    structure_id = int(body.get("structure_id") or 0)
    if not structure_id:
        raise AcademicError(422, "structure_id is required")
    structure = _owned(db, SalaryStructure, structure_id, school_id)
    if not structure.is_active:
        raise AcademicError(422, "Salary structure is inactive")
    staff_ids = body.get("staff_ids") or []
    if body.get("staff_id") is not None:
        staff_ids = list(staff_ids) + [body["staff_id"]]
    if not isinstance(staff_ids, list) or not staff_ids:
        raise AcademicError(422, "staff_ids is required")
    eff = body.get("effective_from") or date.today().isoformat()
    if isinstance(eff, date) and not isinstance(eff, datetime):
        effective_from = eff
    else:
        try:
            effective_from = date.fromisoformat(str(eff)[:10])
        except ValueError as exc:
            raise AcademicError(422, "effective_from must be YYYY-MM-DD") from exc
    now = _now()
    created = []
    for raw_id in staff_ids:
        staff_id = int(raw_id)
        _same_school(db, Staff, staff_id, school_id, "Staff")
        current = (
            db.query(SalaryAssignment)
            .filter(
                SalaryAssignment.school_id == school_id,
                SalaryAssignment.staff_id == staff_id,
                SalaryAssignment.deleted_at.is_(None),
                SalaryAssignment.effective_to.is_(None),
            )
            .first()
        )
        if current is not None:
            # Soft-close prior assignment (history retained).
            current.effective_to = effective_from - timedelta(days=1)
            if current.effective_to < current.effective_from:
                current.effective_to = current.effective_from
            current.updated_at = now
        row = SalaryAssignment(
            school_id=school_id,
            staff_id=staff_id,
            structure_id=structure_id,
            effective_from=effective_from,
            effective_to=None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        created.append(row)
    _commit(db)
    for row in created:
        db.refresh(row)
    return {
        "items": [_assignment_item(db, r) for r in created],
        "total": len(created),
        "page": 1,
        "page_size": len(created),
    }


def _assignment_for_month(
    db: Session, school_id: int, staff_id: int, period: str
) -> SalaryAssignment | None:
    """Resolve structure assignment effective on the last day of the payroll month."""
    _start, month_end = _month_bounds(period)
    rows = (
        db.query(SalaryAssignment)
        .filter(
            SalaryAssignment.school_id == school_id,
            SalaryAssignment.staff_id == staff_id,
            SalaryAssignment.deleted_at.is_(None),
            SalaryAssignment.effective_from <= month_end,
        )
        .order_by(SalaryAssignment.effective_from.desc(), SalaryAssignment.id.desc())
        .all()
    )
    for row in rows:
        if row.effective_to is None or row.effective_to >= month_end:
            return row
        if row.effective_from <= month_end <= row.effective_to:
            return row
    return None


def _active_assignment(db: Session, school_id: int, staff_id: int) -> SalaryAssignment | None:
    return (
        db.query(SalaryAssignment)
        .filter(
            SalaryAssignment.school_id == school_id,
            SalaryAssignment.staff_id == staff_id,
            SalaryAssignment.deleted_at.is_(None),
            SalaryAssignment.effective_to.is_(None),
        )
        .first()
    )


def _processed_or_paid_run(db: Session, school_id: int, period: str) -> PayrollRun | None:
    return (
        db.query(PayrollRun)
        .filter(
            PayrollRun.school_id == school_id,
            PayrollRun.period_label == period,
            PayrollRun.deleted_at.is_(None),
            PayrollRun.status.in_(["processed", "paid"]),
        )
        .first()
    )


def _processed_run_for_period(db: Session, school_id: int, period: str) -> PayrollRun | None:
    return _processed_or_paid_run(db, school_id, period)


def _payroll_settings(db: Session, school_id: int) -> PayrollSetting | None:
    return (
        db.query(PayrollSetting)
        .filter(PayrollSetting.school_id == school_id, PayrollSetting.deleted_at.is_(None))
        .first()
    )


def _unpaid_leave_days(db: Session, school_id: int, user_id: int, period: str) -> int:
    start, end = _month_bounds(period)
    leaves = (
        db.query(Leave)
        .filter(
            Leave.school_id == school_id,
            Leave.user_id == user_id,
            Leave.status == LEAVE_STATUS_APPROVED,
            Leave.from_date <= end,
            Leave.to_date >= start,
        )
        .all()
    )
    days = 0
    for lv in leaves:
        unpaid = True
        if lv.leave_type_id:
            lt = db.get(LeaveType, lv.leave_type_id)
            if lt is not None and lt.school_id == school_id and int(lt.is_paid or 0) == 1:
                unpaid = False
        if not unpaid:
            continue
        a = max(lv.from_date, start)
        b = min(lv.to_date, end)
        if b >= a:
            days += (b - a).days + 1
    return days


def _preview_line(db: Session, school_id: int, staff: Staff, period: str) -> dict:
    user = db.get(User, staff.user_id)
    name = _user_name(user) if user else f"Staff {staff.id}"
    assignment = _assignment_for_month(db, school_id, staff.id, period)
    if assignment is None:
        return {
            "staff_id": staff.id,
            "name": name,
            "department": staff.department,
            "structure_name": None,
            "basic": 0,
            "allowances": 0,
            "deductions": 0,
            "attendance_adjustment": 0,
            "working_days": None,
            "paid_days": None,
            "net": 0,
            "eligible": False,
            "problem": "No salary structure assigned",
        }
    structure = _owned(db, SalaryStructure, assignment.structure_id, school_id)
    lines = _structure_lines(db, school_id, structure.id)
    settings = _payroll_settings(db, school_id)
    adj = 0.0
    working_days = int(settings.working_days_per_month) if settings and settings.working_days_per_month else 30
    unpaid_days = 0
    base = _calc_from_structure(structure, lines, attendance_adjustment=0)
    if settings and int(getattr(settings, "apply_unpaid_leave_adjustment", 0) or 0) == 1:
        unpaid_days = _unpaid_leave_days(db, school_id, staff.user_id, period)
        if unpaid_days and working_days > 0:
            daily = Decimal(str(base["gross"])) / Decimal(str(working_days))
            adj = _money(-(daily * Decimal(str(unpaid_days))))
    calc = _calc_from_structure(structure, lines, attendance_adjustment=adj)
    paid_days = max(0, working_days - unpaid_days) if settings and int(getattr(settings, "apply_unpaid_leave_adjustment", 0) or 0) else None
    return {
        "staff_id": staff.id,
        "name": name,
        "department": staff.department,
        "structure_name": structure.name,
        "basic": calc["basic"],
        "allowances": calc["allowances_total"],
        "deductions": calc["deductions_total"],
        "attendance_adjustment": calc["attendance_adjustment"],
        "working_days": working_days if paid_days is not None else None,
        "paid_days": paid_days,
        "unpaid_leave_days": unpaid_days if paid_days is not None else 0,
        "gross": calc["gross"],
        "net": calc["net"],
        "eligible": True,
        "problem": None,
        "breakdown": calc,
    }


def payroll_preview(
    db: Session,
    school_id: int,
    month: str,
    *,
    department: str | None = None,
) -> dict:
    period = _parse_month(month)
    q = db.query(Staff).filter(Staff.school_id == school_id)
    if department and department.strip():
        q = q.filter(Staff.department.ilike(department.strip()))
    staff_rows = q.order_by(Staff.id.asc()).all()
    items = [_preview_line(db, school_id, s, period) for s in staff_rows]
    total_net = _money(sum(float(i.get("net") or 0) for i in items if i.get("eligible")))
    already = _processed_run_for_period(db, school_id, period) is not None
    return {
        "month": period,
        "items": items,
        "total_net": total_net,
        "already_processed": already,
    }


def _audit(
    db: Session,
    school_id: int,
    run_id: int | None,
    actor_user_id: int | None,
    action: str,
    detail: dict | None = None,
    *,
    actor_v1: str | None = None,
) -> None:
    payload = dict(detail or {})
    if actor_v1:
        payload["actor_v1"] = str(actor_v1)
    db.add(
        PayrollAuditEvent(
            school_id=school_id,
            run_id=run_id,
            actor_user_id=actor_user_id,
            action=action,
            detail_json=json.dumps(payload) if payload else None,
            created_at=_now(),
            updated_at=_now(),
        )
    )


def process_payroll(
    db: Session,
    school_id: int,
    body: dict,
    *,
    idempotency_key: str | None = None,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> dict:
    # Client-supplied line amounts are never accepted — process is structure-driven only.
    forbidden = [k for k in ("items", "total_amount", "gross", "net", "deductions") if k in body and body.get(k) is not None]
    if forbidden:
        raise AcademicError(
            422,
            "Client-supplied payroll amounts are not accepted. "
            "Send only {month}; amounts come from salary structures and preview.",
        )
    period = _parse_month(body.get("month") or body.get("period_label"))
    if idempotency_key:
        existing_key = (
            db.query(PayrollRun)
            .filter(
                PayrollRun.school_id == school_id,
                PayrollRun.idempotency_key == idempotency_key,
                PayrollRun.deleted_at.is_(None),
            )
            .first()
        )
        if existing_key is not None:
            return _process_result(db, school_id, existing_key)

    existing = _processed_run_for_period(db, school_id, period)
    if existing is not None:
        raise AcademicError(409, "Payroll period already processed")

    preview = payroll_preview(db, school_id, period)
    now = _now()
    try:
        run = PayrollRun(
            school_id=school_id,
            period_label=period,
            run_date=date.today(),
            status="processed",
            total_amount=0,
            processed_at=now,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        db.flush()

        processed = 0
        failed = 0
        total = 0.0
        for line in preview["items"]:
            staff_id = int(line["staff_id"])
            if not line.get("eligible"):
                failed += 1
                db.add(
                    PayrollItem(
                        school_id=school_id,
                        run_id=run.id,
                        staff_id=staff_id,
                        gross=0,
                        deductions=0,
                        net=0,
                        breakdown_json=json.dumps(line),
                        payslip_ref=None,
                        status="failed",
                        failure_reason=line.get("problem") or "Ineligible",
                        created_at=now,
                        updated_at=now,
                    )
                )
                continue
            breakdown = line.get("breakdown") or {}
            # Always take server-calculated breakdown; never trust client body amounts.
            gross = _money(breakdown.get("gross") or line.get("gross") or 0)
            deductions = _money(breakdown.get("deductions_total") or line.get("deductions") or 0)
            net = _money(breakdown.get("net") or line.get("net") or 0)
            total = _money(total + net)
            processed += 1
            ref = f"PS-{school_id}-{period}-{staff_id}-{run.id}"
            db.add(
                PayrollItem(
                    school_id=school_id,
                    run_id=run.id,
                    staff_id=staff_id,
                    gross=gross,
                    deductions=deductions,
                    net=net,
                    breakdown_json=json.dumps(breakdown),
                    payslip_ref=ref,
                    status="processed",
                    created_at=now,
                    updated_at=now,
                )
            )
        run.total_amount = _money(total)
        _audit(
            db,
            school_id,
            run.id,
            actor_user_id,
            "process",
            {"month": period, "processed": processed, "failed": failed},
            actor_v1=actor_v1,
        )
        _commit(db)
        db.refresh(run)
        return {
            "processed": processed,
            "failed": failed,
            "run_id": run.id,
            "month": period,
            "total_net": _money(total),
        }
    except AcademicError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def _process_result(db: Session, school_id: int, run: PayrollRun) -> dict:
    items = (
        db.query(PayrollItem)
        .filter(
            PayrollItem.school_id == school_id,
            PayrollItem.run_id == run.id,
            PayrollItem.deleted_at.is_(None),
        )
        .all()
    )
    processed = sum(1 for i in items if i.status == "processed")
    failed = sum(1 for i in items if i.status == "failed")
    return {
        "processed": processed,
        "failed": failed,
        "run_id": run.id,
        "month": run.period_label,
        "total_net": float(run.total_amount or 0),
        "idempotent_replay": True,
    }


def payroll_summary(db: Session, school_id: int, year: int) -> list[dict]:
    yr = int(year)
    prefix = f"{yr}-"
    runs = (
        db.query(PayrollRun)
        .filter(
            PayrollRun.school_id == school_id,
            PayrollRun.deleted_at.is_(None),
            PayrollRun.period_label.like(f"{prefix}%"),
        )
        .all()
    )
    by_month: dict[str, dict] = {}
    for m in range(1, 13):
        key = f"{yr}-{m:02d}"
        by_month[key] = {
            "month": key,
            "processed": 0,
            "pending": 0,
            "failed": 0,
            "total_net": 0.0,
        }
    for run in runs:
        bucket = by_month.get(run.period_label)
        if bucket is None:
            continue
        items = (
            db.query(PayrollItem)
            .filter(
                PayrollItem.school_id == school_id,
                PayrollItem.run_id == run.id,
                PayrollItem.deleted_at.is_(None),
            )
            .all()
        )
        if run.status in ("processed", "paid"):
            bucket["processed"] = sum(1 for i in items if i.status == "processed")
            bucket["failed"] = sum(1 for i in items if i.status == "failed")
            bucket["total_net"] = _money(run.total_amount or 0)
            if run.status == "paid":
                bucket["paid"] = 1
        else:
            bucket["pending"] = len(items) or 1
    return [by_month[f"{yr}-{m:02d}"] for m in range(1, 13)]


def mark_payroll_paid(
    db: Session,
    school_id: int,
    run_id: int,
    *,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> dict:
    run = _owned(db, PayrollRun, run_id, school_id)
    if run.status == "paid":
        return _row_run(run)
    if run.status != "processed":
        raise AcademicError(409, "Only processed payroll runs can be marked paid")
    run.status = "paid"
    run.updated_at = _now()
    _audit(
        db,
        school_id,
        run.id,
        actor_user_id,
        "mark_paid",
        {"month": run.period_label},
        actor_v1=actor_v1,
    )
    _commit(db)
    db.refresh(run)
    return _row_run(run)


def _row_run(run: PayrollRun) -> dict:
    return {
        "id": run.id,
        "school_id": run.school_id,
        "period_label": run.period_label,
        "run_date": run.run_date.isoformat() if run.run_date else None,
        "status": run.status,
        "total_amount": _money(run.total_amount or 0),
        "processed_at": run.processed_at.isoformat() if run.processed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def list_payroll_audit_events(
    db: Session, school_id: int, *, page: int = 1, page_size: int = 20, run_id: int | None = None
) -> dict:
    page, page_size = _page(page, page_size)
    q = db.query(PayrollAuditEvent).filter(PayrollAuditEvent.school_id == school_id)
    if run_id is not None:
        q = q.filter(PayrollAuditEvent.run_id == int(run_id))
    total = q.count()
    rows = q.order_by(PayrollAuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": r.id,
            "run_id": r.run_id,
            "actor_user_id": r.actor_user_id,
            "action": r.action,
            "detail_json": r.detail_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return _envelope(items, total, page, page_size)


def _payslip_item(db: Session, item: PayrollItem, run: PayrollRun | None = None) -> dict:
    run = run or db.get(PayrollRun, item.run_id)
    staff = db.get(Staff, item.staff_id)
    user = db.get(User, staff.user_id) if staff else None
    breakdown: dict[str, Any] = {}
    if item.breakdown_json:
        try:
            breakdown = json.loads(item.breakdown_json)
        except (TypeError, ValueError):
            breakdown = {}
    return {
        "id": item.id,
        "month": run.period_label if run else None,
        "staff_id": item.staff_id,
        "name": _user_name(user) if user else None,
        "employee_code": staff.employee_id if staff else None,
        "department": staff.department if staff else None,
        "designation": staff.designation if staff else None,
        "basic": float(breakdown.get("basic") or 0),
        "allowances": breakdown.get("allowances") or [],
        "deductions": breakdown.get("deductions") or [],
        "attendance_adjustment": float(breakdown.get("attendance_adjustment") or 0),
        "working_days": breakdown.get("working_days"),
        "paid_days": breakdown.get("paid_days"),
        "gross": float(item.gross or 0),
        "net": float(item.net or 0),
        "status": item.status or "processed",
        "processed_at": run.processed_at.isoformat() if run and run.processed_at else None,
        "failure_reason": item.failure_reason,
        "payslip_ref": item.payslip_ref,
        "run_id": item.run_id,
    }


def list_payslips(
    db: Session,
    school_id: int,
    *,
    month: str | None = None,
    staff_id: int | None = None,
    status_filter: str | None = None,
    department: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(PayrollItem).filter(
        PayrollItem.school_id == school_id,
        PayrollItem.deleted_at.is_(None),
    )
    if staff_id is not None:
        query = query.filter(PayrollItem.staff_id == int(staff_id))
    if status_filter:
        query = query.filter(PayrollItem.status == status_filter)
    if department and department.strip():
        staff_ids = [
            s.id
            for s in db.query(Staff)
            .filter(
                Staff.school_id == school_id,
                Staff.department.ilike(department.strip()),
            )
            .all()
        ]
        if not staff_ids:
            return _envelope([], 0, page, page_size)
        query = query.filter(PayrollItem.staff_id.in_(staff_ids))
    if month:
        period = _parse_month(month)
        run_ids = [
            r.id
            for r in db.query(PayrollRun)
            .filter(
                PayrollRun.school_id == school_id,
                PayrollRun.period_label == period,
                PayrollRun.deleted_at.is_(None),
            )
            .all()
        ]
        if not run_ids:
            return _envelope([], 0, page, page_size)
        query = query.filter(PayrollItem.run_id.in_(run_ids))
    total = query.count()
    rows = query.order_by(PayrollItem.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_payslip_item(db, r) for r in rows], total, page, page_size)


def get_payslip(db: Session, school_id: int, row_id: int) -> dict:
    item = _owned(db, PayrollItem, row_id, school_id)
    return _payslip_item(db, item)


def render_payslip_pdf(db: Session, school_id: int, row_id: int) -> bytes:
    slip = get_payslip(db, school_id, row_id)
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Payslip", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, f"Month: {slip.get('month')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Employee: {slip.get('name') or slip['staff_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Code: {slip.get('employee_code') or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Basic: {slip.get('basic'):.2f}", new_x="LMARGIN", new_y="NEXT")
    for a in slip.get("allowances") or []:
        pdf.cell(0, 6, f"+ {a.get('name')}: {float(a.get('amount') or 0):.2f}", new_x="LMARGIN", new_y="NEXT")
    for d in slip.get("deductions") or []:
        pdf.cell(0, 6, f"- {d.get('name')}: {float(d.get('amount') or 0):.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Gross: {slip.get('gross'):.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Net: {slip.get('net'):.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Status: {slip.get('status')}", new_x="LMARGIN", new_y="NEXT")
    note = (
        "Amounts from salary structure only. No statutory tax/PF/ESI computed."
    )
    pdf.set_font("Helvetica", size=8)
    pdf.multi_cell(0, 5, note)
    return bytes(pdf.output())
