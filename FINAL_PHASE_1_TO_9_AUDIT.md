# eSchool SaaS — Final Audit, Phases 1–9

**Date:** 2026-10-19
**Branch:** `main` @ `3aed764` with 35 uncommitted/untracked working-tree entries (unchanged by this audit)
**Scope:** `backend/` (FastAPI) and `admin-web/` (Next.js) in `eSchool-SaasAdminPanel`
**Method:** static inspection plus every check that could run without touching a database, a payment gateway, or the network. No code, environment, database, or Git state was changed. The only file written is this report.

---

## 1. Executive summary

**Recommendation: NOT READY.**

The backend imports cleanly, registers 365 routes with no duplicates, has a single consistent Alembic head, matching dependency pins, and no committed secrets. Every test that can run without a database passes (43/43). That is the full extent of what was directly verified.

What was **not** verified is most of the product: 276 of 319 tests need the Neon test database (their fixtures wipe it), so they were not run. The frontend toolchain is not installed, so no type check, lint, build, or browser run was possible. No server was started against a database.

Release is blocked by:

1. **A confirmed authorization defect** (High): a School Admin of a suspended or deactivated school keeps full CRUD access to school data through `/api/admin/*` with an existing token.
2. **Phase 9 (payments/invoices) exists only as uncommitted, untracked files**, has no frontend, its migration `20261019_0015` is unapplied (database state unknown), and several business rules are undecided.
3. **The Super Admin dashboard shows wrong numbers**: four of its stat cards read fields the API does not return (always 0), and the subscription chart is an equal split per plan, not real data.
4. **No runtime evidence** for Phases 1–8 in this audit. The last recorded full run (`docs/PHASE10_REPORT.md`, 148 tests) predates 171 newer tests and was itself not green in one pass.

### Phase 1–9 status

| Phase | Scope (from `backend/docs`) | Status | Main reason |
|---|---|---|---|
| 1 | v1 auth + user profile | **PARTIAL** | Backend routes present; forgot/reset password UI calls endpoints that do not exist; no login rate limiting; runtime tests BLOCKED |
| 2 | Super Admin auth + school management + public registration | **NOT VERIFIED** | Routes and UI wired consistently; all 44 tests BLOCKED |
| 3 | School Admin role + scoped access | **FAIL** | Suspended-school bypass via `/api/admin/*`; 88 of 105 menu links are placeholders; academics API not used by UI |
| 4 | Plans (packages) | **NOT VERIFIED** | Routes and UI match; 11 tests BLOCKED |
| 5 | Subscriptions, bills, renewals, expiry | **PARTIAL** | Super Admin API complete; no UI for bills or renewals; School Admin cannot read own subscription/bills; expiry not scheduled |
| 6 | Add-ons | **NOT VERIFIED** | Routes and UI match; 9 tests BLOCKED |
| 7 | Super Admin dashboard + reports | **FAIL** | Dashboard cards and chart show incorrect data; 6 dashboard sub-endpoints unused |
| 8 | Settings, audit logs, notifications | **NOT VERIFIED** | Routes and UI match; 6 tests BLOCKED |
| 9 | Razorpay payments, history, invoices | **PARTIAL** | Backend implemented and unit-tested; uncommitted; no frontend; DB tests BLOCKED; migration unapplied; rules pending approval |

---

## 2. Which "Phases 1–9" this audit uses

Two phase schemes exist in the repository:

| Scheme | Location | Used here |
|---|---|---|
| **eSchool SaaS v1 product phases** | `backend/docs/PHASE3_AUDIT.md` … `PHASE10_REPORT.md`, which maps Phase 1–10 to test files | **Yes, primary** |
| Laravel → FastAPI migration programme (Phase 0–10) | root `PHASE*_STATUS.md`, `PHASE_EXECUTION.md` | Summarized only (section 2.1) |

**Limitation:** no original requirement documents exist for Phases 1 and 2. Their requirement lists below are reconstructed from `PHASE10_REPORT.md`, `PHASE10_SECURITY.md`, the API docs, route definitions, and test names. Phases 3–9 have audit notes in `backend/docs`. Where a requirement could not be located, it is marked NOT VERIFIED.

### 2.1 Migration-programme phases (root `PHASE*_STATUS.md`)

