"""Fee assignment, concessions, installments and public enquiry (no external DB).

Service tests run on in-memory SQLite with the real fee tables, so persisted rows are checked,
not mocks. PostgreSQL-only behaviour (row locks, partial-index DDL) is covered by the
tests/v1 suite on the isolated test database; see the QA report.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import tables as t
from app.services.v1 import school_academic_mgmt as mgmt
from app.services.v1 import school_erp_fees as erp
from app.services.v1.school_academics import AcademicError

SCHOOL = 1
OTHER_SCHOOL = 2
TABLES = [
    t.SessionYear, t.SchoolClass, t.ClassSection, t.Student, t.FeeType, t.FeeStructure,
    t.FeeStructureAmount, t.FeeAssignment, t.FeeConcession, t.FeePayment, t.FeeInstallment,
    t.FeePaymentAllocation, t.AuditLog, t.User,
]


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fns(conn, _rec):  # PostgreSQL functions used by index expressions
        conn.create_function("btrim", 1, lambda s: s.strip() if s is not None else None, deterministic=True)

    t.Base.metadata.create_all(engine, tables=[m.__table__ for m in TABLES])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    now = datetime(2026, 11, 13, 9, 0)
    session.add_all(
        [
            t.SessionYear(id=1, name="2026-27", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), school_id=SCHOOL),
            t.SchoolClass(id=5, name="Class 5", medium_id=1, school_id=SCHOOL),
            t.SchoolClass(id=6, name="Class 6", medium_id=1, school_id=SCHOOL),
            t.ClassSection(id=50, class_id=5, section_id=1, medium_id=1, school_id=SCHOOL),
            t.ClassSection(id=51, class_id=5, section_id=2, medium_id=1, school_id=SCHOOL),
            t.ClassSection(id=60, class_id=6, section_id=1, medium_id=1, school_id=SCHOOL),
            t.FeeType(id=1, school_id=SCHOOL, name="Tuition"),
            t.FeeType(id=2, school_id=SCHOOL, name="Transport"),
        ]
    )

    def student(sid, section, status="active", session_year=1, school=SCHOOL, deleted=None):
        return t.Student(
            id=sid, user_id=sid, class_section_id=section, admission_no=f"A{sid}",
            admission_date=date(2026, 4, 1), school_id=school, guardian_id=1,
            session_year_id=session_year, enrollment_status=status, deleted_at=deleted,
        )

    session.add_all(
        [
            student(101, 50),                      # class 5 / A, active
            student(102, 51, status="admitted"),   # class 5 / B, admitted
            student(103, 50, status="inactive"),   # excluded
            student(104, 50, status="transferred"),  # excluded
            student(105, 50, deleted=now),         # excluded (deleted)
            student(106, 50, session_year=2),      # other session: excluded
            student(107, 60),                      # class 6: excluded
            student(108, 50, school=OTHER_SCHOOL),  # other school: excluded
        ]
    )
    session.commit()
    yield session
    session.close()


def _structure(db, *, amounts=((1, "1200"),), class_id=5, installments=None, status=1):
    body = {
        "name": f"Fees {class_id}",
        "session_year_id": 1,
        "class_id": class_id,
        "status": status,
        "amounts": [{"fee_type_id": f, "amount": a} for f, a in amounts],
    }
    if installments is not None:
        body["installments"] = installments
    return mgmt.create_fee_structure(db, SCHOOL, body)


def _inst(*amounts, names=None):
    names = names or [f"Installment {i + 1}" for i in range(len(amounts))]
    return [
        {"name": n, "due_date": (date(2026, 4, 1) + timedelta(days=30 * i)).isoformat(), "amount": a}
        for i, (n, a) in enumerate(zip(names, amounts))
    ]


def _assignment(db, structure_id, student_id):
    return (
        db.query(t.FeeAssignment)
        .filter_by(structure_id=structure_id, student_id=student_id, deleted_at=None)
        .one()
    )


def _pay(db, assignment_id, amount, **extra):
    return mgmt.collect_fee(db, SCHOOL, {"assignment_id": assignment_id, "amount": amount, **extra})


# ---------------------------------------------------------------- A. class assignment


def test_class_structure_assigns_only_enrolled_students_of_that_class(db):
    item = _structure(db)
    assert item["class_assignment"] == {"eligible_students": 2, "created": 2, "already_assigned": 0}
    rows = db.query(t.FeeAssignment).filter_by(structure_id=item["id"]).all()
    assert sorted(r.student_id for r in rows) == [101, 102]
    assert all(r.school_id == SCHOOL for r in rows)


def test_class_assignment_is_idempotent_and_picks_up_new_admissions(db):
    item = _structure(db)
    again = mgmt.assign_structure_to_class(db, SCHOOL, item["id"])
    assert again["created"] == 0 and again["already_assigned"] == 2
    db.add(t.Student(id=109, user_id=109, class_section_id=51, admission_no="A109",
                     admission_date=date(2026, 6, 1), school_id=SCHOOL, guardian_id=1,
                     session_year_id=1, enrollment_status="admitted"))
    db.commit()
    later = mgmt.assign_structure_to_class(db, SCHOOL, item["id"])
    assert later == {"structure_id": item["id"], "class_id": 5, "eligible_students": 3,
                     "created": 1, "already_assigned": 2}
    assert db.query(t.FeeAssignment).filter_by(structure_id=item["id"]).count() == 3


def test_structure_without_class_or_inactive_creates_no_assignments(db):
    no_class = _structure(db, class_id=None)
    inactive = _structure(db, status=0)
    assert "class_assignment" not in no_class and "class_assignment" not in inactive
    assert db.query(t.FeeAssignment).count() == 0
    with pytest.raises(AcademicError) as exc:
        mgmt.assign_structure_to_class(db, SCHOOL, no_class["id"])
    assert exc.value.status_code == 422
    with pytest.raises(AcademicError) as exc:
        mgmt.assign_structure_to_class(db, SCHOOL, inactive["id"])
    assert exc.value.status_code == 422


def test_class_assignment_other_school_structure_is_404(db):
    item = _structure(db)
    with pytest.raises(AcademicError) as exc:
        mgmt.assign_structure_to_class(db, OTHER_SCHOOL, item["id"])
    assert exc.value.status_code == 404


def test_concurrent_class_assignment_never_duplicates(db):
    """A second run racing the first hits the unique index, retries and creates nothing."""
    item = _structure(db, class_id=None)
    db.query(t.FeeStructure).filter_by(id=item["id"]).update({"class_id": 5})
    db.commit()
    real = mgmt._assign_structure_to_class
    calls = {"n": 0}

    def racing(session, school_id, structure, *, branch_id):
        calls["n"] += 1
        if calls["n"] == 1:  # another request commits the same assignments first
            other = sessionmaker(bind=session.get_bind())()
            for sid in (101, 102):
                other.add(t.FeeAssignment(school_id=SCHOOL, structure_id=structure.id, student_id=sid))
            other.commit()
            other.close()
            # this run still believes nobody is assigned
            for sid in (101, 102):
                session.add(t.FeeAssignment(school_id=SCHOOL, structure_id=structure.id, student_id=sid))
            return {"eligible_students": 2, "created": 2, "already_assigned": 0}
        return real(session, school_id, structure, branch_id=branch_id)

    mgmt._assign_structure_to_class = racing
    try:
        result = mgmt.assign_structure_to_class(db, SCHOOL, item["id"])
    finally:
        mgmt._assign_structure_to_class = real
    assert calls["n"] == 2 and result["created"] == 0 and result["already_assigned"] == 2
    assert db.query(t.FeeAssignment).filter_by(structure_id=item["id"], deleted_at=None).count() == 2


# ---------------------------------------------------------------- B. individual assignment


def test_student_specific_fee_is_additional_and_duplicate_is_409(db):
    tuition = _structure(db)
    transport = _structure(db, amounts=((2, "500"),), class_id=None)
    row = mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": transport["id"], "student_id": 101})
    assert row["structure_id"] == transport["id"]
    # the class assignment is untouched; the student now owes both
    assert _assignment(db, tuition["id"], 101).id != row["id"]
    balance = erp.student_fee_balance(db, SCHOOL, 101)
    assert balance["payable"] == 1700.0
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": transport["id"], "student_id": 101})
    assert (exc.value.status_code, exc.value.detail) == (409, mgmt.ASSIGNMENT_EXISTS_DETAIL)
    # already paying it through the class -> same 409
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": tuition["id"], "student_id": 102})
    assert exc.value.status_code == 409


def test_unique_index_blocks_duplicate_even_without_precheck(db):
    """The DB is the last line of defence for concurrent POST /fee-assignments."""
    s = _structure(db, class_id=None)
    db.add(t.FeeAssignment(school_id=SCHOOL, structure_id=s["id"], student_id=101))
    db.commit()
    real = mgmt._active_assignment
    mgmt._active_assignment = lambda *a, **k: None  # simulate the race: pre-check saw nothing
    try:
        with pytest.raises(AcademicError) as exc:
            mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": s["id"], "student_id": 101})
    finally:
        mgmt._active_assignment = real
    assert (exc.value.status_code, exc.value.detail) == (409, mgmt.ASSIGNMENT_EXISTS_DETAIL)
    assert db.query(t.FeeAssignment).filter_by(structure_id=s["id"]).count() == 1


def test_reassign_after_soft_delete_is_allowed(db):
    s = _structure(db, class_id=None)
    row = mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": s["id"], "student_id": 101})
    mgmt.soft_delete_fee_assignment(db, SCHOOL, row["id"])
    again = mgmt.create_fee_assignment(db, SCHOOL, {"structure_id": s["id"], "student_id": 101})
    assert again["id"] != row["id"]


@pytest.mark.parametrize(
    "body,status",
    [
        ({"structure_id": 0, "student_id": 101}, 422),
        ({"structure_id": 1, "student_id": 103}, 422),   # inactive student
        ({"structure_id": 1, "student_id": 104}, 422),   # transferred
        ({"structure_id": 1, "student_id": 105}, 404),   # deleted
        ({"structure_id": 1, "student_id": 108}, 404),   # other school
        ({"structure_id": 999, "student_id": 101}, 404),
    ],
)
def test_invalid_assignment_requests(db, body, status):
    _structure(db, class_id=None)
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_assignment(db, SCHOOL, body)
    assert exc.value.status_code == status


# ---------------------------------------------------------------- C. concessions and balance


def test_fixed_concession_payable_and_remaining_balance(db):
    s = _structure(db)
    mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "amount", "value": "200", "reason": "sibling"})
    a = _assignment(db, s["id"], 101)
    _pay(db, a.id, "300.10")
    figures = erp.assignment_amounts(db, SCHOOL, a)
    assert figures == {"total": Decimal("1200.00"), "concession": Decimal("200.00"), "payable": Decimal("1000.00"),
                       "paid": Decimal("300.10"), "balance": Decimal("699.90")}
    out = mgmt.fees_outstanding(db, SCHOOL)
    line = next(i for i in out["items"] if i["student_id"] == 101)
    assert (line["payable"], line["concession"], line["paid"], line["balance"]) == (1000.0, 200.0, 300.1, 699.9)


def test_percent_concession_uses_decimal_half_up(db):
    s = _structure(db, amounts=((1, "1000.05"),))
    mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "percent", "value": "12.5", "reason": "merit"})
    figures = erp.assignment_amounts(db, SCHOOL, _assignment(db, s["id"], 101))
    # 1000.05 * 12.5% = 125.00625 -> 125.01 ; payable 875.04 (float maths gave 125.0 / 875.05)
    assert (figures["concession"], figures["payable"]) == (Decimal("125.01"), Decimal("875.04"))


def test_full_exemption_gives_zero_payable_and_blocks_payment(db):
    s = _structure(db)
    mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "percent", "value": 100, "reason": "staff child"})
    a = _assignment(db, s["id"], 101)
    assert erp.assignment_amounts(db, SCHOOL, a)["payable"] == Decimal("0.00")
    with pytest.raises(AcademicError) as exc:
        _pay(db, a.id, "0.01")
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "body,status,detail_part",
    [
        ({"kind": "amount", "value": "1200.01"}, 422, "cannot exceed the fee structure total"),
        ({"kind": "percent", "value": "100.01"}, 422, "cannot exceed 100"),
        ({"kind": "amount", "value": 0}, 422, "value > 0"),
        ({"kind": "amount", "value": -5}, 422, "value > 0"),
        ({"kind": "bogus", "value": 5}, 422, "kind"),
        ({"kind": "amount", "value": "abc"}, 422, "value is required"),
    ],
)
def test_excessive_or_invalid_concessions_rejected(db, body, status, detail_part):
    s = _structure(db)
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "reason": "r", **body})
    assert exc.value.status_code == status and detail_part in exc.value.detail
    assert db.query(t.FeeConcession).count() == 0


def test_concession_equal_to_total_is_allowed(db):
    s = _structure(db)
    mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "amount", "value": "1200", "reason": "waiver"})
    assert erp.assignment_amounts(db, SCHOOL, _assignment(db, s["id"], 101))["payable"] == Decimal("0.00")


def test_concession_below_amount_already_paid_rejected_and_duplicate_409(db):
    s = _structure(db)
    a = _assignment(db, s["id"], 101)
    _pay(db, a.id, "1100")
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "amount", "value": "200", "reason": "late"})
    assert exc.value.status_code == 422 and "already been paid" in exc.value.detail
    mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "amount", "value": "100", "reason": "ok"})
    with pytest.raises(AcademicError) as exc:
        mgmt.create_fee_concession(db, SCHOOL, {"student_id": 101, "structure_id": s["id"], "kind": "amount", "value": "1", "reason": "again"})
    assert exc.value.status_code == 409
    assert erp.assignment_amounts(db, SCHOOL, a)["balance"] == Decimal("0.00")


def test_overpayment_rejected_exact_balance_accepted(db):
    s = _structure(db)
    a = _assignment(db, s["id"], 101)
    _pay(db, a.id, "0.10")
    _pay(db, a.id, "0.20")
    with pytest.raises(AcademicError):
        _pay(db, a.id, "1199.71")
    _pay(db, a.id, "1199.70")
    assert erp.assignment_amounts(db, SCHOOL, a)["balance"] == Decimal("0.00")


# ---------------------------------------------------------------- D. installments


def test_1200_in_two_installments_persists_600_600(db):
    s = _structure(db, installments=_inst("600", "600"))
    rows = db.query(t.FeeInstallment).filter_by(structure_id=s["id"], deleted_at=None).order_by(t.FeeInstallment.sort_order).all()
    assert [Decimal(str(r.amount)) for r in rows] == [Decimal("600.00"), Decimal("600.00")]
    assert [r.name for r in rows] == ["Installment 1", "Installment 2"]
    assert sum(Decimal(str(r.amount)) for r in rows) == Decimal("1200.00")
    assert (s["total"], s["installments_total"], s["installments_match_total"]) == (1200.0, 1200.0, True)


def test_single_payment_schedule_keeps_full_payment_label(db):
    s = _structure(db, installments=_inst("1200", names=["Full payment"]))
    assert [i["name"] for i in s["installments"]] == ["Full payment"]


def test_full_payment_label_corrected_in_multi_installment_schedule(db):
    """The QA bug: splitting the default "Full payment" row gave "Full payment" + "Installment 2"."""
    s = _structure(db, installments=_inst("600", "600", names=["Full payment", "Installment 2"]))
    assert [i["name"] for i in s["installments"]] == ["Installment 1", "Installment 2"]
    s2 = _structure(db, installments=_inst("400", "800", names=["Term 1", " full  PAYMENT "]))
    assert [i["name"] for i in s2["installments"]] == ["Term 1", "Installment 2"]


@pytest.mark.parametrize(
    "total,parts",
    [
        ("1000", ("333.33", "333.33", "333.34")),      # equal preset, last absorbs rounding
        ("1000.01", ("250", "250", "250", "250.01")),  # quarterly
        ("1200", ("100",) * 12),                       # monthly
        ("1200", ("200", "1000")),                     # unequal
        ("0.03", ("0.01", "0.01", "0.01")),
        ("99999.99", ("33333.33", "33333.33", "33333.33")),
    ],
)
def test_presets_sum_exactly_to_total(db, total, parts):
    s = _structure(db, amounts=((1, total),), installments=_inst(*parts))
    stored = [Decimal(str(r.amount)) for r in db.query(t.FeeInstallment).filter_by(structure_id=s["id"], deleted_at=None)]
    assert sum(stored) == Decimal(total) and sorted(stored) == sorted(Decimal(p) for p in parts)


@pytest.mark.parametrize("parts", [("600", "599.99"), ("600", "600.01"), ("600.005", "599.995"), ("1200", "0")])
def test_schedule_that_loses_or_creates_money_is_rejected(db, parts):
    with pytest.raises(AcademicError) as exc:
        _structure(db, installments=_inst(*parts))
    assert exc.value.status_code == 422
    assert db.query(t.FeeInstallment).filter_by(deleted_at=None).count() == 0


def test_amount_change_without_schedule_is_flagged(db):
    s = _structure(db, installments=_inst("600", "600"))
    after = mgmt.update_fee_structure(db, SCHOOL, s["id"], {"amounts": [{"fee_type_id": 1, "amount": "1300"}]})
    assert (after["total"], after["installments_total"], after["installments_match_total"]) == (1300.0, 1200.0, False)
    fixed = mgmt.update_fee_structure(db, SCHOOL, s["id"], {"amounts": [{"fee_type_id": 1, "amount": "1300"}], "installments": _inst("650", "650")})
    assert fixed["installments_match_total"] is True


def test_installment_allocation_is_per_student(db):
    """Before the fix, student A's payment marked installment 1 as paid for every student."""
    s = _structure(db, installments=_inst("600", "600"))
    a101, a102 = _assignment(db, s["id"], 101), _assignment(db, s["id"], 102)
    _pay(db, a101.id, "600")
    _pay(db, a102.id, "600")
    inst1, inst2 = db.query(t.FeeInstallment).filter_by(structure_id=s["id"], deleted_at=None).order_by(t.FeeInstallment.sort_order).all()
    allocs = db.query(t.FeePaymentAllocation).all()
    assert {(x.installment_id, Decimal(str(x.amount))) for x in allocs} == {(inst1.id, Decimal("600.00"))}
    assert len(allocs) == 2
    for sid in (101, 102):
        lines = erp.student_fee_balance(db, SCHOOL, sid)["assignments"][0]["installments"]
        assert [(i["allocated"], i["outstanding"]) for i in lines] == [(600.0, 0.0), (0.0, 600.0)]
    _pay(db, a101.id, "600")
    lines = erp.student_fee_balance(db, SCHOOL, 101)["assignments"][0]["installments"]
    assert [i["outstanding"] for i in lines] == [0.0, 0.0]


