# Phase 1 audit: fee assignment, installments, Request Demo

Branch `fix/fee-installment-demo` (from `main` 5fdc23f) · 2026-11-13 · written before any code change.

All paths are under `/api/v1/school-admin` unless shown otherwise. Auth for every fee route: School Admin bearer token plus the `fees.manage` permission (`require_fees`). The optional `X-Branch-Id` header is resolved by `get_branch_context`.

## Where the code lives

| Area | Routes | Service | Schemas |
|---|---|---|---|
| Fee types, structures, assignments, concessions, payments, collect, outstanding | `api/v1/school_admin_mgmt.py` | `services/v1/school_academic_mgmt.py` | `schemas/v1/school_admin_erp.py` (request), `school_admin_erp_responses.py` (OpenAPI only; handlers return dicts) |
| Installments, payment allocation, receipts, cancel, collection report, portal balance | `api/v1/school_admin_erp.py`, `api/student_erp_reads.py` | `services/v1/school_erp_fees.py` | same |
| Public contact enquiry | `api/v1/school_admin_settings.py` (`public_router`) | `services/v1/school_settings_cms.py` | `PublicContactBody` (in the route file) |
| Tables | `fee_structures`, `fee_structure_amounts`, `fee_assignments`, `fee_concessions`, `fee_payments`, `fee_installments`, `fee_payment_allocations`, `contact_inquiries` | `models/tables.py`; migrations 0039, 0041, 0046 | |

Business rules the team agreed on: [FEES_TRANSPORT_GRADING_API_CONTRACT.md](FEES_TRANSPORT_GRADING_API_CONTRACT.md) §4–7 (the contract written with the frontend). The findings below compare the code against it.

## A. Fee assignment

| # | Contract rule | Actual backend behaviour | Verdict |
|---|---|---|---|
| A1 | "A structure applies automatically to every student of its class in its session." | Creating a structure with `class_id` creates **no** assignments. A student owes a structure only if a `fee_assignments` row exists, and rows are created one student at a time (`POST /fee-assignments`). The frontend (live mode) also counts dues from assignments only. | **Backend gap.** Class fees never reach students unless the admin assigns each student by hand. |
| A2 | Inactive students excluded | No class-level logic exists. Other modules already define enrolment as `enrollment_status in {admitted, active}`, not deleted, same `session_year_id` (`school_offline_exams._enrolled`). | Reuse that rule. |
| A3 | Individual assignment = "fees outside the student's class structure (e.g. transport). 409 if already assigned, or if the student already pays it through their class." | It's an **additional** fee. Nothing in the schema overrides a class fee (there's no amount on an assignment), and reductions are done with concessions. A duplicate is blocked by the partial unique index `uq_fee_assignments_active (structure_id, student_id) WHERE deleted_at IS NULL`, surfacing as a generic 409 "A record with these details already exists". No check that the student is enrolled. | Behaviour correct, message unclear, validation missing. |
| A4 | Duplicate prevention under concurrency | The DB unique index makes it concurrency-safe. The frontend's pre-check (list, then POST) is not. | OK (DB). |

## B. Concessions and balances

| # | Finding | Verdict |
|---|---|---|
| B1 | Two copies of the concession and balance maths: `school_academic_mgmt._concession_amount` (**float**) is used by `/fees/collect` and `/fees/outstanding`; `school_erp_fees._concession_amount` (Decimal) is used by the portal balance. | **Float money maths; duplicated logic.** |
| B2 | A fixed concession larger than the structure total is **accepted**, then silently capped at compute time. | Excessive concession not prevented. |
| B3 | A concession can be added after payments, which makes payable < paid and the balance negative. | Not prevented. |
| B4 | One concession per student per structure: unique index `uq_fee_concessions_active` (generic 409). Percent ≤ 100 is already validated. | OK. |
| B5 | Payable = max(total − concession, 0); outstanding = payable − successful payments. | Formula correct; arithmetic in float (B1). |
| B6 | `/fees/collect` checks the balance and then inserts, with no row lock, so two concurrent collections can both pass and overpay. | Race. |
| B7 | The School Admin has no per-student balance route (contract §7 `GET /students/{id}/fees`). `student_fee_balance` exists only for the student/parent portal. The frontend rebuilds dues from four list calls. | Missing route; needs approval (new endpoint). |