By their own status files, these are mostly scaffolds blocked on datasets, Docker, and sign-offs. Examples: Phase 5 = 217 contract stubs (170 stub routes are registered today); Phase 8 = "Admin Next.js SCAFFOLD"; Phase 9 = "Canary SCAFFOLD (gate blocked)". This audit did not re-verify them. They are **NOT VERIFIED** and outside the primary scope.

---

## 3. Phase-by-phase checklist

Legend: **Evidence** = file or route; **Test performed** = what this audit actually ran.

### Phase 1 — Authentication and profile

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Signup, login, logout, `/auth/me`, change password | `app/api/v1/auth.py`; routes `POST /api/v1/auth/{signup,login,logout,change-password}`, `GET /api/v1/auth/me` | Route registration; import | Registered, imports clean | PASS (static) |
| Opaque bearer sessions; expired/revoked → 401; inactive → 403 | `auth_service.resolve_user_from_token` (lines 201–225) | Code read | Logic present | NOT VERIFIED (runtime) |
| Signup cannot set role/school | `PHASE10_SECURITY.md`; `extra=forbid` schemas | Code read | Present | NOT VERIFIED (runtime) |
| Profile `GET/PATCH /api/v1/users/me` | `app/api/v1/users.py`; UI `app/(admin)/settings/page.tsx` | Route/UI mapping | Match | PASS (static) |
| Password hashing | `app/core/security.py` (bcrypt, accepts `$2y$`) | Code read | bcrypt with salt | PASS (static) |
| Forgot / reset password | UI `app/login/LoginForm.tsx:86`, `app/login/reset/page.tsx:45` → `/auth/forgot-password`, `/auth/reset-password` | Route table | **No such v1 routes**; UI shows "not available" on 404 | FAIL |
| Login brute-force protection | `auth_service`, `auth.py` | grep | No rate limit or lockout on v1 or Super Admin login | FAIL (risk) |
| DB URL helpers | `tests/v1/test_db_urls.py` | Ran 5 tests | 5 passed | PASS |
| Behaviour suite | `tests/v1/test_auth_profile.py` (30) | Not run | Needs test DB | BLOCKED |

### Phase 2 — Super Admin auth and school management

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| SA register/login/me (bootstrap gated) | `super_admin/router.py` `POST /register`, `/login`, `GET /me` | Route registration | Registered | PASS (static) |
| School CRUD, activate, suspend, deactivate, provision | `super_admin/schools.py`; 9 routes | Route/UI mapping (`app/(admin)/schools/*`, `lib/school.ts`) | Methods and paths match | PASS (static) |
| School admins CRUD + status | `/super-admin/schools/{id}/admins*` | Route/UI mapping (`SchoolForm.tsx`) | Match | PASS (static) |
| Public school registration (pending approval, rate limited) | `POST /api/v1/schools/register`; `school_registration_service.py` (inactive + not installed, 429 limit) | Code read; UI `RegisterSchoolForm.tsx` | Consistent | NOT VERIFIED (runtime) |
| Unique support email | migration `20261009_0010` | Offline SQL | Index created | PASS (static) |
| Behaviour suites | `test_super_admin_auth` (13), `_flow` (6), `_schools` (23), `test_school_registration` (2) | Not run | Needs test DB | BLOCKED |

### Phase 3 — School Admin role and scoped access

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| `school_admin` role, `assert_school_scope`, `require_school_admin` | `app/api/v1/deps.py:53–90` | Code read | Requires active user + active, installed school | PASS (static) |
| Suspended/deactivated school blocks School Admin | `deps.py` (v1) vs `app/api/deps.py:52–104` (`admin_context`, legacy `/api/admin`) | Code read | **Legacy path checks the user only, never the school**; suspend/deactivate does not revoke sessions (`school_service.py` ~291–305; revocation only in `school_admin_service.py:134`) | **FAIL** (bug B1) |
| School Admin dashboard + modules | `SCHOOL_ADMIN_NAV` (105 links), `lib/schoolModules.ts` | Static mapping script | 17 links map to a live `/api/admin` module; **88 render "No … records are available for this school"**, which reads as empty data, not "not built" | PARTIAL |
| Academics API (`/api/v1/school-admin/academics/*`) | `school_admin_academics.py` (5 routes) | grep frontend | **Not called anywhere in `admin-web`** | PARTIAL (disconnected) |
| Behaviour suite | `test_phase3_school_admin.py` (16) | Not run | Needs test DB. Note: an old `.pytest_cache` (2026-10-05) recorded `test_school_admin_blocked_when_school_suspended_or_deactivated` as last-failed | BLOCKED |

