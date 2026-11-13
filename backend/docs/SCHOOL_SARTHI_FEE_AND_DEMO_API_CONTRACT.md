# SchoolSarthi: Fee and Request Demo API contract (for Vishal)

Backend branch `fix/fee-installment-demo` · 2026-11-13. Every path, field and example comes from the code and was produced by running the services. Nothing is guessed.

**Status legend:**
- **EXISTING**: unchanged.
- **MODIFIED**: same path; the behaviour or fields changed, and every field change is additive.
- **NEW**: new route.
- **MISSING**: doesn't exist; needs separate approval.

## 0. Common rules

| | |
|---|---|
| Base | `/api/v1/school-admin` (fees) · `/api/v1/public` (public enquiry) |
| Auth (fees) | `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`. Role `school_admin` with permission `fees.manage`. |
| Branch | Optional `X-Branch-Id: <id>`. It's a hint only; the server checks the admin may use that branch. Rows from another branch return `404`. |
| Body | `Content-Type: application/json` |
| Money | JSON numbers in rupees with at most 2 decimals. The server computes in `Decimal`, rounds `ROUND_HALF_UP` to the paisa, and returns floats (e.g. `699.9`). Show them with `toFixed(2)`. |

**Error shapes. Handle both:**
- Schema validation (FastAPI) → `422 {"detail": [{"loc": ["body","amount"], "msg": "...", "type": "..."}]}`
- Business rule → `4xx {"detail": "human readable text"}`. Show `detail` as it is.
- `401` no or invalid token · `403` `"Permission denied"` (no `fees.manage`) or school-access text · `404` `"Record not found"` (also for another school's or branch's row) · `409` duplicate or conflict.

## 1. Fee structures

### POST `/fee-structures` (MODIFIED)
```json
{
  "name": "Class 5 annual fees 2026-27",
  "session_year_id": 1,
  "class_id": 5,
  "status": 1,
  "amounts": [{"fee_type_id": 1, "amount": 1200}],
  "installments": [
    {"name": "Installment 1", "due_date": "2026-04-15", "amount": 600},
    {"name": "Installment 2", "due_date": "2026-10-15", "amount": 600}
  ]
}
```
`items` is accepted as an alias of `amounts`. `installments` is optional. `201` response:
```json
{
  "id": 1, "school_id": 1, "branch_id": null, "name": "Class 5 annual fees 2026-27",
  "session_year_id": 1, "class_id": 5, "status": 1, "deleted_at": null,
  "created_at": "2026-11-13T06:00:54.483233", "updated_at": "2026-11-13T06:00:54.483233",
  "amounts": [{"id": 1, "school_id": 1, "branch_id": null, "structure_id": 1, "fee_type_id": 1, "amount": 1200.0,
               "deleted_at": null, "created_at": "…", "updated_at": "…"}],
  "total": 1200.0,
  "installments": [
    {"id": 1, "structure_id": 1, "name": "Installment 1", "due_date": "2026-04-15", "amount": 600.0, "sort_order": 0, "allocated": 0.0, "outstanding": 600.0},
    {"id": 2, "structure_id": 1, "name": "Installment 2", "due_date": "2026-10-15", "amount": 600.0, "sort_order": 1, "allocated": 0.0, "outstanding": 600.0}
  ],
  "installments_total": 1200.0,
  "installments_match_total": true,
  "class_assignment": {"eligible_students": 2, "created": 2, "already_assigned": 0}
}
```
**What changed:**
- **Class fees now reach students.** A structure created with a `class_id` and `status: 1` is assigned in the same transaction to every **enrolled** student of that class in that session. Enrolled means `enrollment_status` is `admitted` or `active` and the student isn't deleted. Inactive, transferred and deleted students, other sessions and other branches are skipped. `class_assignment` reports the counts, and it appears only on create when this happened.
- `installments_total` and `installments_match_total` are new on **every** structure response (list, get, create, patch).

**Validation:**
- `name` and `session_year_id` are required.
- The session and class must belong to the school (422).
- `amounts` must be non-empty; each needs `fee_type_id` and `amount > 0`.
- A fee type can appear only once per structure (409).

### PATCH `/fee-structures/{id}` (MODIFIED)
Body: any of `name`, `status`, `amounts`, `installments`. `session_year_id` and `class_id` **can't be changed** here; they're silently ignored. Changed amounts now keep the structure's `branch_id`.

> **Frontend change needed.** Today the app PATCHes `amounts`, then PUTs installments in a second call. If the second call fails, the schedule no longer adds up to the total. **Send `installments` in the same PATCH whenever the amounts change**, so both are saved in one transaction. If you don't, the response shows `installments_match_total: false` and `installments_total` ≠ `total`. Show a warning and ask the admin to fix the schedule.

### GET `/fee-structures?page=&page_size=` · GET `/fee-structures/{id}` · DELETE `/fee-structures/{id}` (EXISTING, with the new fields above)
`page_size` ≤ 50. The list returns `{items, total, page, page_size}`.