def test_cancelled_payment_frees_its_installment(db):
    s = _structure(db, installments=_inst("600", "600"))
    a = _assignment(db, s["id"], 101)
    pay = _pay(db, a.id, "600")
    erp.cancel_fee_payment(db, SCHOOL, pay["id"], "wrong student")
    _pay(db, a.id, "600")
    first = erp.student_fee_balance(db, SCHOOL, 101)["assignments"][0]["installments"][0]
    assert (first["allocated"], first["outstanding"]) == (600.0, 0.0)


def test_schedule_with_payments_cannot_be_replaced(db):
    s = _structure(db, installments=_inst("600", "600"))
    _pay(db, _assignment(db, s["id"], 101).id, "100")
    with pytest.raises(AcademicError) as exc:
        erp.set_structure_installments(db, SCHOOL, s["id"], _inst("1200"))
    assert exc.value.status_code == 409


def test_idempotent_collect_returns_same_payment(db):
    s = _structure(db)
    a = _assignment(db, s["id"], 101)
    first = _pay(db, a.id, "100", idempotency_key="k-1")
    second = _pay(db, a.id, "100", idempotency_key="k-1")
    assert first["id"] == second["id"] and db.query(t.FeePayment).count() == 1


@pytest.mark.parametrize(
    "kind,value,total,expected",
    [
        ("amount", "200", "1200", "200.00"),
        ("amount", "5000", "1200", "1200.00"),   # capped
        ("percent", "33.33", "100", "33.33"),
        ("percent", "150", "100", "100.00"),     # capped at 100%
        ("percent", "10", "0", "0.00"),
        ("amount", "-1", "100", "0.00"),
    ],
)
def test_concession_value_bounds(kind, value, total, expected):
    assert erp.concession_value(kind, value, Decimal(total)) == Decimal(expected)


