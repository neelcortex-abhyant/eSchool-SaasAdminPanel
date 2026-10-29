# School Admin ERP — Field-Level API Audit (Modules 1–5)

**Date:** 2026-10-29 (revised same day — OpenAPI fix wave)  
**Starting reference:** [`SCHOOL_ADMIN_ERP_MODULES_NOTES.md`](./SCHOOL_ADMIN_ERP_MODULES_NOTES.md)  
**OpenAPI source:** `app.openapi()` from live `app.main:app` import.  
**In-scope operation count:** **71** (51 distinct paths).  
**Safety:** No Neon migrate. No Render deploy. No `admin-web`. Migration head remains `20261029_0041`.

### Classification legend

| Label | Meaning |
|-------|---------|
| **Verified fact** | Confirmed in route handler + service (and OpenAPI where relevant) |
| **Confirmed defect** | Was wrong vs handler/service; listed as open or **fixed** |
| **Unverified** | Not exercised against an isolated DB |
| **Blocker / out of scope / missing** | Product decision, external integration, or unimplemented deliverable |

---

## 0. Fix wave summary (this revision)

### Root cause of Swagger `additionalProp1`

**Verified:** In-scope write routes used `class Body(BaseModel): model_config = ConfigDict(extra="allow")` with **no properties**. Generated OpenAPI was:

```json
{ "properties": {}, "additionalProperties": true, "type": "object", "title": "Body" }
```

Swagger UI renders that as `{"additionalProp1": {}}`. This was **not** a separate FastAPI bug — it was an empty catch-all body model.

### Fixes applied (code)

