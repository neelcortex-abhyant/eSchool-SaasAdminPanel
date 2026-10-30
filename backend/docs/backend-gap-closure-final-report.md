# Backend Gap Closure & Production Readiness — Final Report

Date: 2026-10-30  
Scope: Backend-only remediation from the API ↔ Admin-Web integration audit.  
Constraints honored: no `admin-web/` changes; no duplicate leave/payroll/notification/messaging APIs; no Neon migrate; no commit/push/deploy.

---

## 1. Issues identified

| ID | Issue | Severity |
|---|---|---|
| L1 | `PATCH /academics/leaves/{id}` silently dropped `status` and returned success — Admin Web Approve/Reject appeared to work without changing status | **Critical** |
| L2 | Need stronger offline coverage for approve/reject/cancel, cancelled≠approvable, status `3` | High |
| P1 | Client amounts on `POST /payroll/process` were ignored silently (better as explicit 422) | Medium |
| P2 | Process path needed explicit rollback on mid-run failure | Medium |
| P3 | Legacy `POST /payroll-runs` client items already rejected — needed regression test | Low |
| N1 | OpenAPI named-response gap for fee reminders write | Low (test guardrail) |
| M1 | Attachment payloads lacked additive `name` / `size` / authorized `download_path` aliases | Medium (contract completeness) |
| M2 | OpenAPI named-response gap for attachment upload | Low |
| T1 | Four wave-parity offline tests still asserted Alembic head `20261029_0043` while head is `20261030_0045` | Medium (CI) |

Already sound (verified, not reimplemented): dedicated leave decision routes; negative net payroll; mark-paid transitions; FCM never fake-`sent`; notification cancel/idempotency/retries; messaging storage ownership + admin actor; migrations `0044`→`0045` linear head.

---

## 2. Issues fixed

| ID | Fix |
|---|---|
| L1 | `update_leave` raises **422** when `status` is present; message points to `/approve`, `/reject`, `/cancel` |
| L2 | Offline tests for PATCH rejection, approve/reject/cancel, cancelled guard, status `3` |
| P1 | `process_payroll` rejects body keys `items`/`total_amount`/`gross`/`net`/`deductions` with 422 |
| P2 | `process_payroll` wraps work in try/except and **`db.rollback()`** on failure |
| P3 / mark-paid | Offline tests for mark-paid (processed→paid, draft 409), legacy items rejection |
| N* | Offline tests: cancel queued; cannot cancel sent; max retries; mock FCM failure → `failed` |
| M1 | Additive attachment aliases via `_attachment_public` (`name`, `size`, `download_path`); no raw storage URLs |
| M2 / N1 | Named OpenAPI schemas: `AttachmentUploadOut`, `FeeRemindersOut` |
| T1 | Wave parity / FE gaps head asserts updated to `20261030_0045` (down_revision chain preserved) |

---

## 3. Existing APIs reused

No new business endpoints. Reused:

- `POST /api/v1/school-admin/academics/leaves/{id}/approve|reject|cancel`
- `PATCH /api/v1/school-admin/academics/leaves/{id}` (non-status fields only)
- `POST /api/v1/school-admin/payroll/process`, `POST .../payroll-runs/{id}/mark-paid`, `GET .../payroll/audit-events`
- `POST /api/v1/school-admin/payroll-runs` (legacy draft shell)
- Notification enqueue/delivery/cancel in `notification_delivery.py`
- `POST .../conversations/attachments/upload`, `GET .../messages/{id}/attachments`

---

## 4. Genuinely new APIs

**None.** Only OpenAPI response model classes were added for existing routes (`AttachmentUploadOut`, `FeeRemindersOut`).

---

## 5. Files modified (this remediation)

| File | Change |
|---|---|
| `app/services/v1/school_academics.py` | Leave PATCH status → 422 |
| `app/services/v1/school_erp_payroll.py` | Client-amount 422; transactional rollback on process |
| `app/services/v1/school_messaging.py` | Additive attachment aliases + download_path |
| `app/api/v1/school_admin_messaging.py` | `AttachmentUploadOut` + named 201 response |
| `app/api/v1/school_admin_mgmt.py` | Named response on fee reminders |
| `app/schemas/v1/school_admin_mgmt_responses.py` | `FeeRemindersOut` |
| `tests_offline/test_gap_closure.py` | Expanded leave/payroll/notification/messaging tests |
| `tests_offline/test_*_wave_parity.py` / `test_frontend_api_gaps.py` | Head → `0045` |
| `docs/backend-gap-closure-final-report.md` | This report |

`admin-web/` — **not modified**.

---

## 6. Database migration status

