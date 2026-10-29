# School Admin Feature API Audit

Date: 2026-10-29  
Scope: Six School Admin features only (live bus tracking, payroll/payslips, announcement audience/drafts, teacher–parent messages, leave types, staff certificates/QR).  
Method: OpenAPI + route registration → auth/permission → service → model/migration; cross-check against `OPERATIONS_MODULES_API_CONTRACT.md` and offline tests.  
Safety: no production Neon migrate; no Render deploy; no Git push; `admin-web` not recreated.

## Executive summary

| # | Feature | Status (post-implementation 2026-10-29) |
|---|---------|--------|
| 1 | Live Bus Tracking | **IMPLEMENTED** |
| 2 | Payroll Processing and Payslips | **IMPLEMENTED** |
| 3 | Announcements — Audience and Drafts | **IMPLEMENTED** |
| 4 | Teacher–Parent Messages | **IMPLEMENTED** |
| 5 | Leave Types | **IMPLEMENTED** |
| 6 | Staff Certificates and QR Codes | **IMPLEMENTED** |

**Update:** All six features were completed in the backend delivery documented in [`school-admin-feature-implementation-report.md`](school-admin-feature-implementation-report.md) (Alembic `20261029_0043`, offline tests). Migration authored only — not applied to Neon in that delivery. Historical gap analysis below is retained for audit trail; treat the completion matrix in the implementation report as current truth.

**Frontend evidence:** the intentionally deleted `admin-web` tree is gone; this repo currently has **no** School Admin UI/API-client TypeScript/React sources. Frontend conclusions are therefore limited to backend contracts + historical ops docs (which state some pages used sample/browser-local data until routes landed).

---

## Feature table

