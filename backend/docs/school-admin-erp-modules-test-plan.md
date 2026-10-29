# School Admin ERP — Five Modules Test Plan

**Date:** 2026-10-29  
**Companion:** [`school-admin-erp-modules-implementation-plan.md`](./school-admin-erp-modules-implementation-plan.md)  
**Database rule:** Run integration tests **only** against an isolated `TEST_DATABASE_URL`. Never point pytest at live Neon. Do not apply migrations to Neon from CI or local “convenience” upgrades without explicit approval.

---

## Test layers

| Layer | Tooling | DB required? | Purpose |
|-------|---------|--------------|---------|
| A. Offline / parity | `pytest --noconftest tests_offline/` + selected `tests/v1/*` | No | Alembic chain, model columns, INR/installment validators, OpenAPI path registration |
| B. Route registration | `tests/v1/test_school_admin_erp_routes_registered.py` | No | Admin / staff / portal paths present on `app` |
| C. Isolated DB integration | `tests/v1/…` with fixture DB | Yes — `TEST_DATABASE_URL` only | Auth, school scoping, fee math, capacity, publish gates, GPS/attendance |
| D. Manual / contract smoke | curl / OpenAPI | Optional isolated | PDF content-type, poll payload shape for Juli/Vishal |

---

## Environment

```text
TEST_DATABASE_URL=postgresql+psycopg://…   # dedicated empty/test DB only
# Do NOT set DATABASE_URL to Neon for pytest
# Do NOT alembic upgrade Neon without approval
```

Suggested local commands (PowerShell-friendly):

```powershell
cd backend
$env:PYTHONPATH = "."
# Layer A + B (safe without DB):
python -m pytest --noconftest tests_offline/ tests/v1/test_school_admin_erp_routes_registered.py tests/v1/test_modules_orm_migration_parity.py tests/v1/test_academic_schema.py -q

# Layer C (only when TEST_DATABASE_URL is a real isolated DB):
# python -m pytest tests/v1/test_school_admin_erp_*.py -q
```

---

## Layer A — Offline / parity (must pass without Neon)

| Case | File / assertion |
|------|------------------|
| `20261029_0041` revises `20261028_0040` and is sole head | `tests_offline/test_erp_wave_parity.py` |
| Heads updated in academic/settings parity | `test_academic_mgmt_wave_parity.py`, `test_school_settings_wave_parity.py` |
| Modules ORM migration list includes `0041` | `tests/v1/test_modules_orm_migration_parity.py` |
| Academic schema head is `0041` | `tests/v1/test_academic_schema.py` |
| Model columns: cancel fields, driver/helper, installments, allocations, trips/GPS/attendance | `test_erp_wave_parity.py` |
| `inr_quantize` HALF_UP | unit |
| Installment sum validator 422 on mismatch | unit |
| OpenAPI contains key ERP paths | offline + route registration |

**Pass criteria:** All Layer A tests green on a clean checkout without `TEST_DATABASE_URL`.

---

## Layer B — Route registration

Assert paths exist on `app.routes` for at least:

**Admin**

- `/api/v1/school-admin/report-cards/{report_id}/pdf`
- `/api/v1/school-admin/fee-structures/{structure_id}/installments` (GET + PUT)
- `/api/v1/school-admin/fee-payments/{payment_id}/receipt`
- `/api/v1/school-admin/fee-payments/{payment_id}/receipt/pdf`
- `/api/v1/school-admin/fee-payments/{payment_id}/cancel`
- `/api/v1/school-admin/fees/collection-report`
- `/api/v1/school-admin/transport-trips`
- `/api/v1/school-admin/transport-trips/{trip_id}/start|complete|gps|attendance`
- `/api/v1/school-admin/transport/reports/trips`

**Staff**

- `/api/staff/transport/my-trips`
- `/api/staff/transport/trips/{trip_id}/gps`
- `/api/staff/transport/trips/{trip_id}/attendance`

**Portal**

- `/api/student/report-cards`, `…/{report_id}`, `…/pdf`
- `/api/student/fees/balance`, `…/payments`, receipt PDF
- `/api/parent/children/{student_id}/report-cards…`, `…/fees…`, `…/transport/live`

Preserve regression that existing collect/outstanding/vehicles paths still register.

---

## Layer C — Isolated DB integration (when TEST_DATABASE_URL is set)

Use a disposable schema or dedicated database. Prefer factory helpers already used by school-admin people/offline-exam tests. Each case assumes school A vs school B for tenancy.

### M1 — Report cards / grading

| # | Scenario | Expect |
|---|----------|--------|
| RC-1 | Generate report cards from processed offline results | 200/201; row per student; letter from scale |
| RC-2 | Admin PDF | `200` `application/pdf`; non-empty body |
| RC-3 | Student/parent read unpublished exam | **404** |
| RC-4 | Student/parent read published exam | **200** JSON; PDF 200 |
| RC-5 | Parent of unrelated student | **404** |
| RC-6 | Cross-school report id | **404** |

### M2 — Installments