> In the structure responses, `installments[].allocated` / `outstanding` are **totals across all students** of the structure. Don't show them as one student's dues; use §5 for that.

## 2. Installments

### GET `/fee-structures/{structure_id}/installments` (EXISTING)
`{"items": [FeeInstallment…], "total": 2}`. Same fields as above.

### PUT `/fee-structures/{structure_id}/installments` (MODIFIED)
```json
{"installments": [
  {"name": "Installment 1", "due_date": "2026-04-15", "amount": 600, "sort_order": 0},
  {"name": "Installment 2", "due_date": "2026-10-15", "amount": 600, "sort_order": 1}
]}
```
`items` is an alias. The whole schedule is replaced. Returns the same body as GET.

**Business rules (verified by tests):**
- **The sum must equal the structure total, to the paisa.** Otherwise you get `422 "installment amounts must sum to structure total (1200.00); got 1199.99"`. Money is never created or lost.
- Amounts are rounded half-up to 2 decimals before checking: `600.005` becomes `600.01`.
- Each amount must be > 0. `name` and `due_date` (`YYYY-MM-DD`) are required.
- **Labels:**
  - In a single-row schedule, "Full payment" is kept.
  - In a schedule with more than one row, a row named "Full payment" (any case or spacing) is saved as `"Installment N"`, where N is its position.
  - Other names ("Term 1", "April") are kept as entered.
- `409 "Cannot replace installments that already have successful payment allocations"` once any student has paid towards the schedule.

> **Frontend bug to fix** (`components/ops/fees.tsx:158`). `splitInto` keeps `list[index]?.name`, so splitting the default "Full payment" row into 2 gives "Full payment" + "Installment 2". The server corrects that now, but name the rows `Installment ${i+1}` when `count > 1` (and "Full payment" for 1) so the preview matches what's saved.
>
> **Presets:** the server has no preset generator. `splitEvenly` in `lib/ops/fees-math.ts` (floor each to the paisa, last row takes the remainder) is correct; the server validates the result. Verified: 1200/2 → 600+600; 1000/3 → 333.33+333.33+333.34; 1000.01/4 → 250×3+250.01; 1200/12 → 100×12.

## 3. Assigning fees

### POST `/fee-structures/{id}/assign-class` (NEW)
No body. It assigns the structure to every enrolled student of its class who doesn't have it yet. Run it **after new admissions**, or to backfill structures created before this change.
```json
{"structure_id": 1, "class_id": 5, "eligible_students": 3, "created": 1, "already_assigned": 2}
```
- It's idempotent and safe to repeat.
- A concurrent run can't create duplicates: the unique index refuses the second insert, and the server retries once.
- Errors:
  - `422 "This fee structure is not linked to a class"`
  - `422 "This fee structure is inactive"`
  - `404`: the structure belongs to another school or branch
  - `409 "Fees are being assigned to this class; try again"` (rare race)

Suggested UI: an "Assign to class" button on a class structure that shows `created` / `already_assigned`.

### POST `/fee-assignments` (MODIFIED): student-specific fee
```json
{"structure_id": 2, "student_id": 101}
```
`201` response:
```json
{"id": 3, "school_id": 1, "branch_id": null, "structure_id": 2, "student_id": 101, "deleted_at": null, "created_at": "…", "updated_at": "…"}
```
**Business rules:**
- A student-specific assignment is an **additional** fee (e.g. transport). It doesn't override or change the class fee. To reduce what a student pays, use a concession (§4). The student owes the sum of all their assignments.
- `409 "This student already has these fees"` when an active assignment exists, including when the student already pays it through their class. The DB unique index enforces this even for two simultaneous requests (verified on PostgreSQL). Your list-then-POST pre-check can stay, but the 409 is the source of truth.
- `422 "student is not currently enrolled"` for inactive or transferred students.
- `422 "structure_id must belong to the active branch"` / `"student_id must belong to the active branch"`.
- `404` for an unknown, deleted or other-school student or structure.
- A student can be reassigned after `DELETE /fee-assignments/{id}`.

### GET `/fee-assignments?student_id=&structure_id=&page=&page_size=` · DELETE `/fee-assignments/{id}` (EXISTING)

## 4. Concessions and discounts

### POST `/fee-concessions` (MODIFIED)
```json
{"student_id": 102, "structure_id": 1, "kind": "amount", "value": 200, "reason": "Sibling discount"}
```
`kind` is `"amount"` (fixed rupees) or `"percent"`. `201` response:
```json
{"id": 1, "school_id": 1, "branch_id": null, "student_id": 102, "structure_id": 1, "kind": "amount", "value": 200.0, "reason": "Sibling discount", "deleted_at": null, "created_at": "…", "updated_at": "…"}
```
**Calculation (one Decimal implementation, used by collect, outstanding and the portal):**
- `concession = percent ? round_half_up(total × value / 100) : value`, capped at the total.
- `payable = total − concession`, never below 0.
- `balance = payable − sum(successful payments)`.

Example: total 1000.05 at 12.5% gives a concession of 125.01 and payable 875.04.

