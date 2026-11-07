"""Cross-branch IDOR / isolation offline unit tests (no Neon).

Run::
    pytest --noconftest -p no:cacheprovider tests/v1/test_school_branch_idor_offline.py
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.v1 import school_branches as branches
from app.services.v1.school_branches import BranchContext, BranchError
from app.services.v1.school_academics import AcademicError
from app.services.v1 import school_people as people
from app.services.v1 import school_offline_exams as offline
from app.services.v1 import school_teachers as teachers
from app.services.v1 import school_timetable as timetable
from app.services.v1 import school_homework as homework
from app.services.v1 import school_academics as academics
from app.services.v1 import school_academic_mgmt as fee_mgmt
from app.services.v1 import school_erp_fees as erp_fees
from app.services.v1 import person_documents as docs
from datetime import date


def _ctx(branch_id: int, allowed=(1, 2), full=True) -> BranchContext:
    return BranchContext(
        school_id=10,
        branch_id=branch_id,
        allowed_branch_ids=tuple(allowed),
        is_full_school_admin=full,
    )


def _active_exam_respecting_branch(exam):
    def _fn(db, school_id, exam_id, *, branch_id=None):
        offline._assert_branch_match(exam, branch_id)
        return exam

    return _fn


def test_assert_same_branch_blocks_other_branch_and_other_school():
    ctx = _ctx(1)
    branches.assert_same_branch(10, 1, ctx)
    with pytest.raises(BranchError) as exc:
        branches.assert_same_branch(10, 2, ctx)
    assert exc.value.status_code == 404
    with pytest.raises(BranchError):
        branches.assert_same_branch(99, 1, ctx)


def test_branch_admin_denied_unassigned_branch():
    user = SimpleNamespace(id=uuid.uuid4(), school_id=10, role="school_admin")
    db = MagicMock()
    other = SimpleNamespace(id=2, school_id=10, deleted_at=None, status=1, is_default=0)
    db.get.return_value = other
    original = branches.allowed_branch_ids_for_user
    branches.allowed_branch_ids_for_user = lambda *_a, **_k: ([1], False)  # type: ignore
    try:
        with pytest.raises(BranchError) as exc:
            branches.resolve_branch_context(db, user, header_branch_id=2)
        assert exc.value.status_code == 403
    finally:
        branches.allowed_branch_ids_for_user = original  # type: ignore


def test_owned_student_rejects_cross_branch(monkeypatch):
    student = SimpleNamespace(
        id=5, school_id=10, branch_id=2, user_id=9, deleted_at=None
    )
    user = SimpleNamespace(id=9, school_id=10, deleted_at=None)

    def fake_owned(db, model, row_id, school_id):
        return student

    monkeypatch.setattr(people, "_owned", fake_owned)
    monkeypatch.setattr(people, "db", None, raising=False)

    class FakeDB:
        def get(self, model, pk):
            return user

    with pytest.raises(AcademicError) as exc:
        people._owned_student(FakeDB(), 10, 5, branch_id=1)
    assert exc.value.status_code == 404


def test_get_exam_rejects_cross_branch(monkeypatch):
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.get_exam(MagicMock(), 10, 3, branch_id=1)
    assert exc.value.status_code == 404


def test_get_teacher_rejects_cross_branch(monkeypatch):
    user = SimpleNamespace(id=7, school_id=10, deleted_at=None)
    staff = SimpleNamespace(id=8, school_id=10, branch_id=2, user_id=7)

    monkeypatch.setattr(teachers, "_owned_teacher", lambda *a, **k: (user, staff))
    with pytest.raises(AcademicError) as exc:
        teachers.get_teacher(MagicMock(), 10, 7, branch_id=1)
    assert exc.value.status_code == 404


def test_update_exam_rejects_cross_branch(monkeypatch):
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None, publish=0)

    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.update_exam(MagicMock(), 10, 3, {"name": "X"}, branch_id=1)
    assert exc.value.status_code == 404


def test_timetable_get_entry_rejects_cross_branch(monkeypatch):
    entry = SimpleNamespace(id=9, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(timetable, "_owned_entry", lambda *a, **k: entry)
    with pytest.raises(AcademicError) as exc:
        timetable.get_entry(MagicMock(), 10, 9, branch_id=1)
    assert exc.value.status_code == 404


def test_schedule_get_rejects_cross_branch(monkeypatch):
    schedule = SimpleNamespace(id=4, school_id=10, branch_id=2, exam_id=3, deleted_at=None)
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(offline, "_owned", lambda db, model, row_id, school_id: schedule)
    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.get_schedule(MagicMock(), 10, 4, branch_id=1)
    assert exc.value.status_code == 404


def test_schedule_parent_child_branch_mismatch_rejected(monkeypatch):
    schedule = SimpleNamespace(id=4, school_id=10, branch_id=1, exam_id=3, deleted_at=None)
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(offline, "_owned", lambda db, model, row_id, school_id: schedule)
    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.get_schedule(MagicMock(), 10, 4, branch_id=1)
    assert exc.value.status_code == 404


def test_upsert_mark_rejects_cross_branch_schedule(monkeypatch):
    schedule = SimpleNamespace(
        id=4,
        school_id=10,
        branch_id=2,
        exam_id=3,
        deleted_at=None,
        class_section_id=1,
        session_year_id=1,
        subject_id=1,
        teacher_user_id=None,
        max_marks=100,
    )
    exam = SimpleNamespace(
        id=3, school_id=10, branch_id=2, deleted_at=None, publish=0, results_processed_at=None
    )

    monkeypatch.setattr(offline, "_owned", lambda db, model, row_id, school_id: schedule)
    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.upsert_mark(
            MagicMock(),
            10,
            4,
            {"student_id": 1, "status": "present", "marks_obtained": 10},
            actor_v1_user_id="u1",
            branch_id=1,
        )
    assert exc.value.status_code == 404


def test_mark_audits_reject_cross_branch(monkeypatch):
    mark = SimpleNamespace(id=9, school_id=10, branch_id=2, exam_id=3, deleted_at=None)
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(offline, "_owned", lambda db, model, row_id, school_id: mark)
    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.list_mark_audits(MagicMock(), 10, 9, branch_id=1)
    assert exc.value.status_code == 404


def test_teacher_timetable_read_rejects_cross_branch_teacher(monkeypatch):
    user = SimpleNamespace(id=7, school_id=10, status=1, deleted_at=None)
    staff = SimpleNamespace(id=8, school_id=10, branch_id=2, user_id=7)

    monkeypatch.setattr(
        "app.services.v1.school_teachers._owned_teacher",
        lambda *a, **k: (user, staff),
    )
    with pytest.raises(AcademicError) as exc:
        timetable._require_timetable_teacher(MagicMock(), 10, 7, branch_id=1)
    assert exc.value.status_code == 404


def test_homework_get_rejects_cross_branch(monkeypatch):
    hw = SimpleNamespace(id=5, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(homework, "_owned", lambda db, model, row_id, school_id: hw)
    with pytest.raises(AcademicError) as exc:
        homework.get_homework(MagicMock(), 10, 5, branch_id=1)
    assert exc.value.status_code == 404


def test_homework_submission_rejects_when_parent_other_branch(monkeypatch):
    sub = SimpleNamespace(id=11, school_id=10, homework_id=5, deleted_at=None)
    hw = SimpleNamespace(id=5, school_id=10, branch_id=2, deleted_at=None)

    def _active(db, school_id, homework_id, *, branch_id=None):
        if branch_id is not None and hw.branch_id not in (None, branch_id):
            raise AcademicError(404, "Record not found")
        return hw

    monkeypatch.setattr(homework, "_owned", lambda db, model, row_id, school_id: sub)
    monkeypatch.setattr(homework, "_active_homework", _active)
    with pytest.raises(AcademicError) as exc:
        homework.get_submission(MagicMock(), 10, 11, branch_id=1)
    assert exc.value.status_code == 404


def test_teacher_assignment_get_rejects_cross_branch(monkeypatch):
    row = SimpleNamespace(id=6, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(academics, "_owned", lambda db, model, row_id, school_id: row)
    with pytest.raises(AcademicError) as exc:
        academics.get_teacher_assignment(MagicMock(), 10, 6, branch_id=1)
    assert exc.value.status_code == 404


def test_process_results_rejects_cross_branch(monkeypatch):
    exam = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None, class_section_id=1)

    monkeypatch.setattr(offline, "_active_exam", _active_exam_respecting_branch(exam))
    with pytest.raises(AcademicError) as exc:
        offline.process_results(MagicMock(), 10, 3, branch_id=1)
    assert exc.value.status_code == 404


def test_student_status_rejects_cross_branch(monkeypatch):
    student = SimpleNamespace(id=5, school_id=10, branch_id=2, user_id=9, deleted_at=None)
    user = SimpleNamespace(id=9, school_id=10, deleted_at=None)

    monkeypatch.setattr(people, "_owned_student", lambda *a, **k: (student, user))
    # Force real branch check path via _owned_student kw
    def _owned(db, school_id, student_id, *, branch_id=None):
        if branch_id is not None and student.branch_id not in (None, branch_id):
            raise AcademicError(404, "Record not found")
        return student, user

    monkeypatch.setattr(people, "_owned_student", _owned)
    with pytest.raises(AcademicError) as exc:
        people.update_student_status(MagicMock(), 10, 5, 0, branch_id=1)
    assert exc.value.status_code == 404


def test_student_guardian_link_rejects_cross_branch(monkeypatch):
    student = SimpleNamespace(id=5, school_id=10, branch_id=2, user_id=9, deleted_at=None)
    user = SimpleNamespace(id=9, school_id=10, deleted_at=None)

    def _owned(db, school_id, student_id, *, branch_id=None):
        if branch_id is not None and student.branch_id not in (None, branch_id):
            raise AcademicError(404, "Record not found")
        return student, user

    monkeypatch.setattr(people, "_owned_student", _owned)
    with pytest.raises(AcademicError) as exc:
        people.link_guardian(MagicMock(), 10, 5, {"parent_id": 1}, branch_id=1)
    assert exc.value.status_code == 404


def test_teacher_update_rejects_cross_branch(monkeypatch):
    user = SimpleNamespace(id=7, school_id=10, deleted_at=None, email="a@b.com")
    staff = SimpleNamespace(id=8, school_id=10, branch_id=2, user_id=7)

    monkeypatch.setattr(teachers, "_owned_teacher", lambda *a, **k: (user, staff))
    with pytest.raises(AcademicError) as exc:
        teachers.update_teacher(MagicMock(), 10, 7, {"first_name": "X"}, branch_id=1)
    assert exc.value.status_code == 404


def test_teacher_status_rejects_cross_branch(monkeypatch):
    user = SimpleNamespace(id=7, school_id=10, deleted_at=None)
    staff = SimpleNamespace(id=8, school_id=10, branch_id=2, user_id=7)

    monkeypatch.setattr(teachers, "_owned_teacher", lambda *a, **k: (user, staff))
    with pytest.raises(AcademicError) as exc:
        teachers.update_teacher_status(MagicMock(), 10, 7, 0, branch_id=1)
    assert exc.value.status_code == 404


def test_teacher_document_list_rejects_cross_branch(monkeypatch):
    user = SimpleNamespace(id=7, school_id=10, deleted_at=None)
    staff = SimpleNamespace(id=8, school_id=10, branch_id=2, user_id=7)

    monkeypatch.setattr(docs, "_owned_teacher", lambda *a, **k: (user, staff))
    with pytest.raises(AcademicError) as exc:
        docs.list_documents(
            MagicMock(), 10, "teacher", 7, page=1, page_size=20, category=None, branch_id=1
        )
    assert exc.value.status_code == 404


def test_fee_structure_update_rejects_cross_branch(monkeypatch):
    row = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(fee_mgmt, "_owned", lambda db, model, row_id, school_id: row)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.update_fee_structure(MagicMock(), 10, 3, {"name": "X"}, branch_id=1)
    assert exc.value.status_code == 404


def test_fee_structure_delete_rejects_cross_branch(monkeypatch):
    row = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(fee_mgmt, "_owned", lambda db, model, row_id, school_id: row)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.soft_delete_fee_structure(MagicMock(), 10, 3, branch_id=1)
    assert exc.value.status_code == 404


def test_fee_assignment_delete_rejects_cross_branch(monkeypatch):
    row = SimpleNamespace(id=9, school_id=10, branch_id=2, deleted_at=None)

    monkeypatch.setattr(fee_mgmt, "_owned", lambda db, model, row_id, school_id: row)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.soft_delete_fee_assignment(MagicMock(), 10, 9, branch_id=1)
    assert exc.value.status_code == 404


def test_same_branch_teacher_update_allowed(monkeypatch):
    user = SimpleNamespace(
        id=7,
        school_id=10,
        deleted_at=None,
        email="a@b.com",
        first_name="A",
        last_name="B",
        mobile=None,
        gender=None,
        dob=None,
        current_address=None,
        permanent_address=None,
        country_code=None,
        image=None,
    )
    staff = SimpleNamespace(
        id=8,
        school_id=10,
        branch_id=1,
        user_id=7,
        qualification=None,
        salary=0,
        employee_id="T1",
        joining_date=None,
        employment_status="active",
        department=None,
        designation=None,
    )

    monkeypatch.setattr(teachers, "_owned_teacher", lambda *a, **k: (user, staff))
    monkeypatch.setattr(teachers, "_assignment_count", lambda *a, **k: 0)
    monkeypatch.setattr(teachers, "_commit", lambda db: None)
    monkeypatch.setattr(teachers, "_teacher_item", lambda *a, **k: {"id": 7, "ok": True})
    out = teachers.update_teacher(MagicMock(), 10, 7, {"first_name": "Z"}, branch_id=1)
    assert out["ok"] is True
    assert user.first_name == "Z"


def test_full_school_admin_may_select_assigned_branch():
    ctx = _ctx(1, allowed=(1, 2), full=True)
    branches.assert_same_branch(10, 1, ctx)
    branches.assert_same_branch(10, 1, _ctx(1, allowed=(1, 2), full=True))


def test_branch2_ops_do_not_expand_allowed_set_for_branch_admin():
    """Branch admin allowed set stays assigned-only; cannot open Branch 1."""
    user = SimpleNamespace(id=uuid.uuid4(), school_id=10, role="school_admin")
    db = MagicMock()
    original = branches.allowed_branch_ids_for_user
    branches.allowed_branch_ids_for_user = lambda *_a, **_k: ([2], False)  # type: ignore
    try:
        b1 = SimpleNamespace(id=1, school_id=10, deleted_at=None, status=1, is_default=1)
        db.get.return_value = b1
        with pytest.raises(BranchError) as exc:
            branches.resolve_branch_context(db, user, header_branch_id=1)
        assert exc.value.status_code == 403
        b2 = SimpleNamespace(id=2, school_id=10, deleted_at=None, status=1, is_default=0)
        db.get.return_value = b2
        ctx = branches.resolve_branch_context(db, user, header_branch_id=2)
        assert ctx.branch_id == 2
        assert ctx.allowed_branch_ids == (2,)
    finally:
        branches.allowed_branch_ids_for_user = original  # type: ignore


def test_orm_inventory_branch_id_parity():
    import importlib.util

    from app.models.tables import Base, TeacherAssignment, ClassTimetableEntry, Student

    spec = importlib.util.spec_from_file_location(
        "m0046", "alembic/versions/20261105_0046_school_branches.py"
    )
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    missing = [
        n
        for n in m.BRANCH_SCOPED_TABLES
        if n in Base.metadata.tables and "branch_id" not in Base.metadata.tables[n].c
    ]
    assert missing == [], missing
    assert "branch_id" in TeacherAssignment.__table__.c
    assert "branch_id" in ClassTimetableEntry.__table__.c
    idx_names = {idx.name for idx in Student.__table__.indexes}
    assert "uq_students_school_branch_admission_no_active" in idx_names


# ---- Residual API gap-closure (fees leftovers + reports) ----


def test_installments_get_rejects_cross_branch(monkeypatch):
    structure = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)
    monkeypatch.setattr(erp_fees, "_owned", lambda db, model, row_id, school_id: structure)
    with pytest.raises(AcademicError) as exc:
        erp_fees.list_installments(MagicMock(), 10, 3, branch_id=1)
    assert exc.value.status_code == 404


def test_installments_put_rejects_cross_branch(monkeypatch):
    structure = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)
    monkeypatch.setattr(erp_fees, "_owned", lambda db, model, row_id, school_id: structure)
    with pytest.raises(AcademicError) as exc:
        erp_fees.set_structure_installments(
            MagicMock(),
            10,
            3,
            [{"name": "T1", "due_date": "2026-01-01", "amount": 100}],
            branch_id=1,
        )
    assert exc.value.status_code == 404


def test_concession_list_filters_by_branch(monkeypatch):
    seen = {}

    def fake_list(db, model, school_id, *, page=1, page_size=20, filters=None, **kwargs):
        seen["filters"] = filters
        q = MagicMock()
        if filters:
            filters(q)
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    monkeypatch.setattr(fee_mgmt, "_list_active", fake_list)
    fee_mgmt.list_fee_concessions(MagicMock(), 10, page=1, page_size=20, branch_id=1)
    assert seen["filters"] is not None


def test_concession_create_rejects_cross_branch_student(monkeypatch):
    student = SimpleNamespace(id=5, school_id=10, branch_id=2, deleted_at=None)
    structure = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    def _owned(db, model, row_id, school_id):
        name = getattr(model, "__name__", str(model))
        if "Student" in name:
            return student
        return structure

    monkeypatch.setattr(fee_mgmt, "_owned", _owned)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.create_fee_concession(
            MagicMock(),
            10,
            {
                "student_id": 5,
                "structure_id": 3,
                "kind": "amount",
                "value": 10,
                "reason": "merit",
            },
            branch_id=1,
        )
    assert exc.value.status_code == 404


def test_concession_create_rejects_parent_child_branch_mismatch(monkeypatch):
    student = SimpleNamespace(id=5, school_id=10, branch_id=1, deleted_at=None)
    structure = SimpleNamespace(id=3, school_id=10, branch_id=2, deleted_at=None)

    def _owned(db, model, row_id, school_id):
        name = getattr(model, "__name__", str(model))
        if "Student" in name:
            return student
        return structure

    monkeypatch.setattr(fee_mgmt, "_owned", _owned)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.create_fee_concession(
            MagicMock(),
            10,
            {
                "student_id": 5,
                "structure_id": 3,
                "kind": "percent",
                "value": 10,
                "reason": "merit",
            },
            branch_id=1,
        )
    assert exc.value.status_code == 404


def test_concession_delete_rejects_cross_branch(monkeypatch):
    row = SimpleNamespace(id=9, school_id=10, branch_id=2, deleted_at=None)
    monkeypatch.setattr(fee_mgmt, "_owned", lambda db, model, row_id, school_id: row)
    with pytest.raises(AcademicError) as exc:
        fee_mgmt.soft_delete_fee_concession(MagicMock(), 10, 9, branch_id=1)
    assert exc.value.status_code == 404


def test_receipt_rejects_cross_branch(monkeypatch):
    payment = SimpleNamespace(
        id=11,
        school_id=10,
        branch_id=2,
        deleted_at=None,
        cancelled_at=None,
        student_id=1,
        assignment_id=1,
        amount=100,
        method="cash",
        reference=None,
        remarks=None,
        paid_on=date(2026, 1, 1),
        status="success",
        receipt_no="R1",
        cancel_reason=None,
    )
    db = MagicMock()
    db.get.return_value = payment
    with pytest.raises(AcademicError) as exc:
        erp_fees.get_payment_receipt(db, 10, 11, branch_id=1)
    assert exc.value.status_code == 404


def test_receipt_pdf_rejects_cross_branch(monkeypatch):
    monkeypatch.setattr(
        erp_fees,
        "get_payment_receipt",
        lambda *a, **k: (_ for _ in ()).throw(AcademicError(404, "Record not found")),
    )
    with pytest.raises(AcademicError) as exc:
        erp_fees.render_fee_receipt_pdf(MagicMock(), 10, 11, branch_id=1)
    assert exc.value.status_code == 404


def test_cancel_payment_rejects_cross_branch(monkeypatch):
    payment = SimpleNamespace(
        id=11, school_id=10, branch_id=2, deleted_at=None, status="success"
    )
    monkeypatch.setattr(erp_fees, "_owned", lambda db, model, row_id, school_id: payment)
    with pytest.raises(AcademicError) as exc:
        erp_fees.cancel_fee_payment(
            MagicMock(), 10, 11, "duplicate", actor=None, branch_id=1
        )
    assert exc.value.status_code == 404


def test_same_branch_receipt_allowed(monkeypatch):
    payment = SimpleNamespace(
        id=11,
        school_id=10,
        branch_id=1,
        deleted_at=None,
        cancelled_at=None,
        student_id=1,
        assignment_id=1,
        amount=100,
        method="cash",
        reference=None,
        remarks=None,
        paid_on=date(2026, 1, 1),
        status="success",
        receipt_no="R1",
        cancel_reason=None,
    )
    db = MagicMock()
    db.get.side_effect = lambda model, pk: payment if pk == 11 else None
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    out = erp_fees.get_payment_receipt(db, 10, 11, branch_id=1)
    assert out["id"] == 11
    assert out["amount"] == 100.0


def test_collection_report_branch_filter_applied():
    """Direct unit: branch filter uses FeePayment.branch_id equality."""
    calls = {"filters": []}

    class _FakeQuery:
        def filter(self, *args):
            calls["filters"].extend(args)
            return self

        def join(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return []

    db = MagicMock()
    db.query.return_value = _FakeQuery()
    out = erp_fees.fee_collection_report(
        db, 10, date(2026, 1, 1), date(2026, 1, 31), branch_id=1
    )
    assert out["payment_count"] == 0
    assert any("branch_id" in str(f) for f in calls["filters"])


def test_reports_and_dashboard_pass_branch_filter(monkeypatch):
    captured = {}

    def _stub_filter(branch_id, allowed_branch_ids):
        return [branch_id] if branch_id not in (None, 0) else list(allowed_branch_ids or [])

    monkeypatch.setattr(fee_mgmt, "_branch_ids_filter", _stub_filter)

    class _Agg:
        def __init__(self):
            self.filters = []

        def filter(self, *a):
            self.filters.extend(a)
            return self

        def group_by(self, *a):
            return self

        def scalar(self):
            return 0

        def all(self):
            return []

    def query(*models):
        captured.setdefault("queries", []).append(models)
        return _Agg()

    db = MagicMock()
    db.query.side_effect = query

    for fn in (
        fee_mgmt.report_teachers,
        fee_mgmt.report_staff,
        fee_mgmt.report_exams,
        fee_mgmt.report_expenses,
        fee_mgmt.report_income,
        fee_mgmt.incomes_dashboard,
    ):
        out = fn(db, 10, branch_id=1, allowed_branch_ids=[1, 2])
        assert out.get("branch_id") == 1
        assert out.get("consolidated") is False


def test_consolidated_report_flags_full_school_admin(monkeypatch):
    monkeypatch.setattr(fee_mgmt, "_branch_ids_filter", lambda bid, allowed: list(allowed or []))

    class _Agg:
        def filter(self, *a):
            return self

        def group_by(self, *a):
            return self

        def scalar(self):
            return 0

        def all(self):
            return []

    db = MagicMock()
    db.query.return_value = _Agg()
    out = fee_mgmt.report_teachers(db, 10, branch_id=None, allowed_branch_ids=[1, 2])
    assert out["consolidated"] is True
    assert out["branch_id"] is None


def test_branch_admin_denied_unassigned_still_enforced():
    """Regression: unresolved unassigned branch stays 403 via resolve_branch_context."""
    user = SimpleNamespace(id=uuid.uuid4(), school_id=10, role="school_admin")
    db = MagicMock()
    original = branches.allowed_branch_ids_for_user
    branches.allowed_branch_ids_for_user = lambda *_a, **_k: ([2], False)  # type: ignore
    try:
        db.get.return_value = SimpleNamespace(
            id=1, school_id=10, deleted_at=None, status=1, is_default=1
        )
        with pytest.raises(BranchError) as exc:
            branches.resolve_branch_context(db, user, header_branch_id=1)
        assert exc.value.status_code == 403
    finally:
        branches.allowed_branch_ids_for_user = original  # type: ignore