# ---------------------------------------------------------------- routes (no DB)


def _client():
    from app.main import app

    return TestClient(app)


def test_assign_class_route_requires_school_admin():
    r = _client().post("/api/v1/school-admin/fee-structures/1/assign-class")
    assert r.status_code == 401


def test_openapi_documents_new_fields_and_route():
    from app.main import app

    spec = app.openapi()
    assert "post" in spec["paths"]["/api/v1/school-admin/fee-structures/{row_id}/assign-class"]
    props = spec["components"]["schemas"]["FeeStructureOut"]["properties"]
    assert {"installments_total", "installments_match_total", "class_assignment"} <= set(props)


# ---------------------------------------------------------------- E. public enquiry

URL = "/api/v1/public/schools/SCH001/contact-inquiries"
VALID = {"name": "Asha Rao", "email": "asha@example.org", "phone": "+91 98765 43210",
         "subject": "Admissions", "message": "Please call me back."}


@pytest.fixture()
def public_client(monkeypatch):
    from app.api.deps import central_db
    from app.core import rate_limit
    from app.main import app
    from app.services.v1 import school_settings_cms as cms

    captured: list[dict] = []

    def fake_create(_db, code, body):
        captured.append({"code": code, **body})
        return {"id": 1, "school_id": 7, "name": body["name"], "email": body["email"],
                "phone": body.get("phone"), "subject": body["subject"], "message": body["message"],
                "status": "new", "source": "public", "created_at": None, "updated_at": None}

    monkeypatch.setattr(cms, "create_public_contact_inquiry", fake_create)
    app.dependency_overrides[central_db] = lambda: None
    rate_limit.CONTACT_PER_IP.reset()
    rate_limit.FORGOT_PER_IP.reset()
    try:
        yield TestClient(app), captured
    finally:
        app.dependency_overrides.pop(central_db, None)
        rate_limit.CONTACT_PER_IP.reset()
        rate_limit.FORGOT_PER_IP.reset()


