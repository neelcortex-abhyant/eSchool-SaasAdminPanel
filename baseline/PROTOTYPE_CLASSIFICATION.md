# Prototype scaffold classification

## Location

Inside the Laravel archive (not this repo):

- `/Users/apple/eSchool-Saas-V1.11.0/Admin Panel Code/PHP CODE/PHP_CODE_V1.11.0/backend`
- `/Users/apple/eSchool-Saas-V1.11.0/Admin Panel Code/PHP CODE/PHP_CODE_V1.11.0/frontend`

## Status: PROTOTYPE — not migration-complete

Do not deploy. Do not treat passing local smoke tests as Phase 3–10 evidence.

### Known contract mismatches

| Area | Prototype behavior | Required Laravel contract |
| --- | --- | --- |
| Login body | JSON | Multipart form (`Form` + files) |
| Login resource | Reduced user DTO | Role-specific complete resource graphs |
| Admin API | New `/api/admin` only | Mobile `/api/*` parity first |
| Schema helper | `create_schema()` / `Base.metadata.create_all` in tests | No production DDL; MySQL schema is v1.11 baseline |
| Test DB | SQLite helpers used in places | Contract/integration tests on MySQL |

### Reuse policy

1. Copy individual modules into `/Users/apple/eSchool-SaasAdminPanel/backend` or `admin-web` only after they pass Phase gates.
2. Before any production process starts, ensure `create_schema` is never imported or invoked outside isolated unit tests.
3. Re-validate auth, tenant isolation, and golden fixtures after every reuse.

### Target homes in this repo

- FastAPI production code → `backend/`
- New admin UI → `admin-web/`
- Compatibility tests → `contract-tests/`