**Validation:**
- `value > 0`.
- `percent` ≤ 100 (100 = full exemption, payable 0).
- **NEW:** a fixed `amount` above the structure total → `422 "concession amount cannot exceed the fee structure total (1200.00)"`. An amount equal to the total is allowed.
- **NEW:** a concession that would make payable less than what's already paid → `422 "concession would make the payable amount (1000.00) less than what has already been paid (1100.00)"`.
- **NEW:** a second active concession for the same student and structure → `409 "This student already has a concession on these fees"`. Delete the old one first.
- `reason` is required.

### GET `/fee-concessions?page=&page_size=` · DELETE `/fee-concessions/{id}` (EXISTING)
The list has no `student_id` or `structure_id` filter.

## 5. Collecting fees and balances

### POST `/fees/collect` (MODIFIED)
```json
{"assignment_id": 1, "amount": 600, "method": "cash", "reference": null, "remarks": null, "paid_on": "2026-11-13", "idempotency_key": "9b1c-01"}
```
`201` response:
```json
{"id": 1, "school_id": 1, "branch_id": null, "assignment_id": 1, "student_id": 101, "amount": 600.0, "method": "cash",
 "receipt_no": "RCPT-20261113060054-1-6ED4", "reference": null, "remarks": null, "paid_on": "2026-11-13", "status": "success",
 "idempotency_key": "9b1c-01", "cancelled_at": null, "cancel_reason": null, "deleted_at": null, "created_at": "…", "updated_at": "…"}
```
**What changed:**
- **Overpaying is impossible:** `amount > balance` returns `422 "amount exceeds outstanding balance"`. The exact balance is accepted.
- The student's assignment row is locked while the balance is checked, so two counters collecting at once can't both pass.
- The default `receipt_no` gained a 4-character random suffix. Two collections in the same second for one student used to fail with a 409.
- **Per-student installments.** A payment fills **this student's** installments, earliest due date first. Previously, one student's payment marked installment 1 as paid for the whole class.

Reusing an `idempotency_key` returns the original payment unchanged. Send a new key per attempt and keep it on retries.

### GET `/fees/outstanding?page=&page_size=` (EXISTING; maths now Decimal)
```json
{"items": [{"assignment_id": 2, "student_id": 102, "structure_id": 1, "payable": 1000.0, "concession": 200.0, "paid": 0.0, "balance": 1000.0}],
 "total": 1, "page": 1, "page_size": 20, "summary": {"payable": 1000.0, "collected": 0.0, "outstanding": 1000.0}}
```
Only assignments with a balance > 0 are listed.

### Per-student dues for the School Admin (MISSING)
There's no `GET /school-admin/students/{id}/fees` (the fee contract's §7). The correct per-student, per-installment calculation exists as `student_fee_balance` and is served to students and parents at `GET /api/student/fees/balance`. Exposing it to the School Admin is one small read route, but it's a new endpoint and needs approval. Until then, keep building dues from `/fee-assignments`, `/fee-concessions` and `/fee-payments` with the formula in §4.

## 6. Public enquiry and Request Demo

### POST `/api/v1/public/schools/{code}/contact-inquiries` (MODIFIED: stricter validation)
**No login.** It's for the **public website of a school that is already on SchoolSarthi**. The school is found by its `code` and must be active. The School Admin reads these at `GET /school-admin/contact-inquiries`.
```json
{"name": "Asha Rao", "email": "asha@example.org", "phone": "+91 98765 43210", "subject": "Admissions", "message": "Please call me back."}
```
`201` response:
```json
{"id": 1, "school_id": 7, "name": "Asha Rao", "email": "asha@example.org", "phone": "+91 98765 43210", "subject": "Admissions",
 "message": "Please call me back.", "status": "new", "source": "public", "created_at": "…", "updated_at": "…"}
```

| Field | Rule |
|---|---|
| `name` | required, 1–120 chars, trimmed, no control characters |
| `email` | required, valid email, ≤ 254 |
| `phone` | optional; digits, spaces, `+ ( ) -`, 7–15 digits, ≤ 20 chars |
| `subject` | required, 1–200 chars |
| `message` | required, 1–5000 chars, no control characters except newline and tab |
| anything else | `422` (`extra="forbid"`; e.g. a `school_id` in the body is refused) |

**Errors:**
- `404 "School not found"` for an unknown or inactive code.
- `429 "Too many attempts. Try again later."` with `Retry-After`: 10 enquiries per IP per hour. This has its own bucket now; it used to share the forgot-password limit.

HTML is stored as plain text. **Always render enquiry text escaped** (React does this by default; never use `dangerouslySetInnerHTML`).

### Request Demo (MISSING: needs separate approval)
There's **no** platform Request Demo API. The marketing "Request demo" button links to `/login` (`components/marketing/Hero.tsx:27`). The endpoint above can't be used for it, because a prospect school has no `code` and the enquiry would land in some other school's inbox. See the QA report §3 for the proposed contract and estimate. **Don't wire a demo form until that's approved.**
