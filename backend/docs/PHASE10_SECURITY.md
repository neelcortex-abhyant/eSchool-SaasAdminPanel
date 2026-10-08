# Phase 10 — Final Testing & Security Hardening

## Status

**COMPLETE** (no new product features; Phase 9 untouched)

## Phase 9 (unchanged)

See [PHASE9_AUDIT.md](PHASE9_AUDIT.md):

- BLOCKED / DEFERRED
- Implementation NOT STARTED
- Revenue NOT AVAILABLE
- Fake payment/revenue NOT IMPLEMENTED

Phase 10 did **not** add payments, gateways, webhooks, or revenue APIs.

## Authentication model

- Opaque Bearer tokens (`auth_sessions.token_hash` = SHA-256 of plaintext token)
- Not JWT
- TTL: `V1_SESSION_TTL_MINUTES` (default 10080)
- Logout sets `revoked_at`
- Expired / revoked / unknown tokens → 401
- Inactive users (`v1_users.status != 1`) → 403 on token resolve (and sessions revoked on school-admin deactivate)

## Roles

| Role | How assigned | Access |
|---|---|---|
| `user` | Public `/api/v1/auth/signup` only | Own profile |
| `school_admin` | Super Admin creates under a school | `/api/v1/school-admin/*` scoped to `auth.user.school_id` |
| `super_admin` | Bootstrap register (first SA or `V1_SUPER_ADMIN_EMAIL`) / env promote | `/api/v1/super-admin/*` |

Clients cannot set `role` or `school_id` on signup/profile (Pydantic `extra=forbid`).

## School isolation

- School Admin identity school comes from **server-side** `auth.user.school_id`
- `assert_school_scope` denies cross-school path IDs with 403
- Super Admin routes require `require_super_admin`; School Admin → 403
- Path `school_id` / resource mismatch for SA → 404 (existing convention)

## Super Admin API surface

`/api/v1/super-admin/*` — schools, plans, subscriptions/bills, addons, reports/dashboard, settings, audit-logs, notifications.

Dashboard payment revenue fields remain **unavailable** (no gateway source).

## Security decisions (Phase 10)

1. Reject inactive users at session resolve (bugfix)
2. Revoke open sessions when a school admin is deactivated
3. No fake payment/revenue scaffolding
4. Secrets in settings returned as `value: null` + `configured` flag
5. Audit actor always from authenticated user; metadata sanitized
6. Migrations remain additive; no Phase 10 schema change

## Tests

`tests/v1/test_phase10_security.py` — auth matrix, escalation, IDOR, validation, secrets, audit spoofing, soft-delete, CORS, error leakage, Phase 9 freeze check.
