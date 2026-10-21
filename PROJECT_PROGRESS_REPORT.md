# eSchool SaaS Admin Panel — Complete Progress Report

**Report date:** 2026-10-21  
**Repository:** `eSchool-SaasAdminPanel`  
**Branch inspected:** `main` @ `41c97f5` (matches `origin/main`)  
**Method:** Evidence from Git history, current working tree, backend code, Alembic graph (offline), and existing audit/status documents. No migrations were applied. No production database was queried. No secrets, tokens, or full database URLs are included. No existing project files were modified except for creating this report.

---

## 1. Executive Summary

### Overall status

The project has a **substantial FastAPI Super Admin / School Admin backend** covering auth, schools, plans, subscriptions, bills, renewals, add-ons, dashboard/reports, settings/audit/notifications, Razorpay payments, payment history, invoices, School Admin RBAC, and password reset.

The **Next.js admin frontend (`admin-web/`) was deleted** in commit `41c97f5` (2026-10-20). As of this audit, this repository’s tracked tree contains `backend/`, migration/ops scaffolding (`baseline/`, `contract-tests/`, `ops/`, `datasets/`), and docs — **not a runnable admin UI**.

### Estimated progress

| Scope | Estimate | Basis |
|---|---|---|
| Backend SaaS platform APIs (auth → payments → RBAC) | **~70–80% implemented in code** | Routes, models, migrations, and large test suites exist in Git; much of this was previously exercised on an isolated test DB in earlier sessions/docs |
| End-to-end product (API + admin UI + ops ready) | **~35–45%** | Backend strong; **frontend removed**; many School Admin academic modules still stubs/legacy; automatic expiry and tax/legal invoice decisions open; production migration application not confirmed in this audit |
| Laravel → FastAPI full migration programme (root `PHASE*_STATUS.md`) | **Mostly scaffold / not verified** | Own status files still describe datasets, canary, and cutover as blocked |

These percentages are **evidence-based ranges**, not inventing precision. They weigh: (a) code present and documented, (b) whether a UI exists to use it, (c) whether runtime/production verification is available in this audit.

### Production-ready?

**No.**

Reasons with evidence:

1. **No admin frontend in the current repo** (`admin-web/` deleted at `41c97f5`; `Test-Path admin-web` → false).
2. **Production/staging migration state was not re-verified** in this audit (by design: no live DB access). Alembic head offline is `20261020_0016`. Whether Render/Neon has applied `20261017_0013`–`20261020_0016` is **unknown here**.
3. **Subscription expiry does not auto-run**; access policy still defaults to allow (`subscription_access.py` always returns `False`). Docs describe a future 403 that the code does not yet enforce.
4. **Tax / GST / seller legal invoice content** still unresolved (nullable tax columns; receipt wording).
5. **Flutter student/staff apps** and full legacy route parity are outside this repo’s completed surface; migration Phase 0–10 docs remain largely scaffolded.
6. This audit **did not re-run the full pytest suite** (avoids wiping the shared test DB without an explicit isolated confirmation pass in this session). Historical test evidence exists in docs and prior phase work, but is not a fresh green run as of today.

---

## 2. Work Completed From Start to Today

### 2.1 Repository bootstrap and Neon migration (2026-10-03 → 2026-10-06)

| Item | What landed | Evidence |
|---|---|---|
| Initial repo | Scaffold | Commit `2edfbe6` Initial Setup |
| Auth + Alembic | `v1_users`, sessions, Neon | `a8d78b0`, `a8fd66d`; migrations `20261005_0001`–`0003` |
| Frontend ↔ API wiring / Netlify fixes | Login proxy to Render | `a26eaef` … `d35749c` |
| Marketing / admin UI theme | SchoolSarthi / cream-amber UI (later removed with `admin-web`) | `6ba368b`, `a849b56` |

### 2.2 Security hardening and core SaaS modules (2026-10-07 → 2026-10-13)