### Phase 4 — Plans

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Plan CRUD + status on `packages` (no separate table) | `super_admin/plans.py`; migration `20261007_0006` | Route table; offline SQL | Present | PASS (static) |
| UI list/create/edit/status | `app/(admin)/packages/page.tsx` → `PlatformResource` (POST, PATCH, PATCH /status) | Method mapping | Match | PASS (static) |
| Behaviour suite | `test_phase4_plans.py` (11) | Not run | Needs test DB | BLOCKED |

### Phase 5 — Subscriptions, bills, renewals, expiry

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Per-school subscription CRUD + status; one active per school | `super_admin/subscriptions.py`; `subscription_service.py` (`_deactivate_active_for_school`, school lock) | Code read | Present | NOT VERIFIED (runtime) |
| Bills CRUD + status | `/super-admin/schools/{id}/subscriptions/{sid}/bills*` | Route table | Present | PASS (static) |
| Renewal once per period | `renew_subscription` (`FOR UPDATE NOWAIT`, unique `(subscription_id, period_start)`) | Code read; `test_calendar_clamping_helpers` ran | 1 passed | PARTIAL |
| Platform list + expire-due | `GET /super-admin/subscriptions`, `POST …/expire-due` | Route table | Present; **no scheduler** (`docs/RENDER.md`) | PARTIAL |
| UI | `components/schools/SchoolBilling.tsx` | grep | Create/list subscriptions and add-ons only. **No UI for bills, bill status, renewals, or renewal history** | PARTIAL |
| School Admin view of own subscription/bills | Route table | — | **No endpoint exists**; menu `/school/subscription` is a placeholder | FAIL (missing) |
| Subscription expiry blocks access | `services/v1/subscription_access.py` | Code read | Always returns `False` (deliberately undecided) | NOT VERIFIED (business rule) |
| Behaviour suites | `test_phase5_subscriptions` (9), `_renewals` (16 of 17), `_expiry` (3), `_history_and_price` (5), `_activation_concurrency` (3), `test_platform_subscriptions` (4), `test_money_precision` (7) | Not run | Needs test DB | BLOCKED |

### Phase 6 — Add-ons

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Add-on catalog CRUD + status | `super_admin/addons.py`; migration `0008` | Route table; offline SQL | Present | PASS (static) |
| School assignment + status | `super_admin/school_addons.py` | Route table; `SchoolBilling.tsx` | Present; UI create/list | PASS (static) |
| Behaviour suite | `test_phase6_addons.py` (9) | Not run | Needs test DB | BLOCKED |

### Phase 7 — Super Admin dashboard and reports

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Platform metrics endpoint | `GET /super-admin/dashboard` (`dashboard_service.platform_dashboard`) | Key comparison | Returns schools, students, plans, subscriptions, addons, bills, bill amounts | PASS (static) |
| Dashboard UI shows those metrics | `admin-web/lib/dashboardData.ts` | Key comparison | **Cards read `classes`, `subjects`, `exams`, `fees`, `attendances`, `expenses`, `leaves`, none of which this endpoint returns → always 0.** Subscription/bill metrics are not shown | **FAIL** (bug B5) |
| Subscription distribution chart | `dashboardData.ts:167–173` | Code read | **Each plan gets `100 / plans.length` percent**, regardless of subscriptions | **FAIL** (bug B6) |
| Dashboard sub-endpoints (`/stats`, `/recent-schools`, `/registrations`, `/school-status`, `/subscriptions`, `/recent-activities`) | `docs/DASHBOARD_API.md`; 6 routes | grep frontend | **None called by the UI** | PARTIAL (disconnected) |
| Reports: schools, subscriptions, bills | `/super-admin/reports/*`; `app/(admin)/reports/page.tsx` | Mapping | Match | PASS (static) |
| Revenue / transactions panels | `dashboardData.ts` | Code read | Always empty arrays → "No revenue data available" (honest empty state, not fake data) | PASS (static) |
| `unavailable_metrics` includes `payment_transactions` | `dashboard_service.py:240–243` | Code read | Stale: the table now exists in Phase 9 code | PARTIAL |
| Behaviour suites | `test_phase7_dashboard_reports` (5), `test_dashboard_*` (24) | Not run | Needs test DB | BLOCKED |

