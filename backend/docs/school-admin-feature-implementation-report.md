# School Admin Six Features — Implementation Report

Date: 2026-10-29  
Scope: Complete all six School Admin features per approved plan (backend only).  
Safety: migration files authored only — **not** applied to Neon; no Render deploy; no git push; `admin-web` untouched.

## Completion matrix

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | Live Bus Tracking (admin GPS reads) | **Complete** | `GET /transport/vehicle-locations`, `GET /transport-trips/{id}` + freshness; offline freshness tests |
| 2 | Payroll structures / preview / process / payslips | **Complete** | CRUD structures/assignments; `GET /payroll/preview`; `POST /payroll/process` + Idempotency-Key; payslips + PDF; formula unit test |
| 3 | Announcements audience / drafts / publish | **Complete** | status/audience/publish_at; PATCH/DELETE; lazy publish; notification audience + delivery=`queued` |
| 4 | Teacher–Parent Messaging | **Complete** | Admin policy/conversations/moderate; teacher `/api/teacher/conversations*`; parent `/api/parent/conversations*` |
| 5 | Leave Types + leave_type_id | **Complete** | `/leave-types` CRUD; `/leave-balances`; `Leave.leave_type_id`; policy.types seed on PUT leave-settings |
| 6 | Staff certificates + QR verify | **Complete** | issue-staff; list/get/pdf/revoke; public verify token; staff ID-card `qr_verify_url` |

**Complete** = routes registered + service logic + models/migration `0043` + offline tests with real results.

## Migration

- File: `alembic/versions/20261029_0043_six_features_completion.py`
- Revises: `20261029_0042`
- Single head verified: `alembic heads` → `20261029_0043`
- **Not applied** to production Neon in this delivery

Adds / alters: `leave_types`, `leaves.leave_type_id`, announcement lifecycle columns, notification audience/delivery, certificate staff/token/status, salary structures/lines/assignments, payroll run/item extensions + audit, messaging policy/conversations/messages/reads.

## Key routes (School Admin base `/api/v1/school-admin`)

### Live bus
- `GET /transport/vehicle-locations`
- `GET /transport-trips/{trip_id}` (includes `latest_gps`, freshness)

### Leave
- `GET/POST /leave-types`, `GET/PATCH/DELETE /leave-types/{id}`
- `GET /leave-balances?user_id=&year=`
- Leaves accept `leave_type_id` / `leave_type` code

### Announcements / notices
- `GET/POST /announcements` (+ filters `status`, `q`)
- `GET/PATCH/DELETE /announcements/{id}`
- Notifications accept `audience`; response includes `delivery=queued` (no push fabricated)

### Payroll
- `GET/POST /salary-structures`, `PATCH/DELETE /salary-structures/{id}`
- `GET/POST /salary-assignments`
- `GET /payroll/preview?month=YYYY-MM`
- `POST /payroll/process` + `Idempotency-Key`
- `GET /payroll/summary?year=`
- `GET /payslips`, `GET /payslips/{id}`, `GET /payslips/{id}/pdf`
- Legacy `POST /payroll-runs` retained (client amounts; non-authoritative)

**Formula:** `gross = basic + earnings`; `deductions = sum(deduction lines)`; `attendance_adjustment = 0`; `net = gross - deductions + attendance_adjustment`. No statutory PF/tax invented.

### Messaging
- `GET/PUT /messaging/policy`
- `GET/POST /conversations`, messages, read, flag, hide
- Teacher: `/api/teacher/conversations*`
- Parent: `/api/parent/conversations*`
- Text-only v1; attachments deferred

### Certificates
- `POST /certificates/issue` (exactly one of `student_id` | `staff_id`)
- `POST /certificates/issue-staff`
- `GET /certificates`, `GET /certificates/{id}`, PDF, `POST …/revoke`
- Public: `GET /api/v1/public/certificates/verify/{token}` (minimal validity; no PII in QR — URL token only)
- Staff ID card returns `qr_verify_url` / `qr_code_url` (URL string; `qrcode` lib not a dependency)

## Auth / tenancy

- School Admin: `require_school_permission` + `_school_id(auth)` — never trust client `school_id`
- Fees permission for payroll; settings for leave-types; school for announcements/messaging/certs
- Cross-tenant IDs → 404 via `_owned` / relationship checks
- Messaging admin uses legacy `users.id` resolution (v1 UUID not FK-compatible)

## Tests

```
python -m pytest tests_offline/test_six_features_completion.py -q --tb=short
# 7 passed

python -m pytest tests_offline -q --tb=line
# expect all green after head assertions updated to 0043
```

DB isolation / integration: **unverified** (`TEST_DATABASE_URL` empty; Neon not used).

## Known limitations (documented)

- No WebSockets (HTTP polling + `poll_seconds`)
- No statutory payroll tax/PF/ESI engine
- Notification delivery always `queued` until email/push exists
- Messaging attachments deferred; admin sender attributed via legacy user resolution
- Certificate QR is opaque verify URL string (FE renders QR); no PNG data-URI without `qrcode` package
- Migration not applied to Neon in this task

## Files touched (primary)

| Area | Files |
|------|--------|
| Models / migration | `app/models/tables.py`, `alembic/versions/20261029_0043_six_features_completion.py` |
| Transport | `school_erp_transport.py`, `school_admin_erp.py`, erp responses |
| Leave | `school_settings_cms.py`, `school_admin_settings.py`, `school_academics.py` |
| Announcements | `school_academic_mgmt.py`, `school_admin_mgmt.py`, mgmt schemas/responses |
| Payroll | `school_erp_payroll.py` (new), mgmt routes/schemas |
| Messaging | `school_messaging.py` (new), `school_admin_messaging.py` (new), teacher_portal, student_erp_reads |
| Certificates | `school_academic_mgmt.py`, `public_certificates.py` (new), v1 router |
| Docs / tests | this report; `test_six_features_completion.py`; audit refresh |

## Out of scope (honored)

- Recreating/modifying `admin-web`
- Neon migrate / Render / git push
- Invented statutory formulas / WebSockets
- Unrelated 501 stubs
