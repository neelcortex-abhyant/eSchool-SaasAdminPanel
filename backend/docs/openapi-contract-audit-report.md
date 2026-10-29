# OpenAPI / Swagger Contract Audit & Fix Report

Date: 2026-10-29 (ONE-SHOT MASTER TASK complete)  
Scope: Entire FastAPI application (all mounted routers)  
Safety: no Render deploy; no Neon migrate; no `admin-web` changes; no unrelated SaaS billing logic changes.

## Method

1. Baseline from Git status (preserved existing user changes; did not reset/discard).
2. Generated OpenAPI from `app.main:app` (not source-grep alone).
3. Reconciled prior Phase 1/2 counts with current repository.
4. Fixed remaining school-admin write response gaps, then GET/DELETE/list/read gaps where serializers already existed.
5. Fixed PDF/binary media-type pollution (empty JSON alongside PDF).
6. Verified five frontend API requirements + Alembic `0042` ancestry (not applied).
7. Ran offline regression suite and regenerated OpenAPI metrics.

## Before / after (master-task run)

### Request bodies (Phase 1 — preserved)

| Metric | Before Phase 1 | After / current |
|--------|----------------|-----------------|
| Total operations | 768 | **768** |
| Operations with a request body | 218 | **218** |
| **Generic JSON request bodies** | **46** | **0** |
| Screenshot checklist POST bodies typed | 0/17 | **17/17** |

### Response schemas

| Metric | Start of Phase 2 | End of prior Phase 2 | **Master-task final** |
|--------|------------------|----------------------|------------------------|
| JSON success responses with named `$ref` | 156 | 306 | **425** |
| JSON success responses without named `$ref` | 610 | 460 | **332** |
| **School-admin write ops missing named response** | **116** | **27** | **0** |
| School-admin all ops missing named response | 273 | 123 | **0** |
| Other modules missing named response | 337 | 337 | **332** |

### Media types

| Item | Status |
|------|--------|
| Invoice / fee receipt / report-card PDF routes | `application/pdf` binary schema; empty JSON companion removed via `response_class=Response` + `-> Response` |
| People photo / document download / study-material download | Documented as binary (`octet-stream` / `image/*`) |
| `/api/student-exan-result-pdf` | Still honest **JSON 501 stub** (not PDF) — intentional blocker |

## What was fixed in this run

### Former remaining 27 school-admin writes → **0**

Derived response models from service serializers and wired `responses=json_response(...)` without changing runtime return dicts:

- Offline exams: exam / schedule / mark / bulk / process-results
- Online assessment questions: add / import / patch
- Study materials multipart: `/upload`, `/{id}/file`
- People: documents, photos, guardian link
- Support tickets: create / patch / message
- Misc: homework attachments, subject↔classes, user-form-fields, online-exam-terms

### School-admin reads / deletes → **0 missing**

Wired list envelopes, single-resource GETs, soft-delete shapes, academics polymorphic GET/DELETE, timetable weekly/daily/availability, departments, people list, OA attempts, offline result summaries/audits, homework summary. Binary file routes documented without inventing JSON bodies.

### Other modules (confirmed, non-stub)

- Public school lookup `by-host` / `by-code` → `PublicSchoolLookupOut`
- Auth change/forgot/reset password → `MessageOut`
- Public contact inquiry create → `ContactInquiryOut`
- PDF empty-JSON pollution fixed on school-admin ERP PDF routes

## Frontend API requirements (verified)

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Public school lookup by host and code | Routes registered; OpenAPI schemas present; safe fields only (`code` on by-code only) |
| 2 | Leave `student_id` ↔ `user_id` | Create accepts either; offline tests cover validation |
| 3 | Timetable optional `room` | Model column + request/response schemas; migration `0042` |
| 4 | Nested fee installments | `FeeStructureOut.installments` + installment APIs |
| 5 | Salary-component catalog CRUD | Routes + schemas + auth (fees permission); **catalog only — not wired into payroll calculation lines** |

