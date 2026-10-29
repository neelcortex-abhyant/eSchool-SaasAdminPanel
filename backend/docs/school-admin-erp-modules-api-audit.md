# School Admin ERP — Five Modules API Audit

**Date:** 2026-10-29  
**Source:** ERP Five Modules Plan (report cards/grading, fee structures, fee collection, transport master data, bus tracking)  
**Contract reference:** [`FEES_TRANSPORT_GRADING_API_CONTRACT.md`](./FEES_TRANSPORT_GRADING_API_CONTRACT.md)  
**Scope of this document:** Read-only verification against the FastAPI backend. This planning delivery does **not** change application code or apply Neon migrations.

**Classification key**

| Label | Meaning |
|-------|---------|
| Fully implemented | Real routes + models/services; suitable for use pending regression |
| Partially implemented | Related surface exists; contract gaps or incomplete workflows remain |
| Missing | No usable school-admin / staff / portal API for the capability |
| Existing needs testing | Code exists; focused integration tests thin or absent |

**Locked defaults (product plan)**

- Extend existing school-admin surfaces; do not duplicate offline-exam core.
- Platform SaaS Razorpay ([`payments.py`](../app/api/v1/payments.py)) remains billing-only; school fee online gateway is out of scope unless later wired.
- PDF via FPDF (same pattern as [`invoice_pdf.py`](../app/services/v1/invoice_pdf.py)).
- Alembic baseline at plan time: `20261028_0040`. Additive work only; **do not apply to Neon without approval**.
- Preserve existing API paths where possible; flat `/vehicles` preferred over inventing a forced `/transport/*` rename.

**Evidence sources**

