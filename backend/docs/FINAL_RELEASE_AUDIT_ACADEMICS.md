# Final Release Audit — Academic APIs + Migrations (Phases 3–10)

**Date:** 2026-10-21  
**Scope:** Backend + backend docs only. No frontend access/edits. No commit/push/deploy.

## Audit table

| Category | Result | Evidence |
|---|---|---|
| Duplicate HTTP method/path pairs | **PASS** | OpenAPI inventory: `DUPLICATE_METHOD_PATH none` (399 routes) |
| School Admin route prefixes / tags | **PASS** | Direct + `/academics` under `/api/v1/school-admin`; tag `v1-school-admin` on school_admin router |
| Duplicate model/table definitions | **PASS** | Single `ClassSubject` / `TeacherAssignment` in `tables.py` |
| ORM vs migration unique indexes | **PASS** | Names and partial predicates match 0017–0022 |
| Duplicate/conflicting service validation | **PASS** | Shared `school_academics` service; IntegrityError → fixed 409 |
| Broken imports / OpenAPI startup | **PASS** | `app.main` import OK; OpenAPI paths generated |
| Legacy academics compatibility routes | **PASS** | Preserved; no removal |
| Accidental frontend changes this audit | **PASS** | No `admin-web/`; no `.tsx`/`.jsx` edits |
| Auth on protected School Admin routes | **PASS** | `require_school_permission` / `require_school_admin` on all academic routes |
| RBAC read/write split | **PASS** | structure read `dashboard.view`, write `school.manage`, teachers `teachers.manage` |
| Tenant isolation / forged school_id | **PASS** | `sanitize_write_body` blocklist; `_owned` / `_same_school`; security tests |
| Soft-delete / no cascade wipe | **PASS** | `deleted_at`; migrations no `ON DELETE CASCADE` on new FKs |
| Team-teaching uniqueness | **PASS** | Key includes `staff_id`; schema + assignment tests |
| Alembic graph 0017→0022 | **PASS** | Single head `20261021_0022`; linear parents; no dup revision IDs |
| Preflight data conflicts | **PASS** | 0 conflict groups on target |
| Migration apply (local app DB) | **PASS** | `20261020_0016` → `20261021_0022` |
| Staging/production migration | **BLOCKED** | Not applied; must re-run identity + preflight per environment |
| Academic pytest suite | **PASS** | 37 passed (isolated `eschool_saas_test`) |
| Vishal contract approval | **BLOCKED** | Questions remain; no approval recorded |

## Database identity (no secrets)

| Role | Database name | Host kind | Notes |
|---|---|---|---|
| Alembic / app (`NEON_DATABASE_URL`) | `eschool_saas_v1` | neon | `APP_ENV=local` |
| Pytest (`TEST_DATABASE_URL`) | `eschool_saas_test` | neon | Wipe fixture `DROP SCHEMA public CASCADE` — **test only** |
| Same name as app? | No | — | Isolation gate satisfied |

## Migrations applied

| From | To | Revisions |
|---|---|---|
| `20261020_0016` | `20261021_0022` | 0017, 0018, 0019, 0020, 0021, 0022 |

Post-check: all unique/lookup indexes and tables `class_subjects` / `teacher_assignments` present. Verified final revision `20261021_0022`.

## Tests

### DB-free

- Python AST syntax on academic modules — PASS  
- App import + OpenAPI generation — PASS  
- Duplicate route inventory — PASS  
- ORM index name listing vs migration names — PASS  

### DB-backed (after isolation gate)

```text
python -m pytest tests/v1/test_academic_schema.py tests/v1/test_academic_sessions.py tests/v1/test_academic_structure.py tests/v1/test_school_admin_academic_security.py tests/v1/test_school_admin_classes.py tests/v1/test_school_admin_sections.py tests/v1/test_school_admin_subjects.py tests/v1/test_school_admin_teacher_assignments.py -q --tb=line
```

**Result:** `37 passed in 1179.17s (0:19:39)` — exit code 0.

## Bugs found / fixes in this audit

| Item | Action |
|---|---|
| Docs still said migrations “unapplied” after local apply | Updated `ACADEMICS_API.md` + contract D9 |
| No product code bugs requiring hotfixes during audit | None |

## Remaining risks / approvals

1. **Staging/production:** do not treat local apply as global; run identity + preflight + `alembic upgrade` per target.  
2. **PostgreSQL NULL uniqueness** on teacher-assignment nullable columns still relies on app-layer checks (documented in 0017).  
3. **Vishal** must confirm path preference, subject types, assignment body shape, `/me` permissions (contract §8).  
4. Helper scripts `_release_*.py` / `_phase10_route_inventory.py` / `_release_upgrade_sql.txt` are audit artifacts — not required at runtime.  
5. Untracked `eschool/`, SQL review dumps, and subscription backup files were **not** part of this academic release and were left untouched.

## Frontend confirmation

No frontend files or directories were opened, inspected, created, or modified during this final release audit.