Migration: `alembic/versions/20261029_0042_frontend_api_gaps.py`  
- Revises: `20261029_0041`  
- Head: `20261029_0042`  
- Adds: `class_timetable_entries.room`, table `salary_components`  
- **Not applied to Neon** (safety)

## Remaining 332 missing named JSON responses

**Not claimed fixed.** Dominated by Laravel-parity **501 stubs** under `/api/admin/*`, `/api/teacher/*`, `/api/parent/*`, `/api/student/*`, plus a few super-admin/backups endpoints.

Per scope: do **not** invent response contracts for unimplemented stubs.

Remaining non-stub follow-ups (optional, lower risk):

- Super-admin backups / ping response models (if serializers are stable)
- Isolated DB regression once `TEST_DATABASE_URL` points at a non-production database

## Security / validation notes

- Integration settings responses remain `configured` + `public_config` only (no ciphertext).
- Public school lookup excludes private admin fields.
- PDF/file routes keep private cache headers / nosniff where already present.
- No auth/RBAC weakening; no tenant-scope changes.

## PDF stub: `/api/student-exan-result-pdf`

**Blocker — not implemented as PDF.**

- Lives in `app/api/stubs.py`; returns shared `_stub()` JSON envelope (`fail(..., code=501)`).
- Typo path (`exan`) retained; real PDF report/receipt routes exist elsewhere.
- **Decision:** leave stub unchanged; OpenAPI correctly shows JSON until a deliberate port.

## Exact files changed (this master-task wave)

- `app/schemas/v1/school_admin_core_responses.py` — offline exams, people docs, lists, timetable, summaries, binary helper
- `app/schemas/v1/school_admin_settings_responses.py` — OA questions/attempts, CMS tickets/forms/terms, list envelopes
- `app/schemas/v1/public_schools.py` — **new** public lookup Out model
- `app/schemas/v1/auth.py` — `MessageOut`
- `app/api/v1/school_admin.py` — wired remaining write/read/delete/binary responses
- `app/api/v1/school_admin_settings.py` — wired settings/CMS/public contact responses
- `app/api/v1/school_admin_academics.py` — summary / session / assignment / polymorphic GET+DELETE
- `app/api/v1/school_admin_erp.py` — PDF `response_class=Response` fix
- `app/api/v1/public_schools.py` — named lookup responses
- `app/api/v1/auth.py` — message responses
- `tests_offline/test_openapi_response_coverage.py` — tightened write coverage + former-27 guards
- `scripts/_wire_remaining_sa_responses.py`, `_wire_remaining_sa_responses2.py`, `_list_sa_missing.py` — audit helpers
- `docs/openapi-contract-audit-report.md` — this report

No new Alembic migration in this wave (0042 already present from FE gaps work).

## Tests run (actual)

```bash
cd backend
python -m pytest tests_offline -q --tb=short
```

**Result: 49 passed** (2026-10-29).

Also re-confirmed:

- `test_openapi_no_generic_bodies.py` — **0** generic JSON bodies
- `test_openapi_response_coverage.py` — named responses; school-admin write missing **0**
- `test_frontend_api_gaps.py` — five FE requirements

`TEST_DATABASE_URL` was **empty** → DB integration / tenant isolation tests **not** run (production Neon not used).

OpenAPI regen metrics (from `scripts/_audit_openapi_responses.py` / `_audit_openapi_bodies.py`):

- ops=768, with_body=218, generic_json=0
- with_named_json_success=425, missing_named=332
- school-admin writes missing=0, school-admin all missing=0
- pdf_issues=1 (`/api/student-exan-result-pdf` stub JSON only)

## Remaining blockers / unverified

1. Apply `0042` only with explicit approval per environment (not done here).
2. No isolated `TEST_DATABASE_URL` → cross-school/auth DB behavior unverified in this run.
3. Do not invent schemas for **501 stubs** until routes are ported.
4. Salary components are a **catalog**; payroll run line items remain gross/deductions/net aggregates (no FK from payroll items to components).
5. Reload local uvicorn / Swagger UI cache to pick up OpenAPI changes.
