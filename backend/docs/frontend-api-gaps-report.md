# Frontend API Gaps — Implementation Report

Date: 2026-10-29  
Migration created (not applied to Neon): `20261029_0042`  
Safety: no Render deploy; no production Neon migrate; no `admin-web` changes.

## Audit summary (Phase 1)

| # | Requirement | Pre-fix finding |
|---|-------------|------------------|
| 1 | School lookup for websites | Contract exists (`SCHOOL_DOMAINS_API_CONTRACT.md`); **by-host / by-code routes were missing** |
| 2 | Leave `user_id` / student mapping | Leave rows store `user_id` only; create accepted `user_id` but **not student→user resolution**; list omitted `student_id` |
| 3 | Timetable `room` | Model/API had **no room field**; classroom entity still deferred |
| 4 | Fee installments | **GET/PUT** `/fee-structures/{id}/installments` already existed; structure **GET lacked nested installments**; create already accepted installments |
| 5 | Salary components | Payroll settings/runs existed; **no salary component catalog table or CRUD** |

## Implementation status (Phase 2)

### 1. Public school lookup — **done**
- Endpoints (unauthenticated, public fields only):
  - `GET /api/v1/public/schools/by-host?host=`
  - `GET /api/v1/public/schools/by-code?code=`
- Files: `app/services/v1/public_school_lookup.py`, `app/api/v1/public_schools.py`, mounted in `app/api/v1/router.py`
- Payload matches contract; by-host does not expose `code`; private admin fields excluded

### 2. Leave student ↔ `user_id` — **done**
- Create/update accept `user_id` and/or `student_id` (resolves student → `Student.user_id`; mismatch → 422)
- Responses include both `user_id` and `student_id` (null when leave is for a non-student user)
- Files: `app/services/v1/school_academics.py`, `app/api/v1/school_admin_academics.py`
- Routes unchanged: `/api/v1/school-admin/academics/leaves`

### 3. Timetable `room` — **done**
- Optional `room` (max 128) on create/update/read serialization
- Files: model `ClassTimetableEntry.room`, `school_timetable.py`, `TimetableEntryCreateBody` / `UpdateBody` in `school_admin.py`
- Migration 0042 adds nullable column

### 4. Fee installments — **done** (mostly reuse)
- Existing: `GET`/`PUT /api/v1/school-admin/fee-structures/{structure_id}/installments`
- Added: nested `installments[]` on structure list/get responses; optional `installments` on structure PATCH
- Validation still enforces sum == structure total and blocks replace when allocations exist
- Files: `school_academic_mgmt.py`, `school_admin_erp.py` / `_responses.py`

### 5. Salary components — **done**
- New table `salary_components` (0042) + CRUD under fees permission (same as payroll):
  - `GET/POST /api/v1/school-admin/salary-components`
  - `GET/PATCH/DELETE /api/v1/school-admin/salary-components/{row_id}`
- Fields: `name`, `code`, `kind` (`earning`\|`deduction`), `calc_type` (`fixed`\|`percent`), `default_value`, `is_active`, `sort_order`
- Files: model, mgmt service, routes, request/response schemas

## Tests (Phase 3)

Command (run):

```bash
cd backend
python -m pytest tests_offline -q --tb=short
```

Result: **38 passed** (2026-10-29).

`TEST_DATABASE_URL` was empty → DB integration tests were **not** run (correct per safety rules).

OpenAPI spot-check confirmed: by-host/by-code paths, timetable `room`, `FeeStructureOut.installments`, `SalaryComponentCreateBody` fields, academics `WriteBody.user_id`/`student_id`.

## Migration note

- File: `alembic/versions/20261029_0042_frontend_api_gaps.py`
- Revises: `20261029_0041`
- Adds: `class_timetable_entries.room`, table `salary_components`
- **Do not apply to Neon without explicit approval**

## Remaining blockers

1. Migration 0042 must be applied to each environment before room writes / salary-component CRUD can persist.
2. No isolated `TEST_DATABASE_URL` in this session → cross-school/auth DB regression tests for the five gaps were not executed against a live DB.
3. Salary components are a catalog only; payroll run line items are still gross/deductions/net aggregates (no FK from `payroll_items` to components) — intentional, not invented beyond catalog need.
4. Website lookup uses school `domain` / `code` as approved identifiers; a separate slug column was not present and was not invented (`slug` is derived from domain label per contract).