| Revision | Role | Applied to Neon? |
|---|---|---|
| `20261029_0043` | Prior six-features / ops base | Not verified this session |
| `20261030_0044` | Assignment history, unpaid-leave settings, attachments_json, paid uniqueness | **Not applied** (forbidden without approval) |
| `20261030_0045` | Notification retry/idempotency; leave `decided_*` | **Not applied** |

- Single Alembic head: **`20261030_0045`** (static ScriptDirectory check).
- No new forward migration required (models already match 0044/0045).
- Runtime migration upgrade on an isolated test DB: **pending** (no approved isolated DSN this session).

---

## 7. Tests executed and results

```text
python -m pytest tests_offline/test_gap_closure.py \
  tests_offline/test_four_modules_completion.py \
  tests_offline/test_academic_mgmt_wave_parity.py \
  tests_offline/test_erp_wave_parity.py \
  tests_offline/test_frontend_api_gaps.py \
  tests_offline/test_school_settings_wave_parity.py -q --tb=short
→ 56 passed

python -m pytest tests_offline -q --tb=line
→ 123 passed, 1 warning
```

Integration tests against a live isolated database: **not run** (no explicitly approved safe test database URL).  
Production Neon: **not touched**.  
Live Firebase / real FCM: **not run** (mocked in offline tests only).

---

## 8. Security verification results

| Control | Result | Evidence |
|---|---|---|
| Leave status cannot be smuggled via PATCH | Code + unit test | 422 on `status` |
| Decision transitions pending-only | Code + unit test | 409 for cancelled/approved misuse |
| Tenant ownership on leave rows | Existing `_owned` | Code verified; live cross-school probe UNVERIFIED |
| Payroll amounts not client-overridable | 422 on process + legacy runs | Unit tests |
| Process atomicity | rollback on exception | Code verified |
| Mark-paid state machine | processed→paid; draft blocked | Unit test |
| FCM never fake-sent | queued when unconfigured | Unit test |
| Notification cancel | sent blocked | Unit test |
| Attachment storage_key ownership / no URL keys | 422 | Unit test |
| Attachment download_path is API path, not private URL | Alias design | Unit test |
| Admin actor not teacher spoof | Existing `ensure_school_admin_actor` | Prior + retained tests |
| Secrets in OpenAPI / logs | No private key exposure in responses | Prior OpenAPI guards still pass |

---

## 9. Remaining blockers

1. **Admin Web** still PATCHes leave `{status}` — will now receive **422** until FE is updated to call approve/reject (out of scope here).
2. Alembic **`0044`/`0045` not applied** to any approved environment.
3. **FCM production** needs `FIREBASE_SERVICE_ACCOUNT_JSON` (or project/email/key env); without it notifications stay `queued`.
4. **Document storage** must be configured for attachment upload/download.
5. No isolated DB integration / live E2E verification this session.
6. Admin Web still does not wire mark-paid, notification cancel, attachment upload UI (frontend backlog).

---

## 10. Runtime verification limitations

| Layer | Status |
|---|---|
| Code verified (review + static contracts) | Yes |
| Unit / offline tested | Yes (123 passed) |
| Database integration tested | **No** — pending approved isolated DSN |
| Live external FCM verified | **No** — mocked only |
| Production deployment verified | **No** — not deployed |

---

## 11. Final backend completion percentage

**Estimated backend readiness for the audited four-module surface: ~92% code-complete / offline-verified.**

Calculation (honest, not 100%):

| Slice | Weight | Score | Notes |
|---|---:|---:|---|
| Leave decision correctness + PATCH honesty | 25% | 24 | Fixed; FE still wrong (backend done) |
| Payroll calc/process/mark-paid/audit | 20% | 19 | Hardened + tested offline |
| Notifications delivery/cancel/idempotency | 20% | 18 | Sound offline; live FCM pending |
| Messaging auth + attachments | 15% | 14 | Aliases + ownership; storage env pending |
| Migrations authored / single head | 10% | 9 | Authored; not applied |
| Offline regression suite green | 10% | 10 | 123 passed |

**Weighted ≈ 92%.**

Deducted for: unapplied migrations, no isolated DB run, no live FCM, no production deploy, Admin-Web integration still broken for leave (product E2E incomplete even though backend is correct).

**Do not claim 100%.** Production-ready claim requires applied migrations on a verified environment, isolated DB integration tests, configured FCM/storage, and Admin-Web leave client fix.

---

## Phase 5 checklist

- [x] `admin-web/` unmodified  
- [x] No duplicate decision/process/send/attachment APIs  
- [x] No Neon migrate / commit / push / deploy  
- [x] Offline suite green  
- [x] Report distinguishes code / unit / DB / live / prod layers  
