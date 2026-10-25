# Grading, report cards, student fees and transport — School Admin API contract

Proposed routes for the admin-web pages under **Exam & performance → Grading scales / Report cards**,
**Institutional finance → Fees** and **Transportation module**. The pages already work on sample data
(`NEXT_PUBLIC_OPS_API_MODE=mock`, the default). When these routes are deployed, set
`NEXT_PUBLIC_OPS_API_MODE=live` (or per module, e.g. `fees:live`) and the same pages call them.

The frontend clients that call these routes are `admin-web/lib/ops/grading.ts`, `fees.ts` and
`transport.ts`; the shapes are in `admin-web/lib/ops/types.ts`.

## Common rules

- Base path: `/api/v1/school-admin`. Bearer auth. The school comes from the session — **no `school_id`
  in any request**, and every query is scoped to the caller's school (another school's id → `404`).
- Permissions (suggested): grading and report cards `exams.manage`; fees `fees.manage`; transport
  `transport.manage` (new) or `school.manage`. Missing permission → `403 {"detail": "Forbidden"}`.
- Lists: `?page=1&page_size=20` (max 50) → `{ "items": [...], "total": n, "page": 1, "page_size": 20 }`.
- Errors, as elsewhere in v1:
  - `422` with FastAPI's `detail` list for field errors (`loc: ["body", "field"]`), or a
    `{"detail": "sentence"}` for rule breaks. Nested fields use their path, e.g. `ranges.2.min_percent`,
    `installments.1.due_date`, `items.0.amount`.
  - `409 {"detail": "sentence"}` for conflicts (duplicates, capacity, things in use).
  - `404 {"detail": "Record not found"}`.
- Money is rupees as a number with up to 2 decimals (or say if you prefer integer paise — the client
  converts in one place). Dates `YYYY-MM-DD`, date-times ISO 8601 UTC, times `HH:MM`.
- `status` on records is `1` active / `0` inactive.

---

## 1. Grading scales

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/grading-scales` | | `{items: GradingScale[]}` |
| POST | `/grading-scales` | `GradingScaleInput` | `201 GradingScale` |
| GET | `/grading-scales/{id}` | | `GradingScale` |
| PATCH | `/grading-scales/{id}` | `GradingScaleInput` (partial allowed) | `GradingScale` |
| DELETE | `/grading-scales/{id}` | | `{deleted: true}` |

```json
GradingScale = {
  "id": 1, "name": "CBSE 9-point", "description": null, "is_default": true, "status": 1,
  "ranges": [
    {"id": 1, "grade": "A1", "min_percent": 91, "max_percent": 100, "grade_point": 10, "remark": "Outstanding", "is_pass": true}
  ]
}
```

Rules (422 unless noted):
- `name` required, unique per school (409).
- At least one range; `grade` unique within the scale (case-insensitive); `0 ≤ min_percent ≤ max_percent ≤ 100`.
- Ranges are inclusive, must not overlap, and together must cover 0–100 (gaps of 0.01 allowed between
  `90.99` and `91`). Percentages are compared after rounding to 2 decimals.
- Exactly one default scale per school: setting `is_default: true` clears the others. Deleting the
  default scale → 409 "Choose another default scale before deleting this one."

## 2. Report cards

| Method | Path | Query | Response |
|---|---|---|---|
| GET | `/report-cards/{student_id}` | `session_year_id` (required), `grading_scale_id` (optional; default scale otherwise) | `ReportCard` |
| GET | `/report-cards/{student_id}/pdf` | same | `application/pdf` |

`ReportCard` (see `lib/ops/types.ts`): student details (name, admission no., roll, class, section, session,
guardian), `exams[]` — one per **processed** offline exam of the student's section in the session, with
`subjects[]` (`subject_name, marks_obtained, max_marks, status present|absent|withheld, grade, passed`),
`total_obtained, total_max, percentage, grade, passed, published` — and `overall {total_obtained,
total_max, percentage, grade, passed}`, `promotion` ("Promoted", "Not promoted" or null until every exam
of the session is processed) and `scale_name`.

Grades come from the grading scale applied to the percentage. Withheld subjects are left out of totals
(the same rule as `process-results`). It would also help to return `grade` on
`GET /offline-exams/{id}/results` rows so the results page doesn't grade on the client.

## 3. Fee types

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/fee-types` | `?status=&category=` | `{items: FeeType[]}` |
| POST | `/fee-types` | `{name, category, description, status}` | `201 FeeType` |
| PATCH | `/fee-types/{id}` | any of the same | `FeeType` |

