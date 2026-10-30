# Operations modules: API contract

admin-web has School Admin pages for bus tracking and transport attendance, staff attendance and
leave, payroll, announcements and notifications, teacher–parent messages, and certificates and ID
cards. Where a route below already exists on the server, the page uses it today. The rest of the
pages run on sample data until the routes in this document are deployed. Turn each one on with
`NEXT_PUBLIC_OPERATIONS_API_MODE` (`live`, or per feature: `tracking:live,payroll:live,messaging:live,notices:live`).

General rules (same as the other v1 school-admin routes):
- Base path `/api/v1/school-admin`, Bearer auth, `require_school_admin` plus the matching permission.
- The school always comes from the session (`_school_id(auth)`); never accept `school_id` in a body or query.
  Every id in a path or body must belong to that school (404 otherwise).
- Lists return `{items, total, page, page_size}`; `page_size` max 50.
- 422 `detail` lists or sentences for validation, 409 sentences for conflicts.

## Status (checked 30 Oct 2026 — four-modules backend wave)

Backend now includes (migration `0044` authored, Neon apply **UNVERIFIED**): staff attendance status enum + enriched
reports; leave approve/reject/cancel + `leave_type_id` on academics WriteBody; salary assignment history /
unpaid-leave payroll adjustment / mark-paid / dept filters; portal announcement audience filters; notification
get/cancel + BackgroundTasks delivery (queued without FCM); messaging unread-count + safer admin actor +
storage-gated attachments. See `school-admin-four-modules-implementation-report.md`.

Earlier live on Render (post six-features): trips, GPS locations, fee installments/receipts, salary components,
report-card PDF, certificates, messaging base routes, leave-types/balances.

## 0. Already used from the server (no change needed)

| Area | Routes |
|---|---|
| Vehicles, routes, stops, student transport | `/vehicles`, `/transport-routes`, `/transport-stops`, `/student-transport-assignments` |
| Staff attendance | `POST /staff-attendance` (status enum present/absent/late/half_day/leave), `GET /staff-attendance/register`, `/today`, `/reports?from_date=&to_date=` (counts late/half_day/leave) |
| Leave | `GET/POST /academics/leaves` (`leave_type_id`/`leave_type`), `POST /academics/leaves/{id}/approve\|reject\|cancel` (status 0/1/2/3); overlap + balance gate on approve |
| Leave types | `GET/POST/PATCH/DELETE /leave-types`, `GET /leave-balances`, `GET/PUT /leave-settings` |
| Payroll | `/salary-structures*`, `/salary-assignments`, `/payroll/preview\|process\|summary`, `/payslips*`, `POST /payroll-runs/{id}/mark-paid`, `/payroll/audit-events`; legacy `POST /payroll-runs` deprecated |
| Announcements / notifications | announcements audience/status/publish_at; notifications audience + delivery queued; `GET/POST …/notifications/{id}/cancel` |
| Certificates and ID cards | `/certificate-templates`, `POST /certificates/issue`, `GET /students/{id}/id-card`, `GET /staff/{id}/id-card`, `/id-card-settings` |

Small additions that would remove workarounds:
- **Leave type**: add `leave_type` (string) to leaves. Today admin-web keeps it at the start of `reason` ("Casual leave: fever").
- **Leave balances**: `GET /leave-balances?user_id=&year=` → `[{leave_type, allowed, used, pending, remaining}]` (admin-web works them out from approved leaves today).
- **ID cards**: return `qr_code_url` (or `qr_code` as a data URI) in the ID card payloads; admin-web shows it when present.
- **Certificates**: `GET /certificates?student_id=` (issued list), `GET /certificates/{id}/pdf`, and issuing to staff (`staff_id` instead of `student_id`).

## 1. Bus tracking and transport attendance (`tracking`)

Permission: transport. GPS fixes come from the driver app or a tracker; this contract only covers what the admin reads.

| Method | Path | Notes |
|---|---|---|
| GET | `/transport/vehicle-locations` | Latest fix per vehicle |
| GET | `/transport/trips?status=&route_id=&vehicle_id=&from_date=&to_date=&page=` | |
| GET | `/transport/trips/{id}` | |
| GET | `/transport/attendance?trip_id=&route_id=&student_id=&date=&status=&page=` | Boarding and drop-off records |
| PATCH | `/transport/attendance/{id}` | `{status, note}`; note required; record who corrected it |
| GET | `/transport/reports/routes?from_date=&to_date=` | Route summaries |

```json
VehicleLocation = { "vehicle_id": 3, "registration_no": "KA 01 AB 1234", "route_id": 1, "route_name": "Route 1",
  "driver_name": "Ramesh", "trip_id": 812, "trip_status": "scheduled|active|completed|cancelled",
  "latitude": 12.9716, "longitude": 77.5946, "speed_kmph": 24, "heading": 90, "recorded_at": "2026-10-29T07:12:30Z" }
Trip = { "id": 812, "route_id": 1, "route_name": "...", "vehicle_id": 3, "registration_no": "...", "driver_name": "...",
  "helper_name": "...", "direction": "pickup|drop", "status": "...", "trip_date": "2026-10-29", "scheduled_start": "07:00",
  "started_at": "...|null", "ended_at": "...|null", "boarded": 31, "expected": 34 }
TransportAttendance = { "id": 1, "trip_id": 812, "trip_date": "...", "direction": "pickup", "route_id": 1, "route_name": "...",
  "student_id": 4, "student_name": "...", "admission_no": "...", "stop_name": "...", "status": "boarded|dropped|absent|pending",
  "boarded_at": "...|null", "dropped_at": "...|null", "corrected_by": "name|null", "note": "...|null" }
RouteSummary = { "route_id": 1, "route_name": "...", "trips": 20, "expected": 680, "boarded": 640, "absent": 40, "rate": 94 }
```