| Fix | Detail |
|-----|--------|
| Typed request schemas | New [`app/schemas/v1/school_admin_erp.py`](../app/schemas/v1/school_admin_erp.py) |
| Wired ERP write routes | [`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py) (module 1–4 writes), [`school_admin_erp.py`](../app/api/v1/school_admin_erp.py), [`staff_transport.py`](../app/api/staff_transport.py) |
| PDF OpenAPI media type | `responses={200: {content: {application/pdf: …}}}` on 6 PDF GETs |
| Attendance `event_type` | `Literal["board","drop"]` in OpenAPI |
| Band overlap validation | `_replace_bands` rejects overlapping inclusive ranges (**422**) |

Non-ERP `Body` usages elsewhere in `school_admin_mgmt.py` were **left unchanged** (out of scope).

### Counts

| Metric | Value |
|--------|-------|
| Endpoints audited | **71** |
| Generic request bodies remaining | **0** |
| PDF media-type defects remaining | **0** |
| JSON response schemas without properties | **0** |
| Attendance enum defects remaining | **0** |
| DB tests | **Skipped** (`TEST_DATABASE_URL` empty) |

### Offline tests executed (latest)

```text
python -m pytest --noconftest tests_offline/test_erp_openapi_schemas.py \
  tests_offline/test_erp_wave_parity.py \
  tests/v1/test_school_admin_erp_routes_registered.py -q
→ 16 passed

python -m pytest --noconftest tests_offline/ \
  tests/v1/test_school_admin_erp_routes_registered.py \
  tests/v1/test_modules_orm_migration_parity.py \
  tests/v1/test_academic_schema.py -q
→ 43 passed
```

---

## 0b. Requirement → coverage matrix

| Requirement area | Coverage | Notes |
|------------------|----------|-------|
| **M1** Grading CRUD + bands | **Full** (API) | Overlap validation now enforced |
| M1 Pass/fail from scale + processed results | **Full** | Reuses offline `passed` + letter bands; no invented marks |
| M1 Report generate / list / get / PDF | **Full** | Admin PDF not publish-gated |
| M1 Student/parent published reads + PDF | **Full** | `Exam.publish` gate |
| M1 Teacher report-card APIs | **Missing** | No teacher portal RC routes |
| M1 Explicit exam↔scale association resource | **Partial** | Scale chosen at generate time only |
| M1 Full 0–100 coverage enforcement | **Missing** | Overlap blocked; full coverage not required by service |
| **M2** Fee types / structures / amounts | **Full** | |
| M2 Installments sum = total (INR 2dp) | **Full** | |
| M2 Assignments / concessions | **Partial** | No concession PATCH; no compulsory/optional fee flag |
| M2 Duplicate fee-type category rule | **Missing** | Category free string; name uniqueness not enforced in service |
| M2 Overdue-by-due-date report | **Partial** | Outstanding exists; not installment-overdue filtered |
| M2 Structure edit preserves paid history | **Partial** | Amounts replaceable; installments **409** if allocated |
| **M3** Collect / allocate / overpay block | **Full** | |
| M3 Idempotency / receipt / PDF / cancel audit | **Full** | Cancel ≠ refund |
| M3 Collection report | **Full** | |
| M3 School fee gateway | **Out of scope** | |
| **M4** Vehicles / routes / stops / assignments | **Full** (core) | No stop PATCH; no vehicle_type field |
| M4 Driver/helper + capacity | **Full** | |
| M4 Conflicting driver multi-vehicle | **Missing** | Not enforced |
| **M5** Trips / GPS / attendance / parent poll | **Full** (HTTP) | |
| M5 WebSocket / GPS purge cron / hardware | **Out of scope / blocker** | |

---

## 1. Methodology and commands

### Commands run

```text
cd backend
python -m pytest --noconftest tests_offline/test_erp_openapi_schemas.py ...  # see §0
python -m pytest --noconftest tests_offline/ ...                            # 39 passed
# app.openapi() inspected via tests_offline/test_erp_openapi_schemas.py
```

### Database-dependent tests

`TEST_DATABASE_URL` is empty in local `.env`. **Layer C (DB integration) was skipped.** Runtime tenancy and PDF bytes were not HTTP-exercised against a database. Auth/permission constants and ownership checks were verified from source.

### Auth legend (verified)

| Surface | Dependency | Permission / role |
|---------|------------|-------------------|
| School Admin ERP | `require_school_permission(...)` + Bearer | `exams.manage`, `fees.manage`, `school.manage`, or `reports.view` as noted per route |
| Staff transport | `require_staff_user` | Staff-class roles (`is_staff`); school from tenant |
| Student portal | `require_student_user` | User must have `Student` row in school |
| Parent portal | `require_guardian_user` | User must have Guardian role; child access via guardian link |

School Admin `school_id` always comes from `auth.user.school_id` (never from body). Bodies strip `school_id` / `id` / timestamps via `sanitize_body` (`_WRITE_BLOCKLIST`).

### Common error shapes (verified)

| Status | Shape | Source |
|--------|-------|--------|
| 401 | Auth failure (dependency) | `deps` / school-admin auth |
| 403 | Missing permission or staff profile | `require_school_permission`, `AcademicError(403, …)` |
| 404 | `{"detail": "Record not found"}` or similar | `_owned` / portal gates |
| 409 | Conflict string detail | capacity, duplicate attendance, installment replace, default scale delete |
| 422 | `{"detail": "<sentence>"}` from `AcademicError`, or FastAPI validation list for typed Pydantic bodies | `_run` / Pydantic |

List envelope (verified in `_list_active` / `_envelope`): `{ "items": [...], "total": n, "page": p, "page_size": s }` unless a service returns a custom dict (noted per endpoint).

---

## 2. Endpoint inventory summary (71)

### Module 1 — Report cards and grading (15)

| Method | Path | Auth | OpenAPI body |
|--------|------|------|--------------|
| GET | `/api/v1/school-admin/grading-scales` | `exams.manage` | none |
| POST | `/api/v1/school-admin/grading-scales` | `exams.manage` | `GradingScaleCreateBody` |
| GET | `/api/v1/school-admin/grading-scales/{scale_id}` | `exams.manage` | none |
| PATCH | `/api/v1/school-admin/grading-scales/{scale_id}` | `exams.manage` | `GradingScalePatchBody` |
| DELETE | `/api/v1/school-admin/grading-scales/{scale_id}` | `exams.manage` | none |
| GET | `/api/v1/school-admin/report-cards` | `exams.manage` | none |
| POST | `/api/v1/school-admin/report-cards` | `exams.manage` | `ReportCardGenerateBody` |
| GET | `/api/v1/school-admin/report-cards/{report_id}` | `exams.manage` | none |
| GET | `/api/v1/school-admin/report-cards/{report_id}/pdf` | `exams.manage` | PDF response |
| GET | `/api/student/report-cards` | student | none |
| GET | `/api/student/report-cards/{report_id}` | student | none |
| GET | `/api/student/report-cards/{report_id}/pdf` | student | PDF response |
| GET | `/api/parent/children/{student_id}/report-cards` | guardian | none |
| GET | `/api/parent/children/{student_id}/report-cards/{report_id}` | guardian | none |
| GET | `/api/parent/children/{student_id}/report-cards/{report_id}/pdf` | guardian | PDF response |

### Module 2 — Fee structures and installments (17)

| Method | Path | Auth | OpenAPI body |
|--------|------|------|--------------|
| GET/POST | `/api/v1/school-admin/fee-types` | `fees.manage` | POST `FeeTypeCreateBody` |
| PATCH/DELETE | `/api/v1/school-admin/fee-types/{row_id}` | `fees.manage` | PATCH `FeeTypePatchBody` |
| GET/POST | `/api/v1/school-admin/fee-structures` | `fees.manage` | POST `FeeStructureCreateBody` |
| GET/PATCH/DELETE | `/api/v1/school-admin/fee-structures/{row_id}` | `fees.manage` | PATCH `FeeStructurePatchBody` |
| GET/PUT | `/api/v1/school-admin/fee-structures/{structure_id}/installments` | `fees.manage` | PUT `FeeInstallmentsPutBody` |
| GET/POST | `/api/v1/school-admin/fee-assignments` | `fees.manage` | POST `FeeAssignmentCreateBody` |
| DELETE | `/api/v1/school-admin/fee-assignments/{row_id}` | `fees.manage` | none |
| GET/POST | `/api/v1/school-admin/fee-concessions` | `fees.manage` | POST `FeeConcessionCreateBody` |
| DELETE | `/api/v1/school-admin/fee-concessions/{row_id}` | `fees.manage` | none |

### Module 3 — Fee collection, allocations, receipts, reports (13)

| Method | Path | Auth | OpenAPI body |
|--------|------|------|--------------|
| GET | `/api/v1/school-admin/fee-payments` | `fees.manage` | none |
| GET | `/api/v1/school-admin/fees/outstanding` | `fees.manage` | none |
| POST | `/api/v1/school-admin/fees/collect` | `fees.manage` | `FeeCollectBody` |
| GET | `/api/v1/school-admin/fee-payments/{payment_id}/receipt` | `fees.manage` | none |
| GET | `/api/v1/school-admin/fee-payments/{payment_id}/receipt/pdf` | `fees.manage` | PDF response |
| POST | `/api/v1/school-admin/fee-payments/{payment_id}/cancel` | `fees.manage` | `FeePaymentCancelBody` |
| GET | `/api/v1/school-admin/fees/collection-report` | `fees.manage` | none |
| GET | `/api/student/fees/balance` | student | none |
| GET | `/api/student/fees/payments` | student | none |
| GET | `/api/student/fees/payments/{payment_id}/receipt/pdf` | student | PDF response |
| GET | `/api/parent/children/{student_id}/fees/balance` | guardian | none |
| GET | `/api/parent/children/{student_id}/fees/payments` | guardian | none |
| GET | `/api/parent/children/{student_id}/fees/payments/{payment_id}/receipt/pdf` | guardian | PDF response |

### Module 4 — Transport management (14)

| Method | Path | Auth | OpenAPI body |
|--------|------|------|--------------|
| GET/POST | `/api/v1/school-admin/vehicles` | `school.manage` | POST `VehicleCreateBody` |
| PATCH/DELETE | `/api/v1/school-admin/vehicles/{row_id}` | `school.manage` | PATCH `VehiclePatchBody` |
| GET/POST | `/api/v1/school-admin/transport-routes` | `school.manage` | POST `TransportRouteCreateBody` |
| PATCH/DELETE | `/api/v1/school-admin/transport-routes/{row_id}` | `school.manage` | PATCH `TransportRoutePatchBody` |
| GET/POST | `/api/v1/school-admin/transport-stops` | `school.manage` | POST `TransportStopCreateBody` |
| DELETE | `/api/v1/school-admin/transport-stops/{row_id}` | `school.manage` | none |
| GET/POST | `/api/v1/school-admin/student-transport-assignments` | `school.manage` | POST `StudentTransportAssignmentCreateBody` |
| DELETE | `/api/v1/school-admin/student-transport-assignments/{row_id}` | `school.manage` | none |

### Module 5 — Trips, GPS, attendance, portal live (12)

| Method | Path | Auth | OpenAPI body |
|--------|------|------|--------------|
| GET/POST | `/api/v1/school-admin/transport-trips` | `school.manage` | POST `TransportTripCreateBody` |
| POST | `/api/v1/school-admin/transport-trips/{trip_id}/start` | `school.manage` | none |
| POST | `/api/v1/school-admin/transport-trips/{trip_id}/complete` | `school.manage` | none |
| POST | `/api/v1/school-admin/transport-trips/{trip_id}/gps` | `school.manage` | `TransportGpsBody` |
| POST/GET | `/api/v1/school-admin/transport-trips/{trip_id}/attendance` | `school.manage` | POST `TransportAttendanceBody` |
| GET | `/api/v1/school-admin/transport/reports/trips` | `reports.view` | none |
| GET | `/api/staff/transport/my-trips` | staff | none |
| POST | `/api/staff/transport/trips/{trip_id}/gps` | staff | `TransportGpsBody` |
| POST | `/api/staff/transport/trips/{trip_id}/attendance` | staff | `TransportAttendanceBody` |
| GET | `/api/parent/children/{student_id}/transport/live` | guardian | none |

---

## 3. OpenAPI defects — status after fix wave

| # | Defect | Status | Notes |
|---|--------|--------|-------|
| D1 | Empty `Body` → Swagger `additionalProp1` on 18 ERP writes | **Fixed** | 23 typed write bodies; **0** generic `Body` on ERP ops |
| D2 | PDF `200` documented as `application/json` | **Fixed** | **6/6** PDF routes declare `application/pdf` |
| D3 | JSON response property schemas absent | **Fixed** | `responses={code: {"model": …}}` via `school_admin_erp_responses.py` — **65/65** JSON ops have property schemas (docs only; no runtime `response_model` filtering) |
| D4 | `event_type` missing enum | **Fixed** | `Literal["board","drop"]` + case-normalization validator |
| D5 | Required fields missing from OpenAPI | **Fixed** with D1 | e.g. collect requires `assignment_id`,`amount` |

### Verified current counts (`app.openapi()`, 2026-10-29 re-check)

| Check | Count |
|-------|-------|
| In-scope operations | 71 |
| Generic empty request bodies | **0** |
| Typed write bodies | **23** |
| PDF media type OK | **6** |
| Attendance enum OK | **2** |
| JSON responses with properties | **65** (all non-PDF JSON ops) |

**Regression tests:** `tests_offline/test_erp_openapi_schemas.py` (request bodies, PDF media types, attendance enum + case norm, sample response `$ref` properties).

---

## 4. Common response field sources

### `_row_dict` (verified)

Serializes **all SQLAlchemy columns** on the model row (ISO dates/datetimes, float for `Decimal`, `HH:MM:SS` for times). Soft-delete response: `{ "id", "deleted": true }`.

### Admin report card row (mgmt `_row_dict`) vs portal `_report_dict`

| Field | Admin `GET /report-cards/{id}` | Portal |
|-------|--------------------------------|--------|
| Column dump including `subjects_json` string | Yes | No |
| `subjects` parsed JSON | No | Yes |
| `exam_name`, `student_name` | No | Yes |
| `percentage`, `letter_grade`, `passed` | Yes | Yes |

---

# Module 1 — Report cards and grading

**Routes:** [`school_admin_mgmt.py`](../app/api/v1/school_admin_mgmt.py), [`school_admin_erp.py`](../app/api/v1/school_admin_erp.py), [`student_erp_reads.py`](../app/api/student_erp_reads.py)  
**Services:** [`school_academic_mgmt.py`](../app/services/v1/school_academic_mgmt.py), [`school_erp_report_cards.py`](../app/services/v1/school_erp_report_cards.py)

### GET `/api/v1/school-admin/grading-scales`

| | |
|--|--|
| Purpose | Paginated grading scales with nested `bands` |
| Auth | Bearer + `exams.manage` |
| Query | `page` int default 1 ≥1; `page_size` int default 20 1..50 |
| Response 200 | Envelope of `_scale_item` |
| Tenant | `school_id` filter |

**Response item fields (verified):** `id`, `school_id`, `name`, `description`, `is_default`, `status`, `deleted_at`, `created_at`, `updated_at`, `bands[]` with `id`, `letter`, `min_percent`, `max_percent`, `grade_point`, `remark`, `is_pass`, `sort_order`.

### POST `/api/v1/school-admin/grading-scales` — schema `GradingScaleCreateBody` (**D1 fixed**)

| Field | Type | Required | Default | Constraints (service) | Description |
|-------|------|----------|---------|----------------------|-------------|
| `name` | string | **yes** | — | non-empty trim | Scale name |
| `description` | string\|null | no | null | — | |
| `is_default` | bool\|int\|string | no | false | truthy → clears other defaults | |
| `status` | int | no | `1` | — | |
| `bands` or `ranges` | array | **yes** (non-empty) | — | each object; **no overlapping** inclusive ranges | Grade bands |

**Band item fields**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `letter` or `grade` | string | **yes** | — | non-empty |
| `min_percent` | number | **yes** | — | with max: `0 ≤ min ≤ max ≤ 100` |
| `max_percent` | number | **yes** | — | |
| `grade_point` | number\|null | no | null | |
| `remark` | string\|null | no | null | truncated to 255 |
| `is_pass` | bool\|int\|string | no | true | |
| `sort_order` | int | no | index | |

**Example (service-supported, not OpenAPI):**

```json
{
  "name": "CBSE 9-point",
  "is_default": true,
  "bands": [
    {"letter": "A1", "min_percent": 91, "max_percent": 100, "grade_point": 10, "is_pass": true},
    {"letter": "E", "min_percent": 0, "max_percent": 32, "is_pass": false}
  ]
}
```

**Status:** 201 + scale item; 422 missing name/bands/overlap; OpenAPI lists properties.

### GET `/api/v1/school-admin/grading-scales/{scale_id}`

Path `scale_id` int. 200 `_scale_item`; 404 cross-school/missing.

### PATCH `/api/v1/school-admin/grading-scales/{scale_id}` — schema `GradingScalePatchBody` (**D1 fixed**)

Partial: `name`, `description`, `status`, `is_default`, `bands`/`ranges` (same band rules if present).

### DELETE `/api/v1/school-admin/grading-scales/{scale_id}`

Soft-delete scale + bands. **409** if `is_default`. Response `{id, deleted:true}`.

### GET `/api/v1/school-admin/report-cards`

Query: `page`, `page_size`, optional `exam_id`≥1, `student_id`≥1. Envelope of report-card `_row_dict`.

### POST `/api/v1/school-admin/report-cards` — **D1**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `exam_id` | int | **yes** | — | owned exam; must have offline results |
| `grading_scale_id` | int\|null | no | school default scale | owned if set |

**Example:** `{"exam_id": 12, "grading_scale_id": 3}`  
**Response 201:** `{exam_id, created, items[], total}`  
**422:** missing exam_id; no processed offline results.

### GET `/api/v1/school-admin/report-cards/{report_id}`

200 admin `_row_dict`. No `Exam.publish` gate (**verified fact** — admin can read unpublished).

### GET `/api/v1/school-admin/report-cards/{report_id}/pdf`

Purpose: FPDF download. Headers: `Content-Disposition` attachment, `Cache-Control: private, no-store`.  
OpenAPI `200` documents `application/pdf` (**D2 fixed**).  
No publish gate for admin PDF (**verified**).

### Portal report-card GETs

| Endpoint | Extra checks |
|----------|--------------|
| `GET /api/student/report-cards` | Own student; only `Exam.publish == 1` |
| `GET /api/student/report-cards/{report_id}` | Own + publish |
| `GET /api/student/report-cards/{report_id}/pdf` | Same + PDF (**D2**) |
| Parent list/get/pdf | Guardian child; path `student_id` must match report’s student; publish |

**Portal JSON fields (verified `_report_dict`):** `id`, `school_id`, `exam_id`, `exam_name`, `student_id`, `student_name`, `grading_scale_id`, `percentage`, `letter_grade`, `passed`, `subjects`, `generated_at`.

Unpublished → **404** “Record not found” (not 403).

---

# Module 2 — Fee structures and installments

**Services:** `school_academic_mgmt.py`, `school_erp_fees.py`

### Fee types

#### POST `/fee-types` — **D1**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `name` | string | **yes** | — | non-empty |
| `category` | string | no | `"other"` | stored as given (no enum enforced in service) |
| `description` | any | no | null | |
| `status` | int | no | `1` | |

#### PATCH `/fee-types/{row_id}` — **D1** — partial same fields.  
#### GET list / DELETE soft-delete — standard.

### Fee structures

#### POST `/fee-structures` — **D1**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `name` | string | **yes** | — | |
| `session_year_id` | int | **yes** | — | same school |
| `class_id` | int\|null | no | null | same school if set |
| `status` | int | no | `1` | |
| `amounts` or `items` | array | **yes** non-empty | — | |
| `installments` | array\|omit | no | omit | if present, must sum to structure total |

**Amount item:** `fee_type_id` int required (>0), `amount` number required (>0).

**Installment item (if provided):** see PUT installments below.

**Example:**

```json
{
  "name": "Class 5 annual 2026-27",
  "session_year_id": 2,
  "class_id": 3,
  "amounts": [{"fee_type_id": 1, "amount": 36000}, {"fee_type_id": 3, "amount": 2000}],
  "installments": [
    {"name": "Term 1", "due_date": "2026-04-15", "amount": 19000},
    {"name": "Term 2", "due_date": "2026-10-15", "amount": 19000}
  ]
}
```

**Response:** `_structure_item` = columns + `amounts[]` + `total` float.

#### PATCH `/fee-structures/{row_id}` — **D1**

May update `name`, `status`, replace `amounts`/`items`. Does **not** auto-update installments in this handler (**verified**).

#### GET/DELETE structure — standard; delete soft-deletes amounts too.

### GET `/fee-structures/{structure_id}/installments`

Auth `fees.manage`. Response:

```json
{
  "items": [
    {
      "id": 1,
      "structure_id": 9,
      "name": "Term 1",
      "due_date": "2026-04-15",
      "amount": 19000.0,
      "sort_order": 0,
      "allocated": 0.0,
      "outstanding": 19000.0
    }
  ],
  "total": 1
}
```

### PUT `/fee-structures/{structure_id}/installments` — **D1**

Route accepts body key `installments` **or** `items` (list).

| Field (each installment) | Type | Required | Constraints |
|--------------------------|------|----------|-------------|
| `name` | string | **yes** | non-empty |
| `due_date` | string date | **yes** | `YYYY-MM-DD` |
| `amount` | number | **yes** | > 0; INR 2dp `ROUND_HALF_UP` |
| `sort_order` | int | no | defaults to index |

**Business rules (verified):**  
- Sum of amounts must equal structure amounts total → else **422**.  
- If any existing installment has allocations > 0 → **409** cannot replace.  
- Empty list → **422**.

**Example:**

```json
{
  "installments": [
    {"name": "Term 1", "due_date": "2026-04-15", "amount": "19000.00", "sort_order": 0},
    {"name": "Term 2", "due_date": "2026-10-15", "amount": "19000.00"}
  ]
}
```

### Fee assignments

#### POST — **D1**

| Field | Required | Constraints |
|-------|----------|-------------|
| `structure_id` | yes | owned |
| `student_id` | yes | owned |

#### GET query: `page`, `page_size`, optional `student_id`, `structure_id`.  
#### DELETE soft-delete.

### Fee concessions

#### POST — **D1**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `student_id` | int | yes | |
| `structure_id` | int | yes | |
| `kind` | string | yes | `percent` \| `amount` |
| `value` | number | yes | > 0; if percent ≤ 100 |
| `reason` | string | yes | non-empty |

---

# Module 3 — Fee collection, allocations, receipts, reports

### GET `/fee-payments`

Query: `page`, `page_size`, optional `student_id`. Envelope of payment `_row_dict` (includes `cancelled_at`, `cancel_reason` columns when present; list filters `deleted_at IS NULL` via `_list_active`).

### GET `/fees/outstanding`

Query: `page`, `page_size`. Returns envelope **plus** `summary: {payable, collected, outstanding}`.  
Item fields: `assignment_id`, `student_id`, `structure_id`, `payable`, `concession`, `paid`, `balance`.  
Only rows with `balance > 0`. Overpay blocked at collect; cancelled payments excluded because `status != success` or soft-deleted (**verified** via `_paid_for_assignment`).

### POST `/fees/collect` — **D1**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `assignment_id` | int | **yes** | — | owned |
| `amount` | number | **yes** | — | > 0; ≤ outstanding (+0.001); INR quantize |
| `method` | string | no | `"cash"` | |
| `receipt_no` | string | no | auto `RCPT-…` | |
| `reference` | string\|null | no | null | |
| `remarks` | string\|null | no | null | |
| `paid_on` | date string | no | today | `YYYY-MM-DD` |
| `idempotency_key` | string\|null | no | null | unique per school if set; replay returns existing |

**Example:**

```json
{
  "assignment_id": 44,
  "amount": 5000,
  "method": "upi",
  "reference": "UPI-883201",
  "paid_on": "2026-10-29",
  "idempotency_key": "collect-44-20261029-a"
}
```

**Behavior (verified):** creates `FeePayment` `status=success`; `allocate_payment` earliest due first; leftover may create allocation with `installment_id=null`. **Overpay → 422.** No school fee gateway.

**Response 201:** payment `_row_dict` (allocations not embedded in collect response — **verified**; use receipt endpoint).

### GET `/fee-payments/{payment_id}/receipt`

Fields: `id`, `receipt_no`, `student_id`, `student_name`, `assignment_id`, `amount`, `method`, `reference`, `remarks`, `paid_on`, `status`, `cancelled_at`, `cancel_reason`, `lines[]` with `allocation_id`, `installment_id`, `installment_name`, `amount`.  
Cancelled payments still readable for audit if `cancelled_at` set (**verified**).

### GET `…/receipt/pdf` — PDF; **D2** OpenAPI media type wrong.

### POST `/fee-payments/{payment_id}/cancel` — typed OpenAPI OK

**CancelBody**

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `reason` | string | **yes** | minLength 1, maxLength 512; `extra=forbid` |

**Example:** `{"reason": "Duplicate entry corrected by accountant"}`  
**Behavior:** status `cancelled`, soft-delete payment + allocations, audit `fee_payment.cancel`. **No refund.** 422 if not success. Response = receipt JSON.

### GET `/fees/collection-report`

| Query | Type | Required | Constraints |
|-------|------|----------|-------------|
| `from_date` | date | **yes** | |
| `to_date` | date | **yes** | ≥ from_date else 422 |
| `class_id` | int\|null | no | ≥1 |

**Response fields:** `from_date`, `to_date`, `class_id`, `payment_count`, `total_collected`, `by_method`, `items[]` (`id`, `receipt_no`, `student_id`, `amount`, `method`, `paid_on`). Success + not deleted only.

### Portal fee reads

| Endpoint | Response |
|----------|----------|
| `…/fees/balance` | `student_id`, `payable`, `paid`, `outstanding`, `assignments[]` with installment breakdown |
| `…/fees/payments` | `{items:[{id,receipt_no,amount,method,paid_on,status}], total}` success only |
| `…/receipt/pdf` | PDF; ownership check; **D2** |

Parent path `student_id` must match payment’s student on PDF (**verified**).

---

# Module 4 — Transport management

**Permission:** `school.manage` for all listed routes.  
**Service:** `school_academic_mgmt` + `school_erp_transport` (driver/helper + capacity).

### Vehicles

#### POST `/vehicles` — **D1**

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `name` | string | **yes** | — | |
| `registration_no` | string | **yes** | — | |
| `capacity` | int\|null | no | null | |
| `status` | int | no | `1` | |
| `driver_staff_id` | int\|null | no | — | same-school `staffs.id` or null |
| `helper_staff_id` | int\|null | no | — | same |

**Response `_vehicle_item`:** `id`, `school_id`, `name`, `registration_no`, `capacity`, `driver_staff_id`, `helper_staff_id`, `status`, `created_at`, `updated_at`.

#### PATCH — **D1** — same fields partial; staff validated when keys present.  
#### GET list / DELETE soft-delete.

### Routes

#### POST — **D1:** `name` required; optional `vehicle_id` (owned), `description`, `status` default 1.  
#### PATCH — **D1:** `name`, `description`, `status`, `vehicle_id` (nullable).  
Response includes nested `stops[]`.

### Stops

#### GET query: `page`, `page_size`, optional `route_id`.  
#### POST — **D1:**

| Field | Required | Constraints |
|-------|----------|-------------|
| `route_id` | yes | owned |
| `name` | yes | |
| `stop_order` | no | default 0 |
| `pickup_time` | no | `HH:MM` or `HH:MM:SS` |
| `drop_time` | no | same |
| `landmark` | no | |

No PATCH stop endpoint (**verified** — only DELETE soft-delete).

### Student transport assignments

#### POST — **D1**

| Field | Required | Constraints |
|-------|----------|-------------|
| `student_id` | yes | owned; unique active assignment per student (DB unique index) |
| `route_id` | yes | owned |
| `stop_id` | no | must belong to route |

**409** if vehicle capacity reached (`assert_route_vehicle_capacity`). Capacity null → no check.

---

# Module 5 — Trips, GPS, attendance, portal live

### Admin trips

#### GET `/transport-trips`

Query: `page`, `page_size`, `status` (alias), `route_id` optional. Envelope of trip dict.

**Trip fields:** `id`, `school_id`, `route_id`, `vehicle_id`, `driver_staff_id`, `status`, `started_at`, `ended_at`, `created_at`, `updated_at`.

#### POST `/transport-trips` — **D1**

| Field | Required | Default / notes |
|-------|----------|-----------------|
| `route_id` | **yes** | owned |
| `vehicle_id` | if route has none | else route’s vehicle |
| `driver_staff_id` | no | defaults to vehicle.driver_staff_id |

Creates `status=scheduled`. **201.**

#### POST `…/start` — scheduled → `in_progress` + `started_at`; else 422.  
#### POST `…/complete` — in_progress → `completed` + `ended_at`; else 422.

**Unverified / not exposed:** `cancel_trip` / `soft_delete_trip` exist in service but **no HTTP routes** in this wave.

#### POST `…/gps` — typed `GpsBody`

| Field | Type | Required | OpenAPI | Service |
|-------|------|----------|---------|---------|
| `lat` | number | yes | yes | float; trip must be `in_progress` |
| `lng` | number | yes | yes | same |

Response: `id`, `trip_id`, `vehicle_id`, `lat`, `lng`, `recorded_at`, `staff_id`, `expires_at` (from `GPS_RETENTION_DAYS` if configured).

#### POST `…/attendance` — typed `AttendanceBody` (**D4** missing enum)

| Field | Type | Required | Service constraints |
|-------|------|----------|---------------------|
| `student_id` | int ≥1 | yes | owned |
| `event_type` | string | yes | `board` \| `drop` (case-normalized) |
| `stop_id` | int\|null ≥1 | no | must belong to trip route |

Rules: duplicate same event → **409**; drop without board → **422**; trip status `in_progress` or `scheduled`.

**Example:** `{"student_id": 101, "event_type": "board", "stop_id": 5}`

#### GET `…/attendance` → `{items, total}` event list.

#### GET `/transport/reports/trips` — auth **`reports.view`**

Query `page`, `page_size`. Envelope; each item adds `gps_points`, `attendance_events` counts. (Service supports `from_dt`/`to_dt` but **route does not expose them** — **verified fact** / docs gap, not OpenAPI empty-body.)

### Staff `/api/staff/transport`

| Endpoint | Notes |
|----------|-------|
| GET `/my-trips` | Trips where `driver_staff_id` = staff profile; 403 if no staff row |
| POST `/trips/{id}/gps` | Driver or vehicle driver/helper; else 403 |
| POST `/trips/{id}/attendance` | Requires staff profile; then same attendance rules |

### Parent live poll

`GET /api/parent/children/{student_id}/transport/live`

Response fields: `student_id`, `assignment` (`id`, `route_id`, `route_name`, `stop_id`, `vehicle_id`) or null, `active_trip` trip dict or null (`in_progress` on child’s route), `latest_gps` `{lat,lng,recorded_at}` or null.  
Guardian-only; non-child → 404. **HTTP poll only** (no WebSocket — blocker).

---

## 5. Preserved business rules (verified)

| Rule | Where |
|------|-------|
| Installments sum = structure total, INR 2dp HALF_UP | `validate_installment_sum` / `inr_quantize` |
| Overpay disabled | `collect_fee` |
| Cancel without refund | `cancel_fee_payment` |
| Installment replace blocked after allocations | **409** |
| Report-card portal gated by `Exam.publish` | `school_erp_report_cards` |
| Admin RC PDF/JSON not publish-gated | admin routes |
| Vehicle capacity on assign | `assert_route_vehicle_capacity` |
| Parent/driver authorization | guardian children / staff assignment checks |
| Legacy payments without allocations still count | `_paid_for_assignment` / notes |
| SaaS Razorpay untouched | out of scope |

---

## 6. Blockers and out of scope (from notes + code)

| Topic | Status |
|-------|--------|
| GPS retention purge cron | Not implemented; optional `expires_at` only |
| Fee refunds / gateway reverse | Cancel only |
| School fee online gateway | Out of scope |
| WebSocket live tracking | Not implemented |
| `admin-web` | Deleted / out of scope for this audit |
| Neon apply of `20261029_0041` | Requires explicit approval |
| Service `cancel_trip` without route | Not in endpoint inventory as HTTP API |

---

## 7. Unverified in this audit

- End-to-end HTTP against isolated Postgres (empty `TEST_DATABASE_URL`).
- Actual PDF byte validity beyond “handler returns `Response(media_type=application/pdf)`”.
- Unique constraint failure messages for duplicate fee assignment / registration (DB-level).
- Exact 401/403 payload strings for every dependency path.

---

## 8. Source file map

| Area | Files |
|------|-------|
| Admin ERP additive | `app/api/v1/school_admin_erp.py` |
| Admin CRUD | `app/api/v1/school_admin_mgmt.py` |
| Staff | `app/api/staff_transport.py` |
| Portal | `app/api/student_erp_reads.py` |
| Fees ERP | `app/services/v1/school_erp_fees.py` |
| Report cards ERP | `app/services/v1/school_erp_report_cards.py` |
| Transport ERP | `app/services/v1/school_erp_transport.py` |
| Shared CRUD | `app/services/v1/school_academic_mgmt.py` |
| Models | `app/models/tables.py` |
| RBAC constants | `app/services/v1/rbac.py` (`exams.manage`, `fees.manage`, `school.manage`, `reports.view`) |

---

## 9. Completion metrics

| Metric | Value |
|--------|-------|
| In-scope endpoints inspected / audited | **71** |
| Paths | **51** |
| Defective write bodies before fix (**D1**) | **18** → now **0** |
| Write bodies fixed | **18** (+5 already-typed GPS/attendance/cancel) |
| PDF media-type defects fixed (**D2**) | **6** → now **0** remaining |
| JSON response schemas missing (**D3**) | **65** → now **0** remaining |
| Attendance enum (**D4**) | **2** fixed + case normalization |
| Offline OpenAPI/parity tests | see latest run below |
| DB integration tests | **0** (skipped — empty `TEST_DATABASE_URL`) |
| Neon / Render / admin-web | **Not touched** |
| Alembic head | **`20261029_0041`** (unchanged) |

### Changed files (OpenAPI fix waves)

- `backend/app/schemas/v1/school_admin_erp.py`
- `backend/app/schemas/v1/school_admin_erp_responses.py` (**new** — response docs)
- `backend/app/api/v1/school_admin_mgmt.py`
- `backend/app/api/v1/school_admin_erp.py`
- `backend/app/api/staff_transport.py`
- `backend/app/api/student_erp_reads.py`
- `backend/app/services/v1/school_academic_mgmt.py` (band overlap)
- `backend/tests_offline/test_erp_openapi_schemas.py`
- `backend/docs/school-admin-erp-field-level-api-audit.md` (this file)

### Module coverage headline

| Module | Status |
|--------|--------|
| 1 Report cards & grading | **Partially covered** (core full; teacher APIs / full 0–100 coverage missing) |
| 2 Fee structures & installments | **Partially covered** (core full; overdue filter / category uniqueness / optional flags missing) |
| 3 Fee collection & receipts | **Fully covered** for in-scope goals (gateway out of scope) |
| 4 Transport management | **Partially covered** (core full; stop PATCH / driver conflict / vehicle_type missing) |
| 5 Bus tracking & attendance | **Fully covered** for HTTP poll design (WebSocket/cron/hardware out of scope) |

**Audit completeness:** Every in-scope endpoint in §2 was inspected against route + service + regenerated OpenAPI after the schema fix.