### Phase 8 — Settings, audit logs, notifications

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Platform settings GET/PATCH; secrets returned as `null` + `configured` | `super_admin/settings.py`; `PHASE10_SECURITY.md` | Route table; UI `settings/page.tsx:301` | Match | NOT VERIFIED (runtime) |
| Audit log list (SA only); sanitized metadata | `super_admin/audit_logs.py`; `audit_service.sanitize_metadata` | Ran `test_sanitize_metadata_strips_secrets` | 1 passed | PARTIAL |
| Notifications CRUD + status | `super_admin/notifications.py`; UI `announcements/page.tsx` | Mapping | Match | PASS (static) |
| Behaviour suites | `test_phase8_platform` (6), `test_atomic_audit` (3) | Not run | Needs test DB | BLOCKED |

### Phase 9 — Payments, history, invoices

| Requirement | Evidence | Test performed | Actual result | Status |
|---|---|---|---|---|
| Initiate: server-side amount, idempotency, one payable order per bill | `api/v1/payments.py`, `payment_order_service.py`; index `uq_payment_transactions_bill_open` | Unit tests; migration test | Pass | PARTIAL (DB tests BLOCKED) |
| Verify: signature + gateway fetch; checkout alone never pays | `payment_verification_service.verify_checkout_payment` | Unit tests (binding, transitions, remote match) | Pass | PARTIAL |
| Webhook: signature on raw body, event-id dedupe, capture once, cancelled-bill guard, refunds, mismatch diagnostics | same file | Unit tests (parsing, transitions) | Pass | PARTIAL |
| Payment history (SA + school) with filters | `super_admin/payments.py`, `school_payments.py` | Route table | Present | NOT VERIFIED (runtime) |
| Invoices: list, JSON, PDF (safe headers), once per capture, immutable | `super_admin/invoices.py`, `school_payments.py`, `invoice_service.py`, `invoice_pdf.py` | `test_invoice_pdf_response_headers`, filename test | Pass | PARTIAL |
| Migrations `0013`, `0014`, `0015` | `alembic/versions/` | `alembic heads`, offline SQL, schema tests | Single head; additive | PASS (static) / **applied state NOT VERIFIED** |
| API docs + env vars | `backend/docs/PAYMENTS_API.md`, `.env.example` | Read | Present. **But `PHASE9_AUDIT.md` still says "NOT STARTED", and `RENDER.md` omits `RAZORPAY_*`** | PARTIAL |
| Frontend (checkout, history, invoices) | `admin-web` | grep | **None** (out of scope for Phase 8 backend work, but required for an end-to-end feature) | FAIL (missing) |
| Committed to Git | `git status` | Ran | **All Phase 9 files untracked or modified, uncommitted** | FAIL (release) |
| Behaviour suites | `test_payment_initiate` (12), `_orders` (9), `_verify_webhook` (22), `_history` (6), `test_subscription_invoices` (6) | Not run | Needs test DB | BLOCKED |

---

## 4. Verified working (directly checked in this audit)

