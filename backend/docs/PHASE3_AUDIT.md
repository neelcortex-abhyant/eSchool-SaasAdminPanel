"""Phase 3 audit notes (implementation complete).

Existing (reused):
- School CRUD (Phase 2), School model
- v1_users + auth_sessions; hash_password / create_session
- /api/v1/auth/login|/me|/signup
- require_super_admin; school_id isolation on legacy tables

Added:
- ROLE_SCHOOL_ADMIN on existing v1 role system
- v1_users.school_id + status (Alembic 0005)
- schools.v1_admin_id + provisioned_at (Alembic 0005)
- POST .../schools/{id}/provision (idempotent shared-Neon init)
- School Admin CRUD under /api/v1/super-admin/schools/{id}/admins
- GET /api/v1/school-admin/me + scoped school access
- assert_school_scope / require_school_admin

Auth: School Admin uses same /api/v1/auth/login + auth_sessions.
Isolation: school_id from auth.user; never trust client school_id.
Migration: additive 20261007_0005 only.
"""
