# Legacy source map

Legacy trees are referenced in place. Do not move or delete them during migration.

## Admin / API (Laravel 10)

- Root: `/Users/apple/eSchool-Saas-V1.11.0/Admin Panel Code/PHP CODE/PHP_CODE_V1.11.0`
- API routes: `routes/api.php`
- Web routes: `routes/web.php`
- Models: `app/Models`
- Prototype scaffold (not production): `backend/`, `frontend/` inside the Laravel tree

## Student web (Next.js 15)

- Archive/source today: `/Users/apple/eSchool-Saas-V1.11.0/Student Web Code/eSchool Sass student web v-1.11.0`
- Axios client: `src/lib/api/student/axiosConfig.ts`
- Endpoints: `src/lib/api/student/endpoints.ts`
- Target working repo: `/Users/apple/eSchool-SaasStudentWebCode`

## Flutter apps — canonical working tree

**All Flutter app changes must be made in `/Users/apple/eSchool-SaasAppCode/`.**

| App | Canonical path |
| --- | --- |
| Student/parent | `/Users/apple/eSchool-SaasAppCode/e-school-saas/e-school-saas` |
| Staff | `/Users/apple/eSchool-SaasAppCode/eschool-saas-staff/eschool-saas-staff` |

Legacy archive only (do not edit):

- `/Users/apple/eSchool-Saas-V1.11.0/App Code/...`

Key files:

- `lib/utils/constants.dart` — `baseUrl`, `databaseUrl`, `reverbUrl`
- `lib/utils/api.dart` — path constants

Phase 1 manifests were generated from the canonical AppCode tree.

## Docs

- Legacy: `/Users/apple/eSchool-Saas-V1.11.0/eSchool-SaaS-Doc-main`
- Target: `/Users/apple/eSchool-SaasDocMain`

## Migration plan

- `/Users/apple/.cursor/plans/fastapi_next_migration_49752b67.plan.md`