- All 145 Python files in `app/`, `tests/`, `alembic/` parse (no syntax errors).
- All 88 `app.*` modules import without error; `app.main` builds.
- 365 API routes registered; **0 duplicate method+path pairs**. v1: 91 routes (67 `/super-admin`, 9 `/school-admin`, 5 `/auth`, 5 `/schools`, 3 `/payments`, 2 `/users`).
- Alembic: single head `20261019_0015`; one branch point (`20261009_0010`) correctly merged at `6bfcc3198722`; full upgrade renders offline to 744 SQL lines; no `DROP`/`TRUNCATE`/type change in any upgrade (the only `DELETE` is Alembic's own `alembic_version` bookkeeping at the merge).
- Models vs migrations: all 34 tables present; all columns present; one missing index (bug B10).
- `pip check`: no broken requirements; all 16 pinned packages match installed versions (Python 3.12.10).
- No secrets in tracked or untracked files or in `subscription-untracked-backup.zip` (one false positive: a fake `ep-example` URL in `tests/v1/test_db_urls.py`). `backend/.env` is gitignored and has never been committed.
- 43 DB-free tests pass (section 9).
- Frontend: every v1 and `/api/admin` call made by `admin-web` matches a registered backend route and HTTP method, except the two password-reset calls (bug B7). Every non-school menu link has a page.

---

## 5. Confirmed bugs

"Confirmed" means proven by code inspection. Where runtime reproduction needs the database, the steps are given but were not executed.

| ID | Severity | Defect | Files | Reproduction (not executed; needs DB) |
|---|---|---|---|---|
| B1 | **High** | School Admin of a suspended/deactivated school keeps read/write access to school data via legacy `/api/admin/*`. `admin_context` accepts the v1 bearer token and checks only `user.status`; suspending a school does not revoke its admins' sessions. `/api/v1/school-admin/*` correctly returns 403, so the two APIs disagree. | `backend/app/api/deps.py:52–104`; `backend/app/services/v1/school_service.py` (suspend/deactivate ~291–305) | 1) SA creates school + School Admin. 2) School Admin logs in (`POST /api/v1/auth/login`) and keeps the token. 3) SA `POST /api/v1/super-admin/schools/{id}/suspend`. 4) `GET /api/v1/school-admin/me` → 403 (correct). 5) `GET /api/admin/students` with the same bearer → expected 403, code path returns 200. Same for POST/PATCH/DELETE. |
| B2 | **High** (release) | All Phase 9 backend code, migrations, tests, and docs are uncommitted (24 untracked + 8 modified files). Only backups (`subscription-backup.patch`, `.zip`) protect them. | `git status` | `git status --short` |
| B3 | Medium | Unauthenticated `POST /api/webhook/{stripe,razorpay,paystack,flutterwave}` append the full request body (no size limit, no signature check) to `backend/data/webhook_events.jsonl`. Disk-fill risk; also confusable with the real `/api/v1/payments/webhook/razorpay`. | `backend/app/api/staff_and_writes.py:486–525` | `curl -X POST <host>/api/webhook/razorpay --data-binary @large.json` → 200 and file grows |
| B4 | Medium | No rate limiting or lockout on `POST /api/v1/auth/login` or `/api/v1/super-admin/login`. | `app/api/v1/auth.py`, `app/services/v1/auth_service.py` | Repeated wrong-password logins are never throttled |
| B5 | Medium | Super Admin dashboard cards always show 0 for Classes, Exams, Expenses, and their sub-metrics; they read keys `/super-admin/dashboard` does not return. | `admin-web/lib/dashboardData.ts:60–130, 151–165`; `backend/app/services/v1/dashboard_service.py:104–245` | Open `/dashboard` as SA with data present |
| B6 | Medium | "Subscription Distribution" chart assigns each plan an equal share instead of real subscription counts (`/super-admin/dashboard/subscriptions` exists but is unused). | `admin-web/lib/dashboardData.ts:167–173` | 3 plans → 33.3% each regardless of subscriptions |
| B7 | Medium | Forgot/reset password UI calls non-existent `/api/v1/auth/forgot-password` and `/reset-password`. Handled with a "not available" message; the feature does not work. | `admin-web/app/login/LoginForm.tsx:86`; `admin-web/app/login/reset/page.tsx:45` | Click "Forgot password" |
| B8 | Medium | School Admins have no API to read their own subscription or bills, so they cannot find a `bill_id` to pay; the "Subscription" menu item is a placeholder. | Route table; `admin-web/lib/nav.ts:272–276` | — |
| B9 | Low | Stale documentation and a misleading test: `PHASE9_AUDIT.md` says payments are NOT STARTED, and `test_phase9_remains_blocked_deferred` passes only because it asserts that stale text. `PHASE10_REPORT.md` says head `0009` and 148 tests (now `0015` and 319). `RENDER.md` omits `RAZORPAY_*` and has a stale "unapplied head" note. `unavailable_metrics` still lists `payment_transactions`. | `backend/docs/*.md`; `tests/v1/test_phase10_security.py:94`; `dashboard_service.py:240` | Read the files |
| B10 | Low | Model declares `index=True` on `staffs.user_id` (`ix_staffs_user_id`), but no migration creates it (autogenerate drift / missing index). | `backend/app/models/tables.py:~263`; migration `20261005_0003` | Offline SQL has no `ix_staffs_user_id` |
| B11 | Low | Next.js same-origin proxy drops `Content-Disposition` (copies only `content-type`), so proxied invoice PDFs lose their filename. It also does not forward `X-Razorpay-*` (webhooks must target the backend directly; documented). | `admin-web/lib/backendProxy.ts:56–72` | — |
| B12 | Low | 88 School Admin menu items render "No *X* records are available for this school", which misrepresents unbuilt modules as empty data. | `admin-web/components/school-admin/SchoolModulePage.tsx:64–80` | Open any unmapped `/school/<slug>` |

### Risks (not confirmed defects)

| Risk | Detail |
|---|---|
| CORS | `allow_origin_regex=r"https://.*\.netlify\.app$"` with `allow_credentials=True` (`main.py:58–59`) trusts every Netlify-hosted site. Impact is limited because v1 uses bearer tokens from `localStorage` and `netlify.app` is a public suffix (SameSite=Lax cookies are not sent cross-site), but it is broader than needed. |
| `/health` disclosure | Unauthenticated `/health` returns the database host and database name (no credentials). |
| Logo upload | `POST /api/school-logos` (Next.js) is unauthenticated (IP rate limit using a spoofable `x-forwarded-for`) and writes to the local disk; persistence on Netlify serverless is NOT VERIFIED. Magic-byte checks and path-traversal guard are present. |
| Dev defaults | `Settings.app_debug=True` and `session_secret="dev-session-secret"` by default; local `.env` has `APP_DEBUG=true` (docs page enabled). Production must override. The local `SESSION_SECRET` is not the default. |
| Verify depends on Razorpay | `POST /payments/verify` performs a read-only Razorpay payment fetch; when unreachable it falls back to `authorized`. |
| Payment edge cases | A lost order-create response can leave a remote order with no local row (documented). Cancelling a bill while a payment is authorized is allowed; a later capture is recorded for manual refund. |

---

## 6. Incomplete and unverified features

- **Runtime behaviour of all phases**: 276 DB tests not run; no server run against a DB; no browser run.
- **Frontend build health**: `admin-web/node_modules` absent; `tsc`, `next lint`, `next build` not run.
- **Database state**: which Alembic revision Neon is at (`alembic current` needs a live connection) is unknown. `0013`–`0015` may be unapplied; the Phase 9 routes will fail with missing-table errors if so.
- **Phase 9 frontend**: checkout, payment history, invoice list/download — not built.
- **Phase 5 UI**: bills, bill status, renewals, renewal history — not built.
- **School Admin modules**: 88 of 105 menu items unbuilt; academics API unused.
- **Dashboard sub-endpoints**: 6 implemented, none consumed.
- **Subscription expiry**: requires an external scheduler (none configured).
- **Password reset**: no backend.
- **Migration-programme phases (root files)**: not re-verified.

---

## 7. Area results

| Area | Result | Notes |
|---|---|---|
| Backend startup/imports | PASS | 88 modules import; app builds. Server not started with a DB (BLOCKED). |
| Router registration | PASS | 365 routes, no duplicates. |
| Auth / sessions / roles | PARTIAL | Logic present and reviewed; runtime BLOCKED; B1, B4. |
| Tenant isolation | **FAIL** | B1 (legacy admin path ignores school status). v1 scoping (`assert_school_scope`) is correct by inspection. |
| Validation / schemas / pagination | NOT VERIFIED | Pydantic `extra=forbid`, `page_size ≤ 100` observed; runtime BLOCKED. |
| Database models / migrations | PASS (static) | Single head, additive, consistent; B10 minor; applied state NOT VERIFIED. |
| Subscriptions / billing | PARTIAL | API present; UI gaps; B8; business rules open. |
| Payments / invoices / webhooks | PARTIAL | Unit-tested; DB tests BLOCKED; uncommitted; no UI; B3 legacy webhook. |
| Configuration / env | PARTIAL | `.env.example` placeholders only (test passes); Razorpay keys absent from local `.env`; `RENDER.md` incomplete. |
| Dependencies | PASS | `pip check` clean; pins match. Frontend deps not installed (BLOCKED). |
| Secrets | PASS | None found in tracked/untracked/backup files. |
| Frontend ↔ API integration | PARTIAL | All paths/methods match except B7; B5/B6 data defects; B11. |
| Frontend type/lint/build/console | BLOCKED | No `node_modules`; installing was out of scope. |

---

## 8. Commands executed

All Python commands ran with `PYTHONDONTWRITEBYTECODE=1` and with `NEON_DATABASE_URL` / `TEST_DATABASE_URL` overridden in the process environment to an unroutable `127.0.0.1:1` address, so any accidental DB access would fail instead of reaching Neon. No environment file was edited. Pytest ran with `--noconftest` (both `conftest.py` files wipe the test DB at import) and `-p no:cacheprovider`.

| # | Command (from `backend/` unless noted) | Exit | Result |
|---|---|---|---|
| 1 | `git status --short`, `git log --oneline`, `git stash list`, `git ls-files \| grep .env` (repo root) | 0 | 35 entries; 32 commits; 0 stashes; only `.env.example` tracked |
| 2 | Python `ast.parse` over `app/`, `tests/`, `alembic/` | 0 | 145 files, 0 syntax errors |
| 3 | Python: import every `app.*` module, build route table | 1 | Results printed (88 modules, 0 import errors, 365 routes, 0 duplicates); exit 1 came from the audit script's own `/dev/null` write on Windows, after the results |
| 4 | Python: print all `/api/v1` and `/api/admin` routes | 0 | Listed |
| 5 | `python -m alembic heads` / `branches` / `history` | 0 / 0 / 0 | Head `20261019_0015`; branch point `20261009_0010` merged |
| 6 | `python -m alembic upgrade head --sql` (offline; no connection) → scratchpad | 0 | 744 lines |
| 7 | grep destructive DDL; Python model-vs-migration diff on the offline SQL | 0 | Only `alembic_version` DELETE; 1 missing index (others were parser artefacts, rechecked by grep) |
| 8 | `pytest --noconftest -p no:cacheprovider --collect-only -q tests` | 0 | 319 tests collected |
| 9 | `pytest --noconftest -p no:cacheprovider -q` on the 43 DB-free tests (listed in section 9) | 0 | **43 passed** |
| 10 | `python -m pip check`; pin-vs-installed script | 0 | No broken requirements; all pins match |
| 11 | `ls` probe for `render.yaml` / `runtime.txt` | 2 | Files do not exist (expected) |
| 12 | `node --version` (v24.19.0), `npm --version` (11.17.0), `ls admin-web/node_modules` | 0 / 0 / 2 | `node_modules` absent → frontend checks BLOCKED |
| 13 | Node/grep static mapping of `admin-web` API calls, menu links, pages (from `admin-web/`) | 0 | See section 3 |
| 14 | Python secret scan (tracked + untracked + zip members; values not printed) | 0 | 1 false positive |
| 15 | `git check-ignore backend/.env`; `git log --all -- backend/.env` | 0 | Ignored; never committed |
| 16 | `git status --short \| wc -l` (end of audit) | 0 | 35 (unchanged) |

Not executed (deliberately): any pytest using DB fixtures, `alembic current`/`upgrade` against a database, `npm install`, `next build`, server start against a database, any Razorpay call.

---

## 9. Test summary

| Category | Count | Detail |
|---|---|---|
| Collected | **319** | `pytest --collect-only` |
| **Passed** | **43** | `tests/test_payment_orders_unit.py` (7), `tests/test_payment_rules_unit.py` (19 incl. parametrized), `tests/test_payment_schema.py` (7), `tests/v1/test_db_urls.py` (5), `test_api.py::test_schema_catalog_includes_core_tables`, `test_phase10_security.py::{test_phase9_remains_blocked_deferred, test_sanitize_metadata_strips_secrets, test_env_example_has_placeholders_only}`, `test_subscription_renewals.py::test_calendar_clamping_helpers` |
| Failed | 0 | Among tests run |
| Skipped | 0 | |
| **Blocked (not run)** | **276** | Depend on `v1_client`/`v1_db`/`client` fixtures that create and wipe the PostgreSQL test schema at import (`tests/conftest.py`, `tests/v1/conftest.py`). The local `.env` has a `TEST_DATABASE_URL`; running these requires your explicit approval of that database and its wipe. |
| Frontend tests | 0 exist | No test runner configured in `admin-web` |

Caveats on coverage:
- `test_phase9_remains_blocked_deferred` passes but asserts a stale document (B9); its pass is not evidence of anything about payments.
- The last recorded full DB run (`docs/PHASE10_REPORT.md`) covered 148 tests and was not green in a single invocation (Neon connection drops); 171 tests have been added since.

---

## 10. Release blockers and fix priority

| Priority | Item | Why |
|---|---|---|
| P0 | **B1** suspended-school access via `/api/admin` | Authorization bypass. Fix in `admin_context` (apply the same school checks as `require_school_admin`) and/or revoke school-admin sessions on suspend/deactivate |
| P0 | **B2** commit Phase 9 work (after review) | Prevent loss; enable CI/review |
| P0 | Run the 276 DB tests against an approved, isolated test DB | No runtime evidence today |
| P0 | Confirm the DB migration revision; apply `0013`–`0015` to staging first | Phase 9 routes need these tables |
| P1 | Decide the open business rules (section 12) | Determines Phase 9 completeness |
| P1 | **B5/B6** dashboard data | Super Admins see wrong numbers |
| P1 | Install frontend deps and run `tsc`, lint, `next build` | No frontend build evidence |
| P1 | **B8** School Admin subscription/bill read API, then Phase 9 frontend | End-to-end payment flow does not exist |
| P2 | **B3** remove or authenticate legacy `/api/webhook/*`; **B4** login rate limiting | Security hardening |
| P2 | **B7** password reset (implement or remove UI) | Broken feature |
| P3 | **B9** docs/test refresh; **B10** index migration; **B11** proxy headers; **B12** placeholder wording; CORS narrowing; `/health` trimming | Hygiene |

---

## 11. Environment and setup requirements

Backend (`backend/.env`, see `.env.example`):

| Variable | Notes |
|---|---|
| `NEON_DATABASE_URL` | Required. `postgresql+psycopg://…?sslmode=require` |
| `APP_ENV` | `production` in production (enables live-key enforcement, blocks DDL) |
| `APP_DEBUG` | `false` in production (hides `/docs`) |
| `SESSION_SECRET` | Strong random value |
| `ALLOW_DDL` | Must be `false` outside tests |
| `FRONTEND_ORIGIN` | Comma-separated admin origins |
| `V1_SESSION_TTL_MINUTES`, `V1_SUPER_ADMIN_EMAIL` | Optional |
| `TEST_DATABASE_URL` | Isolated DB for pytest only (fixtures wipe it) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_CURRENCY` | Required for Phase 9; **not present in the local `.env`**; `rzp_test_` keys outside production |

Runtime: Python 3.12, `pip install -r backend/requirements.txt`, `alembic upgrade head` against the confirmed target, `uvicorn app.main:app`. External scheduler for `POST /api/v1/super-admin/subscriptions/expire-due`. Razorpay webhook URL must point at the backend host: `/api/v1/payments/webhook/razorpay`.

Frontend: Node 20 (Netlify) / Node 24 locally, `npm install` in `admin-web/`, `BACKEND_URL`, `NEXT_PUBLIC_ADMIN_API_URL`.

---

## 12. Payment and subscription business rules — questions for approval

Current implemented behaviour, then the question:

1. **Renewal extends the term before payment.** `renew_subscription` moves `end_date` forward and creates a *pending* bill; payment only marks that bill paid. If the bill is never paid, or the payment fails or is refunded, the school keeps the extended term. *Should renewal take effect only after a captured payment?*
2. **Payment never activates a subscription.** Expired or inactive subscriptions cannot be renewed (`renew` requires `active`) and cannot be reactivated by paying. *Should a lapsed school be able to pay to reactivate?*
3. **Who can renew?** Renewal is Super Admin only. *Should School Admins be able to start a renewal and pay?*
4. **Refunds** set the payment to `refunded` but leave the bill `paid`, the invoice unchanged, and the subscription unchanged. *Should a full refund reopen or cancel the bill, issue a credit note, or shorten the term?*
5. **Unpaid or expired subscriptions do not block access** (`subscription_expiry_blocks_access` always returns `False`). *Which subscription states should block School Admin access?*
6. **Capture on a cancelled bill** is recorded for manual refund and issues no invoice. *Is manual refund the intended process, or should cancelling a bill with an authorized payment be prevented?*
7. **Bill status can be set to paid manually by a Super Admin** with no payment; a later gateway capture still issues an invoice. *Is manual "paid" allowed alongside gateway payments?*

---

## 13. Final release recommendation

**NOT READY.**

There is one confirmed High-severity authorization defect (B1). The newest phase is uncommitted and has no frontend or applied migration. The dashboard shows incorrect figures. 86% of the test suite (276/319) and the entire frontend build could not be verified in this audit. The project should not be declared error-free: the checks that ran passed, but most behaviour remains unverified.
