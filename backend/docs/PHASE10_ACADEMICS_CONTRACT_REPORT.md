# Phase 10 — API Documentation & Frontend Coordination (Academics)

**Scope:** Backend documentation only. No frontend inspection/edits. No new endpoints. No migrations applied. No commit/push/deploy.

## 1. Files inspected

| Path | Role |
|---|---|
| `backend/app/api/v1/school_admin.py` | Direct School Admin academic routes + write bodies |
| `backend/app/api/v1/school_admin_academics.py` | Compat `/academics/{resource}` CRUD, permissions |
| `backend/app/services/v1/school_academics.py` | Service behavior, response shapes, uniqueness |
| `backend/docs/ACADEMICS_API.md` | Prior academic API docs |
| `backend/docs/SCHOOL_ADMIN_RBAC_API.md` | Auth / RBAC / tenant rules |
| `backend/docs/SCHOOL_API_CONTRACT.md` | Pattern reference (Super Admin schools) |
| `backend/tests/v1/test_academic_*.py`, `test_school_admin_academic_security.py` | Behavior cross-check (read-only) |

## 2. Files changed (documentation only)

| Path | Change |
|---|---|
| `backend/docs/ACADEMICS_FRONTEND_CONTRACT.md` | **Created** — shareable contract for Vishal |
| `backend/docs/ACADEMICS_API.md` | Pointer + dependent-dropdown section |
| `backend/docs/PHASE10_ACADEMICS_CONTRACT_REPORT.md` | This report |
| `backend/_phase10_route_inventory.py` | OpenAPI inventory helper (DB-free) |

## 3. API contract inventory & samples

See [ACADEMICS_FRONTEND_CONTRACT.md](ACADEMICS_FRONTEND_CONTRACT.md):

- Full endpoint inventory with status (V / C / P)
- Sample JSON for list/detail/create/PATCH/PUT associations/errors
- Dependent dropdown mapping
- Unresolved questions for Vishal
- Breaking-change / compatibility notes

## 4. Dependent dropdown mapping

Documented in contract §4 and summarized in ACADEMICS_API.md. **No new options endpoints** — existing filtered lists cover session → medium → class → section → subject → teacher → assignment.

## 5. Frontend/backend mismatches identified (docs only)

Recorded as discrepancies D1–D10 in the contract (path preference, section create semantics, subject type, `teacher_id` = users.id, assignment body shape, soft-delete revive, session compact fields, `/me` permissions, unapplied migrations, nested id meaning in class detail).

Frontend code was **not** opened or modified (strict scope override).

## 6. Questions requiring Vishal’s confirmation

Contract §8 (8 precise questions). **No contact or approval was made** through this phase.

## 7. Tests / checks executed

| Check | Result |
|---|---|
| Load FastAPI app + list `/school-admin` routes | PASS — 31 School Admin route methods (+ unrelated super-admin hit filtered) |
| Required academic paths present in OpenAPI | PASS — `MISSING none` |
| Pydantic write-body field names | PASS — classes/sections/subjects/assignments schemas load |
| `python _phase10_route_inventory.py` | PASS — prints inventory |
| Database-backed pytest | **Not run** (doc-only phase; no isolated DB run requested beyond safety rules) |
| Migrations | **Not applied** |

## 8. Deliberately deferred

- New `/options/*` or direct `/mediums`/`/teachers` shortcuts
- Enriching `GET /me` with roles/permissions
- Assignment soft-delete revive
- Any breaking response/path changes
- Frontend TypeScript clients / types / UI
- Applying Alembic 0017–0022

## 9. Frontend touch verification

No `admin-web/` or other frontend files created or modified in this phase. Changes limited to `backend/docs/*` and `backend/_phase10_route_inventory.py`.