| Feature | Implemented | Commits / files | Verification evidence |
|---|---|---|---|
| Phase 10 security hardening | Opaque sessions, role guards, secret redaction | `bfa2f10`; `docs/PHASE10_SECURITY.md`, `PHASE10_REPORT.md` | Doc claims **148 tests PASS** on `eschool_saas_test` (historical; Neon flakes noted) |
| Plans (`packages`) | CRUD + status | migration `0006`; `super_admin/plans.py` | Tests exist (`test_phase4_plans.py`); not re-run today |
| Subscriptions + bills | CRUD, status, school lock pattern | migration `0007` | `test_phase5_*` present |
| Add-ons | Catalog + school assignment | migration `0008` | `test_phase6_addons.py` present |
| Audit logs + notifications | SA-only audit; notifications CRUD | migration `0009` | `test_phase8_platform.py` present |
| Super Admin dashboard APIs | Platform metrics endpoints | `fb486f6`; `docs/DASHBOARD_API.md` | Dashboard UI historically mismatched API keys (see Oct 19 audit); UI now deleted |
| School management UI/API alignment | Create/edit/profile, status actions | `6a5e4d9` … `5d5e70d` | Frontend later deleted |

### 2.3 Subscriptions deepening (2026-10-16 → 2026-10-17)

| Feature | Implemented | Evidence |
|---|---|---|
| Renewals + agreed price | Renewal API, snapshots, `agreed_price` | `8edb6cf`; migrations `20261015_0011`, `20261016_0012` |
| Alembic merge | Profile + subscription branch merge | `024f4f9`; `6bfcc3198722` |
| Platform subscription list / expire-due | List + manual expire endpoint | `subscriptions.py`; `docs/RENDER.md` (external cron required) |
| Money precision | Half-up paise/rupee helpers | `test_money_precision.py` |
| Access policy stub | Always allow | `subscription_access.py` |

### 2.4 Payments, history, invoices (backend) — committed 2026-10-19

Earlier agent work (Phases 2–7 payment programme) was committed as:

| Commit | Summary |
|---|---|
| `1ea3eda` | Payment transactions, webhooks, history, invoices, docs, tests |
| `cdf95fa` | Payment summary + status filter fixes |
| `56ecdd1` / `9c5a30f` | Frontend payment/plan screens (**later deleted**) |

**Backend capabilities present today:**

- `POST /api/v1/payments/initiate`, `/verify`, `/webhook/razorpay`
- `GET /api/v1/super-admin/payments`, `/{id}` (+ summary fields per later fix)
- `GET /api/v1/schools/{id}/payments`
- Invoice JSON + PDF: school-scoped and Super Admin routes
- Migrations: `20261017_0013`, `20261017_0014`, `20261019_0015` (bill open-order guard)
- Docs: `backend/docs/PAYMENTS_API.md`
- Models: `PaymentTransaction`, `PaymentWebhookEvent`, `SubscriptionInvoice`, counters
- PDF via `fpdf2`; tax columns nullable (not invented)

**Historical verification (not re-run today):** prior sessions documented green runs for payment schema/unit, initiate, verify/webhook, history, and invoice tests on `eschool_saas_test`. `FINAL_PHASE_1_TO_9_AUDIT.md` (2026-10-19 @ `3aed764`) described payments as still uncommitted; **that is outdated** — payments are now on `main`.

### 2.5 School Admin RBAC + password reset (2026-10-20)

| Feature | Implemented | Evidence |
|---|---|---|
| Admin roles / permissions | Catalog + assignment APIs | `41c97f5`; `rbac.py`; `docs/SCHOOL_ADMIN_RBAC_API.md` |
| Password forgot/reset + invite | Routes + mailer + rate limits | `auth.py` forgot/reset; `password_reset_service.py`; `rate_limit.py` |
| Legacy `/api/admin` school gate | Suspended/deactivated school check | `app/api/deps.py` `require_active_admin_school` (addresses Oct 19 High finding for that path) |
| **Frontend removal** | Entire `admin-web/` deleted | Same commit `41c97f5` (~14.9k lines removed) |

### 2.6 Intentionally incomplete / open product decisions

| Topic | Current behaviour | Evidence |
|---|---|---|
| Expired subscription blocks School Admin | **Does not block** | `subscription_access.py` returns `False`; docs still mention a 403 message |
| Automatic expiry | Manual `POST …/expire-due` only | `RENDER.md` |
| GST / tax invoice | Tax fields null; receipt not a tax invoice | Invoice model + `invoice_pdf.py` |
| Capture renews/activates subscription | **No** — bill paid only | Payment verification service design |
| School Admin own subscription/bills list API | **No dedicated school-admin subscription read API found** under `/api/v1/school-admin` | Grep of `school_*.py` shows payments/invoices, not bill list |
| Feature allowlist by plan | Not implemented | Prior audits |
| Admin UI checkout (Razorpay Checkout) | **Not present** (frontend gone) | No `.ts/.tsx` matches for Razorpay in repo |