| # | Scenario | Expect |
|---|----------|--------|
| FI-1 | PUT installments summing to structure total | **200**; list matches |
| FI-2 | Sum mismatch (e.g. 90 vs 100) | **422** |
| FI-3 | Zero/negative installment amount | **422** |
| FI-4 | Replace after success allocation exists | **409** |
| FI-5 | Create structure with optional `installments` | Installments persisted; sum OK |
| FI-6 | INR rounding edge (`10.005` → `10.01`) | Validator/unit + collect use same helper |

### M3 — Collect / allocate / receipt / cancel / report

| # | Scenario | Expect |
|---|----------|--------|
| FC-1 | Collect partial payment | Allocates earliest due; balance decreases |
| FC-2 | Collect exact balance | Outstanding 0 |
| FC-3 | Overpay | **422** `amount exceeds outstanding balance` |
| FC-4 | Idempotency key replay | Same payment returned; no double allocate |
| FC-5 | Receipt JSON + PDF | Lines match allocations; PDF content-type |
| FC-6 | Cancel success payment | status cancelled; deleted_at set; allocations soft-deleted; audit row; outstanding restores |
| FC-7 | Cancel already cancelled | **422** |
| FC-8 | Collection report date range + optional class | Totals match success payments only |
| FC-9 | Legacy payment without allocations | Still counts in paid/outstanding |
| FC-10 | Cross-school payment id | **404** |

### M4 — Driver / capacity

| # | Scenario | Expect |
|---|----------|--------|
| TR-1 | PATCH vehicle with same-school driver/helper | **200**; fields returned |
| TR-2 | Driver staff other school | **422/404** per service rules |
| TR-3 | Assign students until capacity | Last over capacity → **409** |
| TR-4 | Capacity null | No capacity error |
| TR-5 | Stop not on route | **422** |

### M5 — Trips / GPS / attendance / parent poll

| # | Scenario | Expect |
|---|----------|--------|
| BT-1 | Create trip → start → GPS → complete | Status transitions valid |
| BT-2 | Staff GPS on own trip | Point stored; latest visible |
| BT-3 | Staff GPS on unauthorized trip | **403/404** |
| BT-4 | Board then drop | Both events; duplicate board → **409/422** |
| BT-5 | Drop before board | **422** |
| BT-6 | Parent live for assigned child with active trip | Latest lat/lng present |
| BT-7 | Parent live for unassigned / other child | **404** |
| BT-8 | No WebSocket assumption | Only HTTP endpoints tested |

### Permissions / auth smoke

| # | Scenario | Expect |
|---|----------|--------|
| AU-1 | Missing Bearer | **401** |
| AU-2 | School admin without `fees.manage` on collect/cancel | **403** |
| AU-3 | Student token on admin ERP route | **401/403** |

---

## Layer D — Manual smoke (optional)

1. OpenAPI `/docs` (debug only) lists ERP tags/paths.
2. Download admin report-card PDF and fee receipt PDF; open in a PDF reader.
3. Parent poll twice; confirm latest GPS updates after staff POST.
4. Confirm SaaS Razorpay subscription flow untouched (smoke existing payment tests if available).

---

## Regression must-not-break

- Offline exam schedule / marks / process / student offline results.
- Existing `POST /fees/collect` clients (path + overpay block).
- Existing vehicle/route/stop/assignment CRUD paths.
- Settings CMS / backup Super Admin isolation.
- No writes to live Neon; no Render deploy; no `admin-web` recreate.

---

## Coverage map (files)

| Area | Automated today (offline) | Integration target |
|------|---------------------------|--------------------|
| Migration head `0041` | `test_erp_wave_parity`, modules ORM, academic schema | alembic upgrade on **test** DB only |
| INR / installment sum | offline unit | FI-* |
| Route registration | `test_school_admin_erp_routes_registered` | — |
| Report PDF / publish | path only | RC-* |
| Collect / cancel / report | path only | FC-* |
| Capacity / driver | path only | TR-* |
| Trips / GPS / attendance / live | path only | BT-* |

---

## Pass / fail for a release candidate

1. Layer A + B green without Neon.
2. If claiming “DB-verified”: Layer C green on isolated `TEST_DATABASE_URL` with migration applied **only** to that DB.
3. Document any skipped Layer C cases explicitly (empty `TEST_DATABASE_URL` → skip; do not claim complete).
4. Blockers that remain acceptable: GPS purge cron, refunds, school fee gateway, WebSockets — see [`SCHOOL_ADMIN_ERP_MODULES_NOTES.md`](./SCHOOL_ADMIN_ERP_MODULES_NOTES.md).

---

## Verified offline results (planning delivery note)

As of 2026-10-29, with empty `TEST_DATABASE_URL` in local `.env`:

```text
pytest --noconftest tests_offline/ \
  tests/v1/test_modules_orm_migration_parity.py \
  tests/v1/test_academic_schema.py \
  tests/v1/test_school_admin_erp_routes_registered.py
→ 34 passed
```

Layer C was **not** executed against Neon and must not be until an isolated test database is configured and approved.
