# School Admin Four Modules — Implementation Report

Date: 2026-10-30  
Scope: Staff Attendance/Leave, Payroll, Notifications/Announcements, Teacher–Parent Messaging (backend only).  
Safety: migration `20261030_0044` authored only — **not** applied to Neon; no Render deploy; no git push; `admin-web` untouched.

## Completion matrix

| Module | Requirement areas | Status | Evidence |
|--------|-------------------|--------|----------|
| 1 Staff Attendance & Leave | Status enum; reports; leave_type on WriteBody; overlap; approve/reject/cancel; balance gate | **Complete** | `normalize_staff_attendance_status`; enriched report summaries; `POST …/leaves/{id}/approve\|reject\|cancel`; overlap 409; balance check on approve; offline tests |
| 2 Payroll & Salary | Assignment history; unpaid-leave adj; Decimal 2dp; paid status; dept filters | **Complete** | `effective_to` soft-close; `_assignment_for_month`; settings flag; `POST /payroll-runs/{id}/mark-paid`; preview/payslips `department`; audit-events; legacy runs deprecated in OpenAPI |
| 3 Notifications & Announcements | Portal filters; event enqueue; BackgroundTasks; FCM if configured | **Complete** | Portal published+audience+not-deleted filter; leave + homework enqueue; `BackgroundTasks` delivery; stays `queued` without FCM SDK; get/cancel notification |
| 4 Messaging | Admin actor; unread-count; storage-backed attachments | **Complete** | `resolve_school_admin_actor` (no teacher fallback); unread-count admin/teacher/parent; attachments require configured storage |

**Complete** = routes + service logic + models/migration `0044` + offline tests with real results.

## Migration

- File: `alembic/versions/20261030_0044_four_modules_completion.py`
- Revises: `20261029_0043`
- Single head: `20261030_0044`
- **Not applied** to production Neon in this delivery

Adds: `salary_assignments.effective_to` + unique current index; payroll settings unpaid-leave flag / working days; payroll run unique covers `processed|paid`; `conversation_messages.attachments_json`.

## Key API additions / changes

### Leave / attendance
- Staff attendance statuses: `present|absent|late|half_day|leave`
- `POST /academics/leaves/{id}/approve|reject|cancel`
- Leave create accepts `leave_type_id` / `leave_type` via WriteBody

### Payroll
- `GET /payroll/preview?month=&department=`
- `POST /payroll/process` (authoritative); legacy `POST /payroll-runs` **deprecated**
- `POST /payroll-runs/{run_id}/mark-paid`
- `GET /payroll/audit-events`
- `GET /salary-assignments?include_history=&staff_id=`
- `PUT /payroll-settings` `{apply_unpaid_leave_adjustment, working_days_per_month}`
- Adjustment rule (when flag on): `attendance_adjustment = -(gross / working_days) * unpaid_approved_leave_days` (2dp). No PF/ESI/TDS invented.

### Notices
- Portal `/student/announcements`, `/parent/announcements`: published + audience + not soft-deleted
- `GET /notifications/{id}`, `POST /notifications/{id}/cancel`
- Create notification schedules BackgroundTasks delivery attempt
- Leave approve/reject and homework create enqueue notification rows

### Messaging
- `GET /conversations/unread-count` (+ teacher/parent variants)
- Admin sender never remapped to conversation teacher
- Message `attachments` metadata only when document storage configured (503 otherwise)
- Polling via `poll_seconds` unchanged (no WebSockets)

## Tests

```text
pytest tests_offline/test_four_modules_completion.py tests_offline/test_six_features_completion.py -q
```

## Explicit non-goals honored

- No `admin-web` changes
- No Celery/RQ
- No invented statutory payroll formulas
- No Neon migrate / Render deploy / git push without separate approval