admin-web treats a fix older than 5 minutes as stale and older than 30 minutes as offline.

## 2. Payroll (`payroll`)

Permission: fees (or a payroll permission). **The server calculates every amount**; the page only displays them.

| Method | Path | Notes |
|---|---|---|
| GET/POST | `/salary-structures` | `{name, basic, allowances:[{name, amount}], deductions:[{name, amount}]}`; response adds `gross`, `net`, `assigned` |
| PATCH/DELETE | `/salary-structures/{id}` | 409 when employees are on it |
| GET/POST | `/salary-assignments` | POST `{staff_ids:[...], structure_id, effective_from}` soft-closes prior assignment; GET `?include_history=&staff_id=` |
| GET | `/payroll/preview?month=YYYY-MM&department=` | `{items: PreviewLine[], total_net, already_processed}` |
| POST | `/payroll/process` | `{month}` + `Idempotency-Key`; 409 if processed/paid; authoritative structure path |
| POST | `/payroll-runs/{id}/mark-paid` | Only from `processed` → `paid` |
| GET | `/payroll/audit-events?run_id=&page=` | Process / mark-paid audit trail |
| GET | `/payslips?month=&staff_id=&status=&department=&page=` | |
| GET | `/payslips/{id}` (and `/payslips/{id}/pdf` if available) | |
| GET | `/payroll/summary?year=` | `[{month, processed, pending, failed, total_net, paid?}]` |
| GET/PUT | `/payroll-settings` | Includes `apply_unpaid_leave_adjustment`, `working_days_per_month` |

```json
PreviewLine = { "staff_id": 5, "name": "...", "department": "...", "structure_name": "...|null", "basic": 30000,
  "allowances": 10000, "deductions": 3800, "attendance_adjustment": 1500, "working_days": 26, "paid_days": 25,
  "net": 34700, "eligible": true, "problem": "No salary structure assigned|null" }
Payslip = { "id": 1, "month": "2026-10", "staff_id": 5, "name": "...", "employee_code": "...", "department": "...",
  "designation": "...", "basic": 30000, "allowances": [{"name": "HRA", "amount": 8000}], "deductions": [...],
  "attendance_adjustment": 1500, "working_days": 26, "paid_days": 25, "gross": 40000, "net": 34700,
  "status": "processed|pending|failed", "processed_at": "...|null", "failure_reason": "...|null" }
```

## 3. Announcements and notifications (`notices`)

- `POST/PATCH/DELETE /announcements/{id}` accept `audience: ["all"|"students"|"parents"|"teachers"|"staff"]`,
  `publish_at` and `status: "draft"|"scheduled"|"published"|"archived"`. Lists support `?status=&q=`.
- Portal student/parent announcement lists return **published** rows only, matching audience (`all` or role), excluding soft-deleted.
- `POST /notifications` accepts `audience`; delivery starts `queued`; BackgroundTasks attempts FCM only when
  `firebase_private_key` is configured (otherwise remains queued — never fake `sent`).
- `GET /notifications/{id}`, `POST /notifications/{id}/cancel` (queued/partial only).
- Domain events enqueue rows: leave approve/reject, homework create (at minimum).

## 4. Teacher–parent messages (`messaging`)

| Method | Path | Notes |
|---|---|---|
| GET | `/messaging/policy` | `{can_view, can_send, can_moderate, poll_seconds}` for this admin, from school policy |
| GET | `/conversations/unread-count` | Aggregate `{unread, conversations:[{conversation_id, unread}]}` |
| GET | `/conversations?q=&unread=&flagged=&page=` | Only conversations this admin may see |
| GET | `/conversations/{id}/messages?page=` | 403 if the policy doesn't allow it |
| POST | `/conversations/{id}/messages` | `{body, attachments?}`; attachments require document storage; sent as school-admin actor (not teacher) |
| POST | `/conversations/{id}/read` | Clears unread for this admin |
| PATCH | `/conversations/{id}` | `{flagged}` (moderators) |
| PATCH | `/messages/{id}` | `{hidden}` (moderators); hidden messages return `hidden: true` and moderators still see the text |

```json
Conversation = { "id": 1, "subject": "...", "student_id": 4, "student_name": "...", "class_name": "Class 5 A",
  "teacher": {"user_id": 12, "name": "...", "role": "teacher"}, "parent": {"user_id": 30, "name": "...", "role": "parent"},
  "last_message": "...", "last_message_at": "...", "unread": 2, "flagged": false }
Message = { "id": 1, "conversation_id": 1, "sender": {...}, "body": "...", "attachments": [{"name": "...", "url": "...", "size": 1234, "content_type": "application/pdf"}],
  "sent_at": "...", "hidden": false }
```

Teachers may only message parents of students they teach; parents only teachers of their own children. Attachment URLs
should be short-lived signed links. With no push channel yet, admin-web polls every `poll_seconds`.