`category` ∈ `tuition | admission | examination | transport | other`. `name` unique per school (409).
Deactivating keeps the type on existing structures but hides it from new ones. No hard delete
(types are referenced by structures and payments).

## 4. Fee structures (with installments)

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/fee-structures` | `q, session_year_id, class_id, status, sort=name\|class\|total, order, page, page_size` | page of `FeeStructure` |
| POST | `/fee-structures` | `FeeStructureInput` | `201 FeeStructure` |
| GET | `/fee-structures/{id}` | | `FeeStructure` |
| PATCH | `/fee-structures/{id}` | `FeeStructureInput` or `{status}` | `FeeStructure` |

```json
FeeStructureInput = {
  "name": "Class 5 annual fees 2026-27", "session_year_id": 2, "class_id": 3,
  "items": [{"fee_type_id": 1, "amount": 36000}, {"fee_type_id": 3, "amount": 2000}],
  "installments": [{"id": 1, "name": "Term 1", "due_date": "2026-04-15", "amount": 19000},
                   {"name": "Term 2", "due_date": "2026-10-15", "amount": 19000}],
  "late_fee_per_day": 10, "status": 1
}
```

`FeeStructure` adds `id, session_name, class_name, total` and expands items with `fee_type_name, category`.

Rules: name required and unique per session (409); session and class belong to the school; at least one
item, each fee type once, amount > 0; at least one installment, names required, due dates valid and
distinct; **installment amounts must add up to the total of the items** (422 on `installments`).
Installments keep their `id` across edits; an installment with payments against it can't be removed
(409). A structure applies automatically to every student of its class in its session.

## 5. Assigning fees to individual students

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/fee-assignments` | `structure_id, student_id` | `{items: FeeAssignment[]}` |
| POST | `/fee-assignments` | `{structure_id, student_id}` | `201 FeeAssignment` |
| DELETE | `/fee-assignments/{id}` | | `{deleted: true}` |

For fees outside the student's class structure (e.g. transport). 409 if already assigned, if the
student already pays it through their class, or (delete) if payments exist against it.

## 6. Concessions, discounts and exemptions

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/fee-concessions` | `structure_id, student_id` | `{items: Concession[]}` |
| POST | `/fee-concessions` | `{student_id, structure_id, kind: "percent"\|"amount", value, reason}` | `201 Concession` |
| PATCH | `/fee-concessions/{id}` | same | `Concession` |
| DELETE | `/fee-concessions/{id}` | | `{deleted: true}` |

`value > 0`; a percentage ≤ 100 (100 = full exemption); an amount is capped at the structure total;
`reason` required. One concession per student per structure (409). The concession is spread across the
structure's installments in proportion to their amounts (the last installment absorbs rounding).

## 7. What a student owes

`GET /students/{student_id}/fees` → `StudentDues`:

```json
{
  "student_id": 1, "student_name": "Aarav Sharma", "admission_no": "ADM20260001",
  "class_name": "Class 5", "section_name": "A", "class_section_id": 4,
  "lines": [{"structure_id": 1, "structure_name": "…", "installment_id": 2, "installment_name": "Term 2",
             "due_date": "2026-08-15", "amount": 13000, "concession": 0, "paid": 1500, "balance": 11500, "overdue": true}],
  "total": 48000, "concession": 0, "paid": 19000, "balance": 29000, "overdue": 11500, "pending": 0
}
```

`paid` counts only **successful** payments; `pending` is the sum of online payments waiting for
confirmation. `overdue` = balance of installments whose due date is before today.

## 8. Payments and receipts

| Method | Path | Body / query | Response |
|---|---|---|---|
| POST | `/fee-payments` | `PaymentInput` + header `Idempotency-Key` | `201 FeePayment` |
| GET | `/fee-payments` | `q, student_id, class_section_id, method, status, from_date, to_date, page, page_size` | page of `FeePayment` |
| GET | `/fee-payments/{id}` | | `FeePayment` |
| GET | `/fee-payments/{id}/receipt` | | `Receipt` |
| GET | `/fee-payments/{id}/receipt/pdf` | | `application/pdf` (optional) |
| GET | `/fee-outstanding` | `session_year_id, class_id, class_section_id, q, due_before, only_overdue, page, page_size` | `{items: StudentDues[], total, …, summary: {payable, collected, outstanding, overdue}}` |

```json
PaymentInput = {"student_id": 1, "amount": 6000, "method": "cash|cheque|bank_transfer|upi|card|online",
                "reference": "UPI-883201", "remarks": null, "paid_on": "2026-10-24"}
