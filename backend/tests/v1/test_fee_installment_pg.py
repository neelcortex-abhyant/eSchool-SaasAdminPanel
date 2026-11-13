"""Fee assignment / installment rules on real PostgreSQL (isolated test DB only).

Covers what SQLite cannot: the partial unique indexes as migrated, NUMERIC(12,2)
round-trips, SELECT ... FOR UPDATE on collect, and a real two-session duplicate race.
The schema is built once for the module (each build crosses regions; see QA report).
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal

import pytest

from tests.pg_test_utils import resolve_test_database_url, wipe_public_schema

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def pg():
    from app.core.config import get_settings
    from app.core.database import create_schema, reset_engines, session_factory
    from app.core.security import utcnow
    from app.models import tables as t

    get_settings.cache_clear()
    reset_engines()
    wipe_public_schema(resolve_test_database_url())
    create_schema()
    factory = session_factory()
    db = factory()
    school = t.School(name="Fee QA School", code="FEEQA", database_name="legacy_feeqa", status=1, installed=1, created_at=utcnow())
    db.add(school)
    db.flush()
    sid = school.id
    db.add_all(
        [
            t.SessionYear(id=900, name="2026-27", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), school_id=sid),
            t.SchoolClass(id=905, name="Class 5", medium_id=1, school_id=sid),
            t.Section(id=901, name="A", school_id=sid),
            t.ClassSection(id=950, class_id=905, section_id=901, medium_id=1, school_id=sid),
            t.FeeType(id=901, school_id=sid, name="Tuition"),
        ]
    )
    for n, status in ((1, "active"), (2, "admitted"), (3, "inactive")):
        user = t.User(first_name=f"S{n}", last_name="QA", email=f"fee-student-{n}@feeqa-example.com", password="x", school_id=sid)
        db.add(user)
        db.flush()
        db.add(t.Student(id=9000 + n, user_id=user.id, class_section_id=950, admission_no=f"FQ{n}",
                         admission_date=date(2026, 4, 1), school_id=sid, guardian_id=user.id,
                         session_year_id=900, enrollment_status=status))
    db.commit()
    yield {"db": db, "school_id": sid, "factory": factory}
    db.close()
    reset_engines()


def test_pg_class_assignment_installments_and_per_student_allocation(pg):
    from app.models import tables as t
    from app.services.v1 import school_academic_mgmt as mgmt
    from app.services.v1 import school_erp_fees as erp

    db, sid = pg["db"], pg["school_id"]
    s = mgmt.create_fee_structure(db, sid, {
        "name": "Class 5 2026-27", "session_year_id": 900, "class_id": 905,
        "amounts": [{"fee_type_id": 901, "amount": 1200}],
        "installments": [
            {"name": "Full payment", "due_date": "2026-04-15", "amount": 600},
            {"name": "Installment 2", "due_date": "2026-10-15", "amount": 600},
        ],
    })
    assert s["class_assignment"] == {"eligible_students": 2, "created": 2, "already_assigned": 0}
    rows = db.query(t.FeeInstallment).filter_by(structure_id=s["id"], deleted_at=None).order_by(t.FeeInstallment.sort_order).all()
    assert [(r.name, r.amount) for r in rows] == [("Installment 1", Decimal("600.00")), ("Installment 2", Decimal("600.00"))]

    a1 = db.query(t.FeeAssignment).filter_by(structure_id=s["id"], student_id=9001).one()
    a2 = db.query(t.FeeAssignment).filter_by(structure_id=s["id"], student_id=9002).one()
    mgmt.create_fee_concession(db, sid, {"student_id": 9002, "structure_id": s["id"], "kind": "percent", "value": "12.5", "reason": "merit"})
    mgmt.collect_fee(db, sid, {"assignment_id": a1.id, "amount": "600"})
    mgmt.collect_fee(db, sid, {"assignment_id": a2.id, "amount": "600"})
    mgmt.collect_fee(db, sid, {"assignment_id": a1.id, "amount": "0.01"})  # same second: no receipt clash

    b1 = erp.student_fee_balance(db, sid, 9001)["assignments"][0]
    b2 = erp.student_fee_balance(db, sid, 9002)["assignments"][0]
    assert [(i["allocated"], i["outstanding"]) for i in b1["installments"]] == [(600.0, 0.0), (0.01, 599.99)]
    assert [(i["allocated"], i["outstanding"]) for i in b2["installments"]] == [(600.0, 0.0), (0.0, 600.0)]
    assert (b2["payable"], b2["paid"], b2["outstanding"]) == (1050.0, 600.0, 450.0)

    with pytest.raises(Exception) as exc:
        mgmt.create_fee_assignment(db, sid, {"structure_id": s["id"], "student_id": 9001})
    assert getattr(exc.value, "status_code", None) == 409
    with pytest.raises(Exception) as exc:
        mgmt.create_fee_assignment(db, sid, {"structure_id": s["id"], "student_id": 9003})
    assert getattr(exc.value, "status_code", None) == 422
    with pytest.raises(Exception) as exc:
        mgmt.collect_fee(db, sid, {"assignment_id": a2.id, "amount": "450.01"})
    assert getattr(exc.value, "status_code", None) == 422


def test_pg_concurrent_duplicate_assignment_creates_one_row(pg):
    """Two sessions insert the same assignment at once; the partial unique index keeps one."""
    from app.models import tables as t
    from app.services.v1 import school_academic_mgmt as mgmt

    db, sid, factory = pg["db"], pg["school_id"], pg["factory"]
    extra = mgmt.create_fee_structure(db, sid, {
        "name": "Transport", "session_year_id": 900, "class_id": None,
        "amounts": [{"fee_type_id": 901, "amount": 500}],
    })
    barrier = threading.Barrier(2)
    real = mgmt._active_assignment
    results: list[object] = []

    def worker():
        session = factory()
        try:
            barrier.wait(timeout=60)
            results.append(mgmt.create_fee_assignment(session, sid, {"structure_id": extra["id"], "student_id": 9001})["id"])
        except Exception as exc:  # noqa: BLE001 - recorded for the assertion
            results.append(getattr(exc, "status_code", repr(exc)))
        finally:
            session.close()

    mgmt._active_assignment = lambda *a, **k: None  # both pass the pre-check: worst case
    try:
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=120)
    finally:
        mgmt._active_assignment = real
    assert sorted(type(r).__name__ for r in results) == ["int", "int"]
    assert 409 in results and sum(isinstance(r, int) and r != 409 for r in results) == 1
    db.expire_all()
    assert db.query(t.FeeAssignment).filter_by(structure_id=extra["id"], student_id=9001, deleted_at=None).count() == 1
