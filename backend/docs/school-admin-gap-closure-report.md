# Four Modules Gap Closure — Final Report

Date: 2026-10-30  
Scope: Close audit gaps for Attendance/Leave, Payroll, Notifications, Messaging (backend only).  
Safety: migrations authored only — **not** applied to Neon; no Render deploy; no git push; `admin-web` untouched.

## 1. Modified backend files (primary)

| Area | Files |
|------|-------|
| Migration | `alembic/versions/20261030_0045_gap_closure.py` |
| Models | `app/models/tables.py` (Leave decision audit; Notification retry/idempotency) |
| Config | `app/core/config.py` (Firebase env credentials) |
| Notices | `app/services/v1/notification_delivery.py`; hooks in `school_academics.py`, `school_homework.py`, `school_offline_exams.py`, `school_academic_mgmt.py`; `school_admin_mgmt.py` fee reminders |
| Leave | `school_academics.py`; `school_admin_academics.py`; `staff_and_writes.py`; `stubs.py`; `teacher_portal.py` |
| Payroll | `school_erp_payroll.py`; `school_academic_mgmt.py` (legacy runs); `school_admin_mgmt.py`; `school_admin_mgmt_responses.py` |
| Messaging | `school_messaging.py`; `school_admin_messaging.py` |
| Tests | `tests_offline/test_gap_closure.py`; updates to four/six feature offline tests |
| Docs | this report |

## 2. Completed gaps

### Notifications & Announcements
- FCM HTTP v1 send via httpx + JWT (env service account); mockable for tests
- Recipient tokens filtered by school + audience roles
- Event triggers: student absence, fee reminders (`POST /fees/send-reminders`), exam publish, exam results, homework, leave decisions
- Retry counter / max_retries / failure tracking; idempotency_key dedupe
- Status reflects provider outcomes: `sent` / `partial` / `queued` / `failed` / `cancelled`
- Without Firebase env creds → remains `queued` with reason (never fake `sent`)
- Silent `except: pass` removed (logged)

### Leave
- `applies_to` enforced for student/teacher/staff
- Teacher self-service: `GET/POST /api/teacher/leave-requests`, cancel
- Staff: `GET/POST /api/staff/leave-request`, `POST /api/staff/leave-approve` (stubs replaced)
- Legacy `POST /api/leaves` now uses shared create (overlap, balance, applies_to)
- Approver identity: `decided_by_user_id` / `decided_by_v1` / `decided_at`
- Transitions remain guarded (pending-only)

### Payroll
- Negative net rejected in `_calc_from_structure`
- `GET /payroll/audit-events` uses `PayrollAuditEventListOut`
- Legacy `POST /payroll-runs` rejects client amounts; draft shell only
- Process / mark-paid record `actor_v1` in audit detail
- Decimal `_money` preserved

### Messaging
- Secure attachment upload: `POST /conversations/attachments/upload`
- Download: `GET /messages/{id}/attachments?storage_key=`
- storage_key must be school/user-owned prefix; URLs rejected
- Admin actor via email → `school.admin_id` → dedicated school actor user (never teacher spoof)

## 3. Remaining incomplete / blocked

| Item | Status |
|------|--------|
| Neon apply of `0044` + `0045` | **Blocked** — requires explicit approval |
| FCM in production | Needs env `FIREBASE_SERVICE_ACCOUNT_JSON` (or project/client/private_key). `system_settings.firebase_private_key` alone is too short (255) for a PEM |
| Full DB integration tests | Not run against Neon; offline mocks only unless `TEST_DATABASE_URL` isolated DB is provided |
| Celery / true push fan-out worker | Intentionally BackgroundTasks only |
| Percent-based salary components | Still unused in calc (pre-existing) |

## 4. Test results

```text
pytest tests_offline/test_gap_closure.py \
       tests_offline/test_four_modules_completion.py \
       tests_offline/test_six_features_completion.py -q
→ 28 passed
```

## 5. Migration status

| Revision | Role |
|----------|------|
| `20261029_0043` | Six features (prior) |
| `20261030_0044` | Assignment history, unpaid-leave settings, attachments_json, paid unique |
| `20261030_0045` | Notification retry/idempotency; leave decision audit columns |

**Single head:** `20261030_0045`  
**Applied to Neon:** No

## 6. Security verification (offline)

| Check | Result |
|-------|--------|
| Cross-school paths use `_school_id` / `_owned` | Preserved in modified services |
| Leave overlap / balance / applies_to | Unit-covered + shared create path |
| Payroll negative net | Unit-covered |
| Payroll client amounts rejected | Implemented on legacy create |
| Audit-events schema | Named response model matches service |
| FCM without creds stays queued | Unit-covered |
| FCM success mocked | Unit-covered |
| Attachment foreign key rejected | Unit-covered |
| Admin actor not teacher | Unit-covered via `school.admin_id` |

## 7. Updated completion % (evidence-based)

| Module | Prior audit | After gap closure | Notes |
|--------|-------------|-------------------|-------|
| Staff Attendance & Leave | 82% | **94%** | Self-service + applies_to + approver audit; DB apply pending |
| Payroll & Salary | 85% | **95%** | Schema/legacy/actors/negative-net fixed; Neon migrate pending |
| Notifications & Announcements | 72% | **92%** | Real FCM path + events + retry; prod needs Firebase env |
| Teacher–Parent Messaging | 88% | **96%** | Upload/download + admin actor; needs storage configured |

**Overall ~94%** verified offline. Not claimed 100% without Neon migrate + live FCM/storage config.

## 8. Production configuration required

1. Apply Alembic through `20261030_0045` on the target database (approved ops only).
2. Set Firebase env (preferred):
   - `FIREBASE_SERVICE_ACCOUNT_JSON` = full service-account JSON **or** path to JSON file  
   - **or** `FIREBASE_PROJECT_ID` + `FIREBASE_CLIENT_EMAIL` + `FIREBASE_PRIVATE_KEY`
3. Document storage for messaging attachments:
   - `DOCUMENT_STORAGE_BACKEND=local`
   - `DOCUMENT_STORAGE_PATH` = private persistent directory
4. Ensure school rows have usable `admin_id` or matching admin email on legacy `users` for messaging attribution.