---

## 3. Work Timeline

| When | Milestone |
|---|---|
| **2026-10-03** | `2edfbe6` Initial Setup |
| **2026-10-05** | Backend auth + first Alembic revisions |
| **2026-10-06** | Shared Neon PostgreSQL; Netlify/Render login wiring |
| **2026-10-07–08** | Premium admin UI; Phase 10 security; connect live school APIs |
| **2026-10-09–13** | School CRUD UX; dashboard APIs; email uniqueness |
| **2026-10-15–16** | School Admin dashboard UI; subscription renewals / agreed price; merge migrations |
| **2026-10-17** | Super Admin plan/subscription UI; payment screens (frontend); payment backend still largely uncommitted until 19th |
| **2026-10-19** | `1ea3eda` commits payments/invoices backend; `FINAL_PHASE_1_TO_9_AUDIT.md`; payment summary fix `cdf95fa` |
| **2026-10-20** | `41c97f5` School Admin RBAC + password reset; **deletes `admin-web/`** |
| **2026-10-21** | This progress report (working tree clean except untracked backups/SQL/`eschool/`) |

---

## 4. Feature-Wise Status

| Feature | Status | Evidence | Remaining Work |
|---|---|---|---|
| v1 signup/login/logout/me/change-password | Implemented but not fully verified | Routes in `auth.py`; historical Phase 10 tests | Fresh suite run; confirm production sessions |
| Forgot / reset password | Implemented but not fully verified | Routes + `password_reset_service.py` + tests in Git | SMTP/`ADMIN_RESET_URL` ops config; email delivery proof |
| Login rate limiting | Implemented but not fully verified | `rate_limit.py`; `test_auth_limits.py` | Confirm multi-instance behaviour (in-process limits) |
| Super Admin auth + school CRUD | Implemented but not fully verified | `super_admin/schools.py`; historical tests | Fresh run; UI gone |
| Public school registration | Implemented but not fully verified | `POST /schools/register` | UI gone; ops rate-limit monitoring |
| School Admin scoped access (v1) | Implemented but not fully verified | `require_school_admin` + school status/installed | Product rule for expired subscription |
| Legacy `/api/admin` suspended-school gate | Implemented but not fully verified | `require_active_admin_school` in `deps.py` | Confirm all legacy entry points covered by tests |
| School Admin RBAC permissions | Implemented but not fully verified | `rbac.py`, RBAC tests, API doc | Frontend enforcement UI missing; `GET /school-admin/me` roles limitation noted in docs |
| Academics API (`/school-admin/academics`) | Partially implemented | Routes exist | Most School Admin modules historically placeholders; no frontend |
| Plans | Implemented but not fully verified | Plans API + tests | UI deleted |
| Subscriptions + bills (Super Admin) | Implemented but not fully verified | Subscriptions API | School Admin cannot list own bills via dedicated API |
| Renewal + history + agreed price | Implemented but not fully verified | Service + migrations | Confirm migrations applied on deploy target |
| Expire-due | Partially implemented | Endpoint exists; no scheduler | External cron + ops runbook execution |
| Subscription access blocking | Not implemented | Stub always `False` | Product decision + implementation |
| Add-ons | Implemented but not fully verified | Add-on APIs + tests | UI deleted |
| Super Admin dashboard APIs | Implemented but not fully verified | Dashboard routes | Historical UI field mismatch moot (UI gone); `unavailable_metrics` still lists `payment_transactions` despite table existing |
| Reports / settings / audit / notifications | Implemented but not fully verified | Routes + docs | UI deleted |
| Razorpay initiate/verify/webhook | Implemented but not fully verified | Payments code + `PAYMENTS_API.md` + tests in Git | Live gateway never used in audits; production keys/env |
| Payment history APIs | Implemented but not fully verified | SA + school list/detail | Frontend integration |
| Invoices + PDF | Implemented but not fully verified | Invoice service/PDF + tests | Tax/legal decisions; frontend download UX |
| Admin Next.js UI | Not implemented | `admin-web/` deleted at `41c97f5` | Rebuild or restore UI; payment checkout Phase 8 |
| Razorpay Checkout in browser | Not implemented | No frontend SDK usage in repo | Depends on admin UI restore |
| Flutter apps (student/staff) | Unable to determine | Separate repos exist; not audited in depth here | Separate audit |
| Full Laravel route parity / cutover | Partially implemented / blocked | Root `PHASE*_STATUS.md` scaffolds; many stubs | Datasets, canary, DNS cutover |
| Production DB migrations applied | Unable to determine | Offline head `20261020_0016` only | Confirm target DB with safe `alembic current` on staging |
| Celery/Redis workers | Not implemented | Not in payment phases; ops docs only | Only if product requires them |