- Routes: [`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py), [`school_admin_erp.py`](../app/api/v1/school_admin_erp.py), [`staff_transport.py`](../app/api/staff_transport.py), [`student_erp_reads.py`](../app/api/student_erp_reads.py), [`student_offline_exams.py`](../app/api/student_offline_exams.py), [`stubs.py`](../app/api/stubs.py)
- Services: [`school_academic_mgmt.py`](../app/services/v1/school_academic_mgmt.py), [`school_offline_exams.py`](../app/services/v1/school_offline_exams.py), [`school_erp_fees.py`](../app/services/v1/school_erp_fees.py), [`school_erp_report_cards.py`](../app/services/v1/school_erp_report_cards.py), [`school_erp_transport.py`](../app/services/v1/school_erp_transport.py)
- Models: [`tables.py`](../app/models/tables.py)
- Ops notes: [`SCHOOL_ADMIN_ERP_MODULES_NOTES.md`](./SCHOOL_ADMIN_ERP_MODULES_NOTES.md)

---

## Module 1 — Report cards and grading

| Capability | Status | Evidence |
|------------|--------|----------|
| Grading scales + bands CRUD | Fully implemented (needs integration tests) | Models `GradingScale` / `GradingScaleBand`; `/api/v1/school-admin/grading-scales*`; `letter_for_percentage` / `letter_for_scale` |
| Report card generate / list / get from `OfflineExamResult` | Fully implemented (needs tests) | `POST/GET /report-cards`, `GET /report-cards/{id}` in `school_admin_mgmt.py` |
| Offline marks + `process_results` | Fully implemented | `school_offline_exams.py`; student/parent offline result reads in `student_offline_exams.py` |
| Scale↔session/exam association beyond generate body | Partially implemented | Scale chosen at generate time; no first-class “exam uses scale X” resource |
| Report-card PDF / download | Fully implemented (wave `0041`) | `GET /api/v1/school-admin/report-cards/{report_id}/pdf` → FPDF |
| Parent/student **report-card** APIs | Fully implemented (wave `0041`) | `/api/student/report-cards…`, `/api/parent/children/{id}/report-cards…` (+ PDF); gated by `Exam.publish` |
| Historical snapshot on scale change | Partially implemented | `ReportCard.subjects_json` stores snapshot; no separate RC publish flag (uses `Exam.publish`) |
| Stub `GET /api/student/report` | Existing stub — do not confuse | Laravel-shaped stub in `stubs.py`; real portal paths are under `/api/student/report-cards` |

**Do not invent:** New pass-mark rules. Reuse schedule `passing_marks` / processed `passed` + grading-scale letter bands.

---

## Modules 2–3 — Fee structures and collection

| Capability | Status | Evidence |
|------------|--------|----------|
| Fee types / structures / amounts | Fully / Partially implemented | `/fee-types`, `/fee-structures`; structure create accepts optional `installments` |
| Installment schedules | Fully implemented (wave `0041`) | Model `FeeInstallment`; `GET/PUT /fee-structures/{id}/installments`; sum must equal structure total (INR 2dp) |
| Assignments / concessions | Partially implemented | Create/list/delete; limited PATCH/history; one concession per student+structure |
| Collect + outstanding + payments list | Fully implemented (needs tests) | `POST /fees/collect`, `GET /fees/outstanding`, `GET /fee-payments`; optional idempotency; overpay blocked |
| Installment allocation on collect | Fully implemented (wave `0041`) | `allocate_payment` on new collects; earliest due first; legacy payments without allocations remain valid |
| Receipt JSON + PDF | Fully implemented (wave `0041`) | `/fee-payments/{id}/receipt` and `/receipt/pdf` |
| Collection reports | Fully implemented (wave `0041`) | `GET /fees/collection-report?from_date&to_date&class_id=` |
| Corrections / void with audit | Partially → cancel only | `POST /fee-payments/{id}/cancel` soft-deletes + `cancelled_at` / `cancel_reason` + audit; **no refund / money movement** |
| School fee online gateway | Settings only / out of scope | `payment-gateway-settings`; not wired to `FeePayment`; SaaS Razorpay unchanged |
| Legacy `Fee` / academics fees | Parallel legacy | Do **not** merge silently with FeeType stack |
| Parent/student fee reads | Fully implemented (wave `0041`) | `/api/student/fees/…`, `/api/parent/children/{id}/fees/…` |
| Parent/student online pay | Missing (by design) | Stubs may remain; gateway checkout deferred |

**Contract deltas vs [`FEES_TRANSPORT_GRADING_API_CONTRACT.md`](./FEES_TRANSPORT_GRADING_API_CONTRACT.md)**

- Collect path remains `POST /fees/collect` (not `POST /fee-payments`).
- Outstanding path remains `GET /fees/outstanding` (not `/fee-outstanding`).
- Installments are a first-class sub-resource; structure create may include optional `installments`.
- Path naming preserved for Vishal clients already on flat fee routes.

---

## Module 4 — Transport master data

| Capability | Status | Evidence |
|------------|--------|----------|
| Vehicles / routes / stops / student assignments | Fully / Partially implemented | `/vehicles`, `/transport-routes`, `/transport-stops`, `/student-transport-assignments` |
| Driver / helper on vehicle | Fully implemented (wave `0041`) | `TransportVehicle.driver_staff_id` / `helper_staff_id`; validated same-school staff on create/update |
| Capacity enforcement | Fully implemented (wave `0041`) | `assert_route_vehicle_capacity` on student assignment → **409** when full |
| Path parity with contract `/transport/*` | Partially implemented | Flat paths work; contract docs differ — **keep flat**; document aliases only if Vishal requires |
| Assignment PATCH / history / direction | Partially / Missing | Soft-delete present; richer history/direction fields not required for this wave |

---

## Module 5 — Bus tracking and transport attendance

| Capability | Status | Evidence |
|------------|--------|----------|
| Trips CRUD / start / complete | Fully implemented (wave `0041`) | Models `TransportTrip`; admin `/transport-trips…` |
| GPS updates (HTTP) | Fully implemented (wave `0041`) | `TransportGpsPoint`; admin + staff `POST …/gps`; optional `expires_at` from `GPS_RETENTION_DAYS` |
| Boarding / drop-off attendance | Fully implemented (wave `0041`) | `TransportAttendanceEvent`; board before drop; no duplicate board |
| Staff/driver authenticated ops | Fully implemented (wave `0041`) | `/api/staff/transport/my-trips`, `…/gps`, `…/attendance` via existing staff login |
| Parent live tracking | Fully implemented (wave `0041`) | `GET /api/parent/children/{student_id}/transport/live` (HTTP poll) |
| WebSocket realtime | Missing (by design) | No WebSocket infrastructure; poll only |
| GPS retention purge cron | Missing | Points retained; purge cron deferred — see blockers |
| Laravel-shaped transport stubs | Stub only | Do not confuse with real `/api/staff/transport` and portal live paths |

---

## Cross-cutting

| Topic | Status | Notes |
|-------|--------|-------|
| Auth / RBAC | Fully implemented | School-admin Bearer + `exams.manage` / `fees.manage` / `school.manage` ([`rbac.py`](../app/services/v1/rbac.py)); staff session for drivers; student/parent portal auth mirrors offline exams |
| School scoping | Fully implemented | `school_id` from auth; cross-school ids → 404 |
| Alembic | Additive revision present | Head after wave: `20261029_0041` (revises `20261028_0040`). **Not applied to Neon from this planning doc.** |
| Tests | Partially / Existing needs testing | Offline parity + route registration present; full DB integration requires isolated `TEST_DATABASE_URL` |
| admin-web | Out of scope | No restore / recreate; contracts for Vishal (admin) and Juli (student/parent reads) |
| Super Admin SaaS billing | Unchanged | Do not touch Razorpay subscription flows |

---

## Gap summary (planning baseline → resolved by wave)

| Gap (plan baseline) | Resolution |
|---------------------|------------|
| Report-card PDF | Admin + portal PDF endpoints |
| Parent/student report-card APIs | Portal routes + `Exam.publish` gate |
| Fee installments | `fee_installments` + PUT/GET + sum validation |
| Allocation / receipt PDF / collection report / cancel | `school_erp_fees` + admin routes |
| Driver/helper + capacity | Vehicle FKs + assignment check |
| All of Module 5 tracking | Trips / GPS / attendance / staff + parent poll |

**Still open (product / ops blockers — do not invent)**

1. GPS retention purge cron (history kept; optional `expires_at` only).
2. Fee refunds / gateway reverse (cancel only).
3. School fee online gateway wiring.
4. Installment replace after allocations (**409** by design).
5. Concession vs installment leftover edge (unallocated allocation line; overpay still blocked).
6. Forced path migration to `/transport/*` (not done; flat paths preserved).

---

## Recommended consumers

| Consumer | Use this audit for |
|----------|-------------------|
| Backend implementers | Confirm extend-not-duplicate surfaces before further edits |
| Vishal (admin-web) | Prefer existing flat paths; see implementation plan for ERP additions |
| Juli (student/parent) | Portal read contracts in implementation plan |
| Ops | Migration `0041` apply only with explicit Neon approval |