def test_public_enquiry_without_auth_succeeds(public_client):
    client, captured = public_client
    r = client.post(URL, json=VALID)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "new" and captured[0]["code"] == "SCH001"


@pytest.mark.parametrize("missing", ["name", "email", "subject", "message"])
def test_public_enquiry_missing_required_field(public_client, missing):
    client, captured = public_client
    body = {k: v for k, v in VALID.items() if k != missing}
    r = client.post(URL, json=body)
    assert r.status_code == 422 and not captured
    assert any(missing in err["loc"] for err in r.json()["detail"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "not-an-email"),
        ("phone", "call me maybe"),
        ("phone", "12345"),
        ("phone", "1" * 16),
        ("name", "x" * 121),
        ("subject", "x" * 201),
        ("message", "x" * 5001),
        ("message", "   "),
        ("name", "Asha\x00Rao"),
        ("school_id", 99),  # never accepted from the body
    ],
)
def test_public_enquiry_rejects_bad_or_oversized_input(public_client, field, value):
    client, captured = public_client
    r = client.post(URL, json={**VALID, field: value})
    assert r.status_code == 422 and not captured


def test_public_enquiry_malformed_json(public_client):
    client, captured = public_client
    r = client.post(URL, content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and not captured


def test_public_enquiry_html_is_stored_as_text_not_rejected(public_client):
    client, captured = public_client
    r = client.post(URL, json={**VALID, "message": "<script>alert(1)</script>"})
    assert r.status_code == 201
    assert captured[0]["message"] == "<script>alert(1)</script>"  # escaped by the UI, never executed


def test_public_enquiry_rate_limited_separately_from_forgot_password(public_client):
    from app.core import rate_limit

    client, _ = public_client
    for _ in range(rate_limit.CONTACT_PER_IP.limit):
        assert client.post(URL, json=VALID).status_code == 201
    r = client.post(URL, json=VALID)
    assert r.status_code == 429
    # forgot-password for the same IP is unaffected (used to share this bucket)
    rate_limit.FORGOT_PER_IP.check("testclient")
    assert r.headers.get("retry-after")