| Feature | School Admin endpoint(s) & method | Route / service paths | DB model / table | Auth & tenant isolation | Frontend / API-client evidence | Test evidence | Status | Exact missing functionality |
|---------|-----------------------------------|------------------------|------------------|-------------------------|--------------------------------|---------------|--------|------------------------------|
| **1. Live Bus Tracking** | `POST /api/v1/school-admin/transport-trips/{trip_id}/gps`; `GET/POST …/transport-trips`; start/complete; attendance; `GET …/transport/reports/trips`. **No** School Admin `GET` live positions. Parent-only live: `GET /api/parent/children/{student_id}/transport/live`. Staff write: `POST /api/staff/transport/trips/{trip_id}/gps`. | `app/api/v1/school_admin_erp.py`; `app/api/staff_transport.py`; `app/services/v1/school_erp_transport.py` | `TransportGpsPoint` → `transport_gps_points` (Alembic `0041`); also `transport_trips`, vehicles, routes | School Admin: `require_school_permission(PERM_SCHOOL)` + `_school_id(auth)`; GPS rows store `school_id`; trip ownership via `_owned(..., school_id)` | No FE in repo. Ops contract: admin-web needed `GET /transport/vehicle-locations` or latest GPS on trips; treated fixes older than 5/30 min as stale/offline in UI | `tests_offline/test_erp_openapi_schemas.py`, `test_erp_wave_parity.py` register trip/GPS POST + parent live path; model column checks | **PARTIALLY IMPLEMENTED** | School Admin **read** of live/latest GPS (map poll); vehicle-locations aggregate; WebSocket not present (by design HTTP polling). Legacy `/api/transportation/*` live stubs are **501**, not School Admin v1. |
| **2. Payroll & Payslips** | `GET/PUT /api/v1/school-admin/payroll-settings`; `GET/POST /api/v1/school-admin/payroll-runs`; `GET/POST/PATCH/DELETE /api/v1/school-admin/salary-components`. **No** `/payslips*`, `/payroll/preview`, `/payroll/process`, `/salary-structures`, `/salary-assignments`. | `app/api/v1/school_admin_mgmt.py`; `app/services/v1/school_academic_mgmt.py` | `PayrollSetting`, `PayrollRun`, `PayrollItem`, `SalaryComponent` (`payroll_settings`, `payroll_runs`, `payroll_items`, `salary_components` / `0042` for components) | `require_fees` + `_school_id(auth)`; staff_id validated same school on run create | No FE in repo. Ops contract describes full preview/process/payslip UX; notes simple runs exist; staff portal payroll routes are stubs | OpenAPI body coverage lists payroll-settings/runs; salary-component offline FE-gap tests | **PARTIALLY IMPLEMENTED** | Server-side payroll calculation; salary structures/assignments; preview/process with idempotency; **payslip list/get/PDF**; wiring salary components into run line items (catalog only today). Client supplies `gross`/`deductions`/`net` on run create. `/api/staff/payroll-*` = **501 stubs** (not School Admin proof). |
| **3. Announcements — Audience & Drafts** | `GET/POST /api/v1/school-admin/announcements` (title, description/body, session_year_id only). Related: `GET/POST …/notifications` (title, body, status int). No PATCH/DELETE on mgmt announcement routes. | `school_admin_mgmt.py` + `school_academic_mgmt.py` (`list_announcements` / `create_announcement`); polymorphic academics `notices` also maps to `Announcement` | `Announcement` → `announcements` columns: `id`, `title`, `description`, `session_year_id`, `school_id` — **no** `audience`, `status`/`draft`, `publish_at` | `require_school` (mgmt) + school_id from auth; create binds `school_id` | No FE in repo. Ops contract: “Until then admin-web … keeps audience, publish date, drafts … in the browser.” | OpenAPI typed `AnnouncementCreateBody`; offline generic-body checklist includes `POST /announcements` | **PARTIALLY IMPLEMENTED** | Audience enum persistence/validation; draft vs published/scheduled status; `publish_at`; list filters; edit/delete announcement APIs on School Admin mgmt surface; delivery/recipient tracking for notifications. |
| **4. Teacher–Parent Messages** | **None** under `/api/v1/school-admin/*` for conversations/messages. Only unrelated `POST …/support-tickets/{id}/messages` (support desk). Legacy stubs: `GET/POST /api/message`, `GET /api/users/chat/history` → **501**. | Stubs: `app/api/stubs.py`; support: `school_admin_settings.py` / `school_settings_cms.py` | **No** `Conversation` / teacher–parent `Message` ORM tables | N/A for messaging (support tickets use settings permission + school_id) | No FE; ops contract specifies `/messaging/policy`, `/conversations`, moderation — not built | Settings wave tests cover support-ticket messages only (different product) | **MISSING** | Entire School Admin messaging policy, conversation list/read/send, moderation/hide, attachment signed URLs, relationship validation teacher↔parent↔student. Do **not** treat support tickets or 501 stubs as messaging. |
| **5. Leave Types** | `GET/PUT /api/v1/school-admin/leave-settings` — opaque `policy` JSON + notes. Leave requests: `GET/POST/PATCH /api/v1/school-admin/academics/leaves` (reason, dates, user/student, status). **No** `/leave-types` CRUD. | `school_admin_settings.py` + `school_settings_cms.py`; leaves via `school_admin_academics.py` / `school_academics.py` | `SchoolLeaveSetting.policy_json` (opaque); `Leave` has **no** `leave_type` column | Settings: `PERM_SETTINGS`; leaves: school admin academics guards; school_id from auth | No FE. Ops contract: admin-web stores `policy.types = [{key,name,days_per_year,applies_to}]` inside leave-settings; prefixes type into `reason` text | Offline FE-gap / settings tests cover leave-settings presence; leave create requires user_id or student_id | **PARTIALLY IMPLEMENTED** | First-class leave-type entity/CRUD/deactivate; schema validation of types; `leave_type` on leave rows; leave-balance API. Opaque policy can store types but service explicitly does **no** accrual/approval math. |
| **6. Staff Certificates & QR** | Templates: `GET/POST/PATCH/DELETE /api/v1/school-admin/certificate-templates`. Issue: `POST …/certificates/issue` (**requires `student_id`**). ID cards: `GET/PUT …/id-card-settings`; `GET …/students/{id}/id-card`; `GET …/staff/{id}/id-card` (JSON profile payload). `GET/PUT …/staff-qr-attendance-settings` = **attendance** QR config, not certificates. | `school_admin_mgmt.py` + `school_academic_mgmt.py` (`issue_certificate`, `staff_id_card_payload`, …) | `CertificateTemplate`, `CertificateIssue` (`student_id` FK); `IdCardSetting`; `StaffQrAttendanceSetting` | Templates/issue: `require_school`; staff id-card: `require_staff`; all `_school_id` + ownership checks | No FE. Ops contract still lists staff certificates, cert list/PDF, ID-card QR as needed | OpenAPI bodies for certificate-templates/issue; model exists | **PARTIALLY IMPLEMENTED** | Issue certificates to **staff** (`staff_id`); list issued certs; PDF/file storage; QR payload from certificate_no; **verify** endpoint; QR on staff ID card. Person document category `certificate` is file upload, not issued staff certificate workflow. Stubs `/api/certificate/assign|generate` = **501**. |