---

## 5. Pending Work

### P0 — Security / data-loss / release blockers

1. **Restore or replace the admin frontend**  
   **Why:** Without UI, operators cannot run the product from this repo.  
   **Done when:** Authenticated Super Admin and School Admin flows work again against live APIs (login, schools, subscriptions, payments).

2. **Confirm and apply Alembic heads on the intended staging DB (then production)**  
   **Why:** Payment/invoice/RBAC tables may be missing if only older revisions were applied.  
   **Done when:** Staging `alembic current` equals `20261020_0016` after an approved `upgrade`, with DB name printed first. Do not apply blindly.

3. **Close subscription-access product rule**  
   **Why:** Docs advertise blocking expired subscriptions; code does not.  
   **Done when:** Explicit rule implemented or docs updated to match allow-all, with tests.

4. **Production secrets / Razorpay mode checks**  
   **Why:** Live vs test key rules exist in code; misconfiguration is a release risk.  
   **Done when:** Staging uses `rzp_test_`; production checklist confirms `rzp_live_` only in production, secrets never in frontend.

### P1 — Core functionality

5. **School Admin billing UX + APIs for payable bills**  
   **Why:** Payment initiate needs bill/subscription/school ids; School Admin currently lacks a clear own-bills listing API.  
   **Done when:** School Admin can see payable bills from authorized APIs and pay via Checkout → verify.

6. **Wire expire-due to an external cron**  
   **Why:** Active subscriptions past `end_date` stay active until someone calls the endpoint.  
   **Done when:** Documented job runs with Super Admin token against staging/production.

7. **Invoice tax / legal content decision**  
   **Why:** Current PDF is a payment receipt without GSTIN/rate.  
   **Done when:** Business signs off format; implementation stores configured tax or remains explicitly non-tax.

8. **Re-run full backend regression on isolated `eschool_saas_test`**  
   **Why:** ~464 test functions / 45 files; last full green narrative predates large payment+RBAC growth.  
   **Done when:** Confirmed DB name `eschool_saas_test`, suite green (or documented flakes only).

### P2 — Improvements / cleanup / docs

9. Update `FINAL_PHASE_1_TO_9_AUDIT.md` or supersede it (payments now committed; frontend gone).  
10. Remove or quarantine untracked `subscription-backup.*`, `eschool/`, `pending-review.sql`, `review.sql` after review.  
11. Dashboard `unavailable_metrics` should stop listing `payment_transactions` if metrics are available.  
12. Migration-programme Phases 0–10 (datasets, canary, cutover) remain scaffolded — track separately from SaaS API work.  
13. Credit-note / refund invoice workflow still documented as future work.

---

## 6. Testing Status

### Safety note (this audit)

Tests that wipe PostgreSQL via `tests/v1/conftest.py` were **not executed in this session**. Isolation was not re-confirmed against a live connection for a full suite run. Offline-only: Alembic heads via `ScriptDirectory` → `['20261020_0016']`.

### Inventory

| Metric | Value |
|---|---|
| Test files under `backend/tests` | 45 |
| Functions matching `^def test_` | 464 |

### Historical evidence (documents / prior work)