```

`FeePayment` = `{id, receipt_no, student_id, student_name, admission_no, class_name, section_name,
amount, method, reference, remarks, status: "success"|"pending"|"failed", paid_at, allocations:
[{structure_id, installment_id, installment_name, amount}], collected_by}`.

Rules:
- **Idempotency**: the same `Idempotency-Key` (per school) returns the payment already recorded with
  `200` instead of recording it again. The client sends a new key per attempt and keeps it on retries.
- `amount > 0` and not more than the student's balance (422 on `amount`). Cheque, bank transfer and UPI
  need `reference`. `paid_on` not in the future.
- The server allocates the amount to installments, earliest due date first (partial payments allowed).
- Office methods (cash, cheque, bank transfer, UPI/card at the counter) are recorded as `success` with
  a `receipt_no` (unique per school, e.g. `RCPT-2026-0001`). `online` is recorded as `pending`, gets no
  receipt, and becomes `success` only when the gateway confirms it (webhook/verify, like the subscription
  payments). **The client never sets the status.**
- Receipt: `{payment, school_name, session_name, balance_after}` (the student's balance right after this
  payment). Only for `success` payments; otherwise 409 "A receipt is issued only after the payment is
  confirmed."

## 9. Transport

| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/transport/vehicles` | `status` | `{items: Vehicle[]}` |
| POST | `/transport/vehicles` | `VehicleInput` | `201 Vehicle` |
| PATCH | `/transport/vehicles/{id}` | `VehicleInput` or `{status}` | `Vehicle` |
| GET | `/transport/routes` | `status, q` | `{items: Route[]}` (with `stops`) |
| POST | `/transport/routes` | `{name, description, vehicle_id, status}` | `201 Route` |
| GET | `/transport/routes/{id}` | | `Route` |
| PATCH | `/transport/routes/{id}` | same or `{status}` | `Route` |
| POST | `/transport/routes/{id}/stops` | `{name, stop_order, pickup_time, drop_time, landmark}` | `201 Stop` |
| PATCH | `/transport/stops/{id}` | same | `Stop` |
| DELETE | `/transport/stops/{id}` | | `{deleted: true}` |
| GET | `/transport/assignments` | `q, route_id, class_section_id, page, page_size` | page of `TransportAssignment` |
| POST | `/transport/assignments` | `{student_id, route_id, stop_id, direction: "both"\|"pickup"\|"drop", start_date, status}` | `201` |
| PATCH | `/transport/assignments/{id}` | same | `TransportAssignment` |
| DELETE | `/transport/assignments/{id}` | | `{deleted: true}` |

`Vehicle` = `{id, registration_no, vehicle_type: bus|van|car|other, model, capacity, driver_id,
driver_name, helper_id, helper_name, status, assigned_students}`. `driver_id`/`helper_id` are **staff**
ids from `/school-admin/staff` (same school).

`Route` = `{id, name, description, vehicle_id, vehicle_label, capacity, assigned_students, status, stops[]}`.

Rules:
- Vehicles: registration number unique per school ignoring spaces/hyphens (409); capacity 1–100 and not
  below the students currently riding it; driver ≠ helper; a staff member drives/helps on one active
  vehicle at a time (409). Deactivating a vehicle that has riders → 409.
- Routes: name unique (409); vehicle must be active. Moving a route to a vehicle whose seats would be
  exceeded → 409.
- Stops: name unique within the route; `stop_order ≥ 1` and unique within the route; times `HH:MM`.
  Removing a stop where students board → 409.
- Assignments: one active assignment per student (409); the stop must belong to the route (422); the
  route must be active; **capacity**: active riders on all routes sharing the vehicle must not exceed its
  capacity → `409 {"detail": "The vehicle on this route has 40 seats and 40 are taken."}`.
