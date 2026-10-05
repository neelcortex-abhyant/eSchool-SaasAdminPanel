# MySQL → Neon data migration status

## Status: **PENDING — MySQL source data not available**

This backend now targets a **single Neon PostgreSQL** database (`NEON_DATABASE_URL`).
Schema migrations for the FastAPI-mapped tables exist:

| Revision | Purpose |
| --- | --- |
| `20261005_0001` | V1 `users` + `auth_sessions` (already applied on live Neon historically) |
| `20261005_0002` | Rename V1 `users` → `v1_users` (avoids clash with legacy `users`) |
| `20261005_0003` | Legacy school-scoped tables on the same Neon DB |

**Do not apply `0002`/`0003` to the live Neon app database without explicit approval.**

## Why data import is blocked

1. No MySQL dumps / connection details were provided for this migration pass.
2. Legacy SaaS used **database-per-school** (`schools.database_name`). Merging into one
   Postgres DB requires **ID remapping** so primary keys from school A and school B do not collide.
3. ~78 Laravel catalog tables exist; only ~21 are mapped in FastAPI. Unmapped tables need a
   separate import plan if mobile/admin still rely on them via Laravel.

## Recommended import procedure (when MySQL is available)

1. Snapshot every MySQL schema (central + each `schools.database_name`).
2. Apply Alembic through `20261005_0003` on a **staging** Neon database (not production).
3. Import central rows: `schools`, `packages`, `system_settings`, super-admin `users` (`school_id` NULL).
4. For each school DB:
   - Map old integer PKs → new global PKs (or allocate ranges per school).
   - Set `school_id` on every tenant row.
   - Preserve bcrypt `users.password` hashes as-is (`$2y$` / `$2b$`).
   - Preserve Sanctum `personal_access_tokens.token` SHA-256 hashes if sessions must survive.
   - Keep `schools.database_name` as an audit/import label only (connections no longer use it).
5. Do **not** merge V1 `v1_users` with legacy `users`. V1 auth stays on `v1_users` + `auth_sessions`.
6. Verify cross-school isolation: login with school A credentials must not see school B rows.
7. Cut over Render `NEON_DATABASE_URL` only after staging sign-off.

## Unmapped Laravel tables

See `app/models/catalog.py`. Until imported, features that depended on those tables via Laravel
remain incomplete on FastAPI.