| Source | Result | Caveat |
|---|---|---|
| `backend/docs/PHASE10_REPORT.md` | 148 PASS on `eschool_saas_test` | Predates payments/RBAC; Neon mid-suite flakes |
| `FINAL_PHASE_1_TO_9_AUDIT.md` (2026-10-19) | 43/43 offline PASS; DB suites BLOCKED in that audit | Written when payments were still uncommitted |
| Prior payment phase sessions | initiate / verify / history / invoice suites reported green on test DB | Not re-run today |
| Frontend lint/typecheck/build | **No evidence in current tree** | `admin-web` deleted |

### Not run today

- Full `pytest`  
- Frontend build / typecheck / e2e  
- Live Razorpay  
- Production DB connectivity checks  

---

## 7. Git and Deployment Status

### Git

| Item | Value |
|---|---|
| Branch | `main` |
| HEAD | `41c97f5` — *Add school admin RBAC and password reset* |
| Remote | `origin` → `https://github.com/neelcortex-abhyant/eSchool-SaasAdminPanel.git` |
| Sync | Up to date with `origin/main` (no ahead/behind commits observed) |
| Staged changes | None |
| Modified tracked files | None (clean index) |
| Untracked | `backend/pending-review.sql`, `backend/review.sql`, `eschool/`, `subscription-backup.patch`, `subscription-untracked-backup.zip` (plus this new report once saved) |

### Important commits (selected)

| Hash | Date | Subject |
|---|---|---|
| `2edfbe6` | 2026-10-03 | Initial Setup |
| `a8fd66d` | 2026-10-06 | Migrate backend to shared Neon PostgreSQL |
| `bfa2f10` | 2026-10-08 | Complete Phase 10 security hardening |
| `fb486f6` | 2026-10-13 | Complete Super Admin dashboard APIs |
| `8edb6cf` | 2026-10-16 | Improve subscription management and renewal flows |
| `1ea3eda` | 2026-10-19 | feat: add payment invoices and secure school admin access |
| `cdf95fa` | 2026-10-19 | Fix super admin payment summary and status filters |
| `41c97f5` | 2026-10-20 | Add school admin RBAC and password reset (**deletes admin-web**) |

### Alembic (code graph only)

- **Head:** `20261020_0016`  
- **Parents chain includes:** payment `0013` → invoices `0014` → bill guard `0015` → RBAC/reset `0016`  
- **Applied on production?** **Unable to determine** in this audit (no DB queried; no migration run)

### Deployment

- Ops docs describe Render + Neon + Netlify historically (`RENDER.md`, Netlify commits).  
- **Current production deployment health was not verified** in this audit. Do not treat docs as proof the live site matches `41c97f5`.

---

## 8. Final Progress Count

Counts below match the status table in section 4 (one row = one feature line).

| Status | Count |
|---|---|
| Complete and verified | **0** |
| Implemented but not fully verified | **18** |
| Partially implemented | **4** |
| Not implemented | **4** |
| Blocked / unable to determine | **3** |
| **Total feature rows** | **29** |

**Why “Complete and verified” is 0:** This audit did not re-run DB-backed suites or production checks. Features with strong code + historical tests are classified **Implemented but not fully verified**, not “complete and verified.”

---

## 9. Next Steps (recommended order)

1. **Decide frontend strategy:** restore `admin-web` from Git history (`41c97f5^`) or rebuild against current APIs — required before any operator can use payments/RBAC in a browser.  
2. **Staging migration verification:** print DB name, `alembic current`, then approved upgrade to `20261020_0016`.  
3. **Isolated full backend regression** on `eschool_saas_test` after confirming `current_database()`.  
4. **School Admin payables path:** bill list API (if missing) + Checkout initiate/verify UI using only public `key_id`.  
5. **Ops product rules:** external expire-due cron + final subscription-access decision (implement or document allow-all).

---

## Limitations of this report

- No production or staging database was opened.  
- No pytest suite was executed in this session.  
- Flutter and student-web sibling repos were not fully audited.  
- Content of untracked SQL/backup archives was not treated as product evidence.  
- Older audits (`FINAL_PHASE_1_TO_9_AUDIT.md`, `PHASE10_REPORT.md`) are partially outdated relative to `41c97f5`.

---

## Confirmation

- This report created **only** `PROJECT_PROGRESS_REPORT.md`.  
- No migrations applied.  
- No live Razorpay calls.  
- Nothing staged, committed, pushed, or deployed as part of this audit.