---

## Detailed findings (verified facts)

### 1. Live Bus Tracking — PARTIALLY IMPLEMENTED

**Verified present**
- School Admin can create/list trips, start/complete, post GPS (`lat`/`lng`), board/drop attendance, trip reports.
- GPS points are persisted in `transport_gps_points` with `school_id`, `trip_id`, `vehicle_id`, `recorded_at` (optional `expires_at` from `GPS_RETENTION_DAYS`).
- Parent live status returns `latest_gps` for an in-progress trip on the child’s route (not School Admin).
- Staff drivers can POST GPS on assigned trips.

**Verified missing for School Admin**
- No `GET` that returns current/live positions of school buses for an admin map.
- Ops contract (2026-10-29) still lists admin GPS read as needed.
- Hardcoded map coordinates: **not** found in backend GPS write path (coordinates come from request body). Without FE, cannot verify UI mock maps.

**Assumption (not proven):** whether production devices actually post GPS; only code path audited.

### 2. Payroll Processing and Payslips — PARTIALLY IMPLEMENTED

**Verified present**
- School-scoped payroll settings CRUD.
- Payroll run create persists `PayrollRun` + `PayrollItem` rows (gross/deductions/net from client).
- Salary component catalog CRUD (earning/deduction metadata); not applied in run math.

**Verified missing**
- Payslip resources (`GET /payslips`, PDF).
- Salary structures/assignments and server preview/process workflow from ops contract.
- `/api/staff/payroll-slip` etc. are contract stubs returning 501 — not School Admin implementations.

### 3. Announcements — Audience and Drafts — PARTIALLY IMPLEMENTED

**Verified present**
- School-scoped list + create with title/description/session_year.

**Verified missing**
- No audience field on model or create body.
- No draft/scheduled/published status column (unlike payroll runs or online assessments).
- No dedicated PATCH/DELETE on `/school-admin/announcements`.
- Ops doc states FE previously kept audience/drafts client-side.

### 4. Teacher–Parent Messages — MISSING

**Verified**
- No School Admin conversation/message routes in OpenAPI under `/api/v1/school-admin`.
- No ORM tables for teacher–parent chat.
- Legacy message/chat paths are 501 stubs.
- Support-ticket messages are a different domain (school ↔ support), not teacher–parent.

**Permission note:** Even if an admin role exists, no messaging policy endpoint grants or denies access — feature is absent, not merely locked down.

### 5. Leave Types — PARTIALLY IMPLEMENTED

**Verified present**
- `leave-settings` stores opaque JSON `policy` per school (can hold a `types` array by convention).
- Leave request APIs exist and are school-scoped.

