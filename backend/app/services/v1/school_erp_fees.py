"""Fee installments, payment allocation, cancel, receipts, collection reports."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fpdf import FPDF
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.tables import (
    AuditLog,
    FeeAssignment,
    FeeConcession,
    FeeInstallment,
    FeePayment,
    FeePaymentAllocation,
    FeeStructure,
    FeeStructureAmount,
    School,
    Student,
    User,
)
from app.services.v1.school_academics import AcademicError, _commit, _now, _owned
from app.services.v1.school_offline_exams import _guardian_children


def inr_quantize(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def inr_float(value: Decimal | float | int | str) -> float:
    return float(inr_quantize(value))


def validate_installment_sum(structure_total: Decimal | float, items: list[dict]) -> Decimal:
    """Raise 422 if installment amounts do not sum to structure total (INR 2dp)."""
    total = inr_quantize(structure_total)
    if not items:
        raise AcademicError(422, "installments must be a non-empty list")
    summed = Decimal("0.00")
    for raw in items:
        amt = inr_quantize(raw.get("amount") or 0)
        if amt <= 0:
            raise AcademicError(422, "each installment amount must be > 0")
        summed += amt
    summed = inr_quantize(summed)
    if summed != total:
        raise AcademicError(
            422,
            f"installment amounts must sum to structure total ({total}); got {summed}",
        )
    return summed


def _structure_total_dec(db: Session, school_id: int, structure_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(FeeStructureAmount.amount), 0))
        .filter(
            FeeStructureAmount.school_id == school_id,
            FeeStructureAmount.structure_id == structure_id,
            FeeStructureAmount.deleted_at.is_(None),
        )
        .scalar()
    )
    return inr_quantize(total or 0)


def _active_installments(db: Session, school_id: int, structure_id: int) -> list[FeeInstallment]:
    return (
        db.query(FeeInstallment)
        .filter(
            FeeInstallment.school_id == school_id,
            FeeInstallment.structure_id == structure_id,
            FeeInstallment.deleted_at.is_(None),
        )
        .order_by(FeeInstallment.due_date.asc(), FeeInstallment.sort_order.asc(), FeeInstallment.id.asc())
        .all()
    )


def _installment_allocated(db: Session, school_id: int, installment_id: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(FeePaymentAllocation.amount), 0))
        .filter(
            FeePaymentAllocation.school_id == school_id,
            FeePaymentAllocation.installment_id == installment_id,
            FeePaymentAllocation.deleted_at.is_(None),
        )
        .scalar()
    )
    return inr_quantize(total or 0)


def list_installments(db: Session, school_id: int, structure_id: int) -> dict:
    _owned(db, FeeStructure, structure_id, school_id)
    rows = _active_installments(db, school_id, structure_id)
    items = []
    for row in rows:
        allocated = _installment_allocated(db, school_id, row.id)
        amount = inr_quantize(row.amount)
        items.append(
            {
                "id": row.id,
                "structure_id": row.structure_id,
                "name": row.name,
                "due_date": row.due_date.isoformat(),
                "amount": float(amount),
                "sort_order": row.sort_order,
                "allocated": float(allocated),
                "outstanding": float(inr_quantize(amount - allocated)),
            }
        )
    return {"items": items, "total": len(items)}


def set_structure_installments(
    db: Session, school_id: int, structure_id: int, items: list[dict]
) -> dict:
    structure = _owned(db, FeeStructure, structure_id, school_id)
    structure_total = _structure_total_dec(db, school_id, structure.id)
    validate_installment_sum(structure_total, items)

    existing = _active_installments(db, school_id, structure.id)
    for inst in existing:
        allocated = _installment_allocated(db, school_id, inst.id)
        if allocated > 0:
            raise AcademicError(
                409,
                "Cannot replace installments that already have successful payment allocations",
            )

    now = _now()
    for inst in existing:
        inst.deleted_at = now
        inst.updated_at = now

    for idx, raw in enumerate(items):
        name = str(raw.get("name") or "").strip()
        if not name:
            raise AcademicError(422, "installment name is required")
        due_raw = raw.get("due_date")
        if not due_raw:
            raise AcademicError(422, "installment due_date is required")
        if isinstance(due_raw, date) and not isinstance(due_raw, datetime):
            due = due_raw
        else:
            try:
                due = date.fromisoformat(str(due_raw)[:10])
            except ValueError as exc:
                raise AcademicError(422, "due_date must be YYYY-MM-DD") from exc
        amount = inr_quantize(raw.get("amount") or 0)
        sort_order = int(raw.get("sort_order") if raw.get("sort_order") is not None else idx)
        db.add(
            FeeInstallment(
                school_id=school_id,
                structure_id=structure.id,
                name=name,
                due_date=due,
                amount=float(amount),
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
        )
    _commit(db)
    return list_installments(db, school_id, structure.id)


def allocate_payment(db: Session, school_id: int, payment: FeePayment, structure_id: int) -> list[FeePaymentAllocation]:
    """Allocate a new success payment across unpaid installments (earliest due first)."""
    remaining = inr_quantize(payment.amount)
    if remaining <= 0:
        return []
    installments = _active_installments(db, school_id, structure_id)
    if not installments:
        return []
    now = _now()
    created: list[FeePaymentAllocation] = []
    for inst in installments:
        if remaining <= 0:
            break
        already = _installment_allocated(db, school_id, inst.id)
        due = inr_quantize(inr_quantize(inst.amount) - already)
        if due <= 0:
            continue
        take = due if due <= remaining else remaining
        row = FeePaymentAllocation(
            school_id=school_id,
            payment_id=payment.id,
            installment_id=inst.id,
            amount=float(take),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        created.append(row)
        remaining = inr_quantize(remaining - take)
    if remaining > 0:
        # Leftover (e.g. concession edge) stored as unallocated line.
        row = FeePaymentAllocation(
            school_id=school_id,
            payment_id=payment.id,
            installment_id=None,
            amount=float(remaining),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        created.append(row)
    return created


def get_payment_receipt(db: Session, school_id: int, payment_id: int) -> dict:
    payment = db.get(FeePayment, payment_id)
    if payment is None or payment.school_id != school_id:
        raise AcademicError(404, "Record not found")
    # Cancelled payments are soft-deleted but remain receivable for audit/receipt.
    if payment.deleted_at is not None and payment.cancelled_at is None:
        raise AcademicError(404, "Record not found")
    alloc_q = db.query(FeePaymentAllocation).filter(
        FeePaymentAllocation.school_id == school_id,
        FeePaymentAllocation.payment_id == payment.id,
    )
    if payment.cancelled_at is None:
        alloc_q = alloc_q.filter(FeePaymentAllocation.deleted_at.is_(None))
    allocations = alloc_q.order_by(FeePaymentAllocation.id.asc()).all()
    lines = []
    for a in allocations:
        inst_name = None
        if a.installment_id:
            inst = db.get(FeeInstallment, a.installment_id)
            inst_name = inst.name if inst else None
        lines.append(
            {
                "allocation_id": a.id,
                "installment_id": a.installment_id,
                "installment_name": inst_name,
                "amount": float(inr_quantize(a.amount)),
            }
        )
    student = db.get(Student, payment.student_id)
    student_user = db.get(User, student.user_id) if student else None
    student_name = ""
    if student_user:
        student_name = f"{student_user.first_name or ''} {student_user.last_name or ''}".strip()
    return {
        "id": payment.id,
        "receipt_no": payment.receipt_no,
        "student_id": payment.student_id,
        "student_name": student_name,
        "assignment_id": payment.assignment_id,
        "amount": float(inr_quantize(payment.amount)),
        "method": payment.method,
        "reference": payment.reference,
        "remarks": payment.remarks,
        "paid_on": payment.paid_on.isoformat() if payment.paid_on else None,
        "status": payment.status,
        "cancelled_at": payment.cancelled_at.isoformat() if payment.cancelled_at else None,
        "cancel_reason": payment.cancel_reason,
        "lines": lines,
    }


def render_fee_receipt_pdf(db: Session, school_id: int, payment_id: int) -> bytes:
    receipt = get_payment_receipt(db, school_id, payment_id)
    school = db.get(School, school_id)
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, (school.name if school else "School")[:80], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=14)
    pdf.cell(0, 8, "Fee Payment Receipt", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, f"Receipt: {receipt.get('receipt_no') or receipt['id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Student: {receipt.get('student_name') or receipt['student_id']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Paid on: {receipt.get('paid_on') or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Method: {receipt.get('method') or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Status: {receipt.get('status')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Amount: INR {receipt['amount']:.2f}", new_x="LMARGIN", new_y="NEXT")
    if receipt.get("lines"):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Allocations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        for line in receipt["lines"]:
            label = line.get("installment_name") or (
                f"Installment #{line['installment_id']}" if line.get("installment_id") else "Unallocated"
            )
            pdf.cell(0, 6, f"{label}: INR {line['amount']:.2f}", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def cancel_fee_payment(
    db: Session,
    school_id: int,
    payment_id: int,
    reason: str,
    actor: Any = None,
) -> dict:
    reason = str(reason or "").strip()
    if not reason:
        raise AcademicError(422, "reason is required")
    if len(reason) > 512:
        raise AcademicError(422, "reason must be at most 512 characters")
    payment = _owned(db, FeePayment, payment_id, school_id)
    if payment.status != "success" or payment.deleted_at is not None:
        raise AcademicError(422, "Only successful (non-cancelled) payments can be cancelled")
    now = _now()
    payment.status = "cancelled"
    payment.cancelled_at = now
    payment.cancel_reason = reason
    payment.deleted_at = now
    payment.updated_at = now
    for alloc in (
        db.query(FeePaymentAllocation)
        .filter(
            FeePaymentAllocation.school_id == school_id,
            FeePaymentAllocation.payment_id == payment.id,
            FeePaymentAllocation.deleted_at.is_(None),
        )
        .all()
    ):
        alloc.deleted_at = now
        alloc.updated_at = now

    meta = {"reason": reason, "amount": float(inr_quantize(payment.amount))}
    db.add(
        AuditLog(
            actor_id=str(actor.id) if actor is not None else None,
            actor_email=getattr(actor, "email", None) if actor is not None else None,
            action="fee_payment.cancel",
            entity_type="fee_payment",
            entity_id=str(payment.id),
            school_id=school_id,
            metadata_json=json.dumps(meta),
            created_at=now,
        )
    )
    _commit(db)
    return get_payment_receipt(db, school_id, payment.id)


def fee_collection_report(
    db: Session,
    school_id: int,
    from_date: date,
    to_date: date,
    class_id: int | None = None,
) -> dict:
    if to_date < from_date:
        raise AcademicError(422, "to_date must be on or after from_date")
    q = db.query(FeePayment).filter(
        FeePayment.school_id == school_id,
        FeePayment.deleted_at.is_(None),
        FeePayment.status == "success",
        FeePayment.paid_on >= from_date,
        FeePayment.paid_on <= to_date,
    )
    if class_id is not None:
        q = (
            q.join(FeeAssignment, FeeAssignment.id == FeePayment.assignment_id)
            .join(FeeStructure, FeeStructure.id == FeeAssignment.structure_id)
            .filter(FeeStructure.class_id == class_id)
        )
    rows = q.order_by(FeePayment.paid_on.asc(), FeePayment.id.asc()).all()
    total_collected = Decimal("0.00")
    by_method: dict[str, Decimal] = {}
    items = []
    for p in rows:
        amt = inr_quantize(p.amount)
        total_collected += amt
        method = p.method or "cash"
        by_method[method] = inr_quantize(by_method.get(method, Decimal("0")) + amt)
        items.append(
            {
                "id": p.id,
                "receipt_no": p.receipt_no,
                "student_id": p.student_id,
                "amount": float(amt),
                "method": method,
                "paid_on": p.paid_on.isoformat(),
            }
        )
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "class_id": class_id,
        "payment_count": len(items),
        "total_collected": float(inr_quantize(total_collected)),
        "by_method": {k: float(v) for k, v in by_method.items()},
        "items": items,
    }


def _concession_amount(db: Session, school_id: int, student_id: int, structure_id: int, total: Decimal) -> Decimal:
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
        return Decimal("0.00")
    if conc.kind == "percent":
        return inr_quantize(total * inr_quantize(conc.value) / Decimal("100"))
    return min(inr_quantize(conc.value), total)


def _paid_success(db: Session, school_id: int, assignment_id: int) -> Decimal:
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
    return inr_quantize(total or 0)


def student_fee_balance(db: Session, school_id: int, student_id: int) -> dict:
    assignments = (
        db.query(FeeAssignment)
        .filter(
            FeeAssignment.school_id == school_id,
            FeeAssignment.student_id == student_id,
            FeeAssignment.deleted_at.is_(None),
        )
        .all()
    )
    items = []
    total_payable = Decimal("0.00")
    total_paid = Decimal("0.00")
    for a in assignments:
        structure_total = _structure_total_dec(db, school_id, a.structure_id)
        concession = _concession_amount(db, school_id, student_id, a.structure_id, structure_total)
        payable = inr_quantize(max(structure_total - concession, Decimal("0")))
        paid = _paid_success(db, school_id, a.id)
        outstanding = inr_quantize(payable - paid)
        installments = []
        for inst in _active_installments(db, school_id, a.structure_id):
            allocated = _installment_allocated(db, school_id, inst.id)
            # Per-assignment installment outstanding is approximate when shared;
            # report installment face vs global allocations for transparency.
            installments.append(
                {
                    "id": inst.id,
                    "name": inst.name,
                    "due_date": inst.due_date.isoformat(),
                    "amount": float(inr_quantize(inst.amount)),
                    "allocated": float(allocated),
                    "outstanding": float(inr_quantize(inr_quantize(inst.amount) - allocated)),
                }
            )
        items.append(
            {
                "assignment_id": a.id,
                "structure_id": a.structure_id,
                "payable": float(payable),
                "paid": float(paid),
                "outstanding": float(outstanding),
                "installments": installments,
            }
        )
        total_payable += payable
        total_paid += paid
    return {
        "student_id": student_id,
        "payable": float(inr_quantize(total_payable)),
        "paid": float(inr_quantize(total_paid)),
        "outstanding": float(inr_quantize(total_payable - total_paid)),
        "assignments": items,
    }


def _assert_student_or_parent(db: Session, school_id: int, user: User, student_id: int) -> None:
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
        return
    children = _guardian_children(db, user, school_id)
    if student.id not in {c.id for c in children}:
        raise AcademicError(404, "Record not found")


def portal_student_fee_balance(db: Session, school_id: int, user: User) -> dict:
    student = (
        db.query(Student)
        .filter(Student.user_id == user.id, Student.school_id == school_id, Student.deleted_at.is_(None))
        .first()
    )
    if student is None:
        raise AcademicError(404, "Student profile not found")
    return student_fee_balance(db, school_id, student.id)


def portal_child_fee_balance(db: Session, school_id: int, user: User, student_id: int) -> dict:
    _assert_student_or_parent(db, school_id, user, student_id)
    return student_fee_balance(db, school_id, student_id)


def portal_list_payments(db: Session, school_id: int, user: User, student_id: int) -> dict:
    _assert_student_or_parent(db, school_id, user, student_id)
    rows = (
        db.query(FeePayment)
        .filter(
            FeePayment.school_id == school_id,
            FeePayment.student_id == student_id,
            FeePayment.deleted_at.is_(None),
            FeePayment.status == "success",
        )
        .order_by(FeePayment.id.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": p.id,
                "receipt_no": p.receipt_no,
                "amount": float(inr_quantize(p.amount)),
                "method": p.method,
                "paid_on": p.paid_on.isoformat() if p.paid_on else None,
                "status": p.status,
            }
            for p in rows
        ],
        "total": len(rows),
    }


def portal_payment_receipt_pdf(
    db: Session, school_id: int, user: User, payment_id: int
) -> bytes:
    payment = _owned(db, FeePayment, payment_id, school_id)
    _assert_student_or_parent(db, school_id, user, payment.student_id)
    if payment.status != "success" or payment.deleted_at is not None:
        raise AcademicError(404, "Record not found")
    return render_fee_receipt_pdf(db, school_id, payment_id)