## C. Installments

| # | Finding | Verdict |
|---|---|---|
| C1 | No backend generator or presets. The **frontend** splits (`admin-web/lib/ops/fees-math.ts::splitEvenly`: floor each to the paisa, last one absorbs the rest) and sends explicit rows. The backend validates **sum == structure total** exactly (Decimal, 2 dp, `ROUND_HALF_UP`) or returns 422. ₹1,200 / 2 → 600 + 600 is accepted and saved. | Invariant enforced server-side. |
| C2 | **"Full payment" label:** created in the **frontend** (`admin-web/components/ops/fees.tsx:144,158`). The default row is named "Full payment", and `splitInto` keeps `list[index]?.name`, so splitting into 2 gives "Full payment" + "Installment 2". The backend stores whatever name it gets. | Frontend bug. The backend can correct the label when saving. |
| C3 | **Allocations are shared across students.** `_installment_allocated` sums allocations from **every** student's payments on a structure. When student A pays instalment 1, student B's payment skips to instalment 2 (or ends unallocated), and B's balance shows instalment 1 as paid. | **Real calculation bug.** |
| C4 | `PATCH /fee-structures/{id}` with new `amounts` and no `installments` leaves the old schedule whose sum no longer equals the total. The frontend does exactly this (PATCH amounts, then a separate PUT installments), so a failed PUT leaves it inconsistent. New amount rows also lose `branch_id`. | Invariant can break; branch bug. |
| C5 | Installment amounts are written as `float(Decimal)` into `Numeric(12,2)`. 2-dp values round-trip, but there's no reason to leave Decimal. | Minor. |

## D. Request Demo / public enquiry

| # | Finding | Verdict |
|---|---|---|
| D1 | No platform-level **Request Demo** API (prospect → SchoolSarthi). The marketing "Request demo" button links to `/login` (`admin-web/components/marketing/Hero.tsx:27`). | **Missing.** Needs separate approval (§E). |
| D2 | Existing public enquiry: `POST /api/v1/public/schools/{code}/contact-inquiries`, no auth. It is for an **existing** school's website (the school is resolved by `code`, status = 1), stored in `contact_inquiries`, and read by the School Admin at `/contact-inquiries`. Body `{name, email (EmailStr), phone?, subject, message}`, `extra="forbid"`. | Exists. Not a demo request (it needs a school code). |
| D3 | On D2: `message` has no max length; `phone` is free text; rate limit reuses the **forgot-password** bucket (`FORGOT_PER_IP`, 20/h), so enquiries and password resets block each other. On `main` the IP is the proxy's (fixed on `fix/p0-school-admin-auth-domain`). | Hardening needed. |

## E. Plan (in scope, no schema change, no migration)

1. Class-level assignment: `POST /fee-structures/{id}/assign-class` (idempotent, enrolled students only, savepoint per row so a concurrent run can't make duplicates). It also runs automatically when a structure is created with a `class_id`.
2. Individual assignment: a clear 409 for a duplicate and a 422 for a student who isn't enrolled.
3. One Decimal implementation for concession, payable and balance; reject a fixed concession above the total, or one below what's already paid; lock the assignment row on collect.
4. Per-student installment allocation (C3); keep the structure-level aggregate where it is meant (replace guard).
5. When a schedule has more than one row, save a row named "Full payment" as "Installment N" (its position); save Decimal; keep `branch_id` on PATCHed amounts; report `installments_total` / `installments_match_total` on structures.
6. Harden the public enquiry (length and phone limits, its own rate-limit bucket).
7. Not built (needs approval): Request Demo API; School Admin per-student balance route.
8. Tests: SQLite in-memory service tests (Decimal, labels, allocation, duplicates, concessions) plus route-level validation tests. The Postgres suite runs separately on the isolated test DB.