**Verified missing**
- No `leave_types` table or typed CRUD/deactivate API.
- `Leave` model has no `leave_type` column; types are not first-class FK/enum in DB.
- Service comment: “Opaque policy document only — no accrual/approval math invented here.”

### 6. Staff Certificates and QR Codes — PARTIALLY IMPLEMENTED

**Verified present**
- Certificate template CRUD; issue certificate **to students** with persisted `certificate_no`.
- Staff ID card **JSON** payload (identity fields + settings) — no QR string/image in payload.
- Staff QR **attendance** settings (separate feature).

**Verified missing**
- Staff as certificate subject (`CertificateIssue.student_id` only).
- Certificate PDF generation / binary storage for issues.
- QR encode of certificate id/no + public/admin verify endpoint.
- List issued certificates for admin.

---

## Super Admin / non–School-Admin endpoints (do not count as School Admin)

| Area | Paths | Note |
|------|-------|------|
| Legacy admin CRUD | `GET/POST/PATCH/DELETE /api/admin/announcements`, `/api/admin/leaves`, … | Separate `/api/admin` surface (`admin_context`); not `/api/v1/school-admin` |
| Contract stubs (501) | `/api/certificate/*`, `/api/message`, `/api/users/chat/history`, `/api/staff/payroll-*`, `/api/staff/qr-attendance/*`, many `/api/transportation/*` live routes | Unported Laravel stubs — return stub JSON, not real School Admin APIs |
| Parent live bus | `GET /api/parent/children/{student_id}/transport/live` | Parent portal, not School Admin |
| Staff GPS write | `POST /api/staff/transport/trips/{trip_id}/gps` | Staff role, not School Admin UI |
| Super-admin SaaS | `/api/v1/super-admin/*` | Platform admin; unrelated to school payroll/certs/messaging |

---

## Tests run (actual)

```powershell
cd backend
python -m pytest tests_offline/test_erp_wave_parity.py tests_offline/test_erp_openapi_schemas.py tests_offline/test_school_settings_wave_parity.py tests_offline/test_openapi_no_generic_bodies.py -q --tb=line
```

**Result: 26 passed** in 32.05s (offline suite subset used for this audit).

`TEST_DATABASE_URL` was **empty** → no DB integration / tenant-isolation live tests in this run.

OpenAPI spot-check (from live `app.main:app`) confirmed registered School Admin paths listed in the table above and absence of `/payslips`, `/messaging/*`, `/leave-types`, admin GPS GET, certificate verify/QR.

---

## Final summary

| Implemented for School Admin today | Still sample / client-side / incomplete | Missing endpoints |
|------------------------------------|-----------------------------------------|-------------------|
| Trip + GPS **write**, transport master data, parent live poll (parent role) | Admin **live map read** of GPS | `GET` vehicle-locations / trip latest GPS for school-admin |
| Payroll settings, runs (client amounts), salary-component catalog | Full calculated payroll + payslips | `/payslips`, `/payroll/preview`, `/payroll/process`, salary-structures/assignments |
| Announcement create/list (basic fields) | Audience + drafts (ops doc: were browser-local) | audience/status/publish_at; PATCH/DELETE announcements |
| — | — | All teacher–parent messaging routes + models |
| Opaque leave-settings policy bag; leave requests | Typed leave-type CRUD & leave.leave_type | `/leave-types*`, leave balances |
| Student certificate issue + staff ID-card JSON + attendance QR settings | Staff certificates + cert QR verify | staff issue, cert list/PDF, QR verify |

**Separate verified facts from assumptions**
- **Facts:** route registration, models/columns, service behavior, auth dependency names, stub 501 responses, ops contract text, offline test registration, empty `TEST_DATABASE_URL`.
- **Assumptions / unverified:** whether any external School Admin frontend (outside this repo) still mocks map/payslip/message UI; live GPS device feeds; production DB contents; runtime RBAC matrix beyond code inspection.
