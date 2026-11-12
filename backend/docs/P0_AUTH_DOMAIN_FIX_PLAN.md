# P0 Bug Fix Plan: School Admin Login, Session Persistence, School Domain Provisioning

Scope: **backend only** (`backend/`). Frontend items (admin-web) are written up as hand-off notes for Vishal, not edited.
After approval, this plan is also saved in the repo as `backend/docs/P0_AUTH_DOMAIN_FIX_PLAN.md`, and Steps 1–5 run without further stops.

---

## Context

QA retest of the deployed portal (Netlify → Render → Neon):
- School Admin login stays on "Signing in…" and never completes.
- Opening the dashboard in a new tab sends the user back to login.
- Admission, Fees and Branch testing is blocked behind login.
- The domain preview shows `qa-sunrise-1105` with no verified full hostname.

### How login works today (traced in code)

1. `admin-web/app/login/LoginForm.tsx` → `POST /api/v1/auth/login`, sent to the Netlify route `app/api/v1/[...path]/route.ts`.
2. `admin-web/lib/backendProxy.ts` → `fetch()` to Render, **with no timeout**.
3. `backend/app/api/v1/auth.py::login` → `login_with_limits` → `auth_service.login` (bcrypt check → `assert_school_admin_login_allowed` → `create_session`). The response is `{access_token, expires_at, user}`.
4. The frontend stores the token in `localStorage` plus a presence cookie `v1_session=1`, then goes to `/school`.
5. `/school` calls `GET /school-admin/me` and `GET /school-admin/school`, both through `require_school_admin` in `backend/app/api/v1/deps.py`.
6. `admin-web/middleware.ts` redirects to `/login` whenever the `v1_session` cookie is missing.

### Root-cause candidates found in the code (Step 1 confirms which apply)

| # | Finding | Location | Effect |
|---|---|---|---|
| H1 | **Cold-start hang.** Render free instance sleeps and Neon compute suspends. The Netlify proxy `fetch` has no timeout, so login can wait past Netlify's function limit (10–26 s). | Render/Neon, `lib/backendProxy.ts` | "Signing in…" never resolves. No cookie is set, so a new tab goes to login. |
| H2 | **Login and route gates disagree.** Login allows any school with `status==1`. `require_school_admin` also needs `installed==1` and an active subscription. | `auth_service.assert_school_admin_login_allowed` vs `deps.require_school_admin` | Login returns 200, then every `/school-admin/*` call returns 403, which blocks the panel. |
| H3 | **IP rate limit shared by everyone.** `client_ip()` uses `request.client.host`, which is the proxy's IP for every user. 50 failed logins in 15 min from anyone → **all** users get 429. | `app/core/rate_limit.py` | QA retests with wrong passwords lock out the whole portal for 15 min. |
| H4 | **DB write on every request.** `resolve_user_from_token` commits `last_used_at` on every authenticated call. | `auth_service.py` | Slower `/me` and dashboard loads, contention when calls run in parallel. |
| H5 | **No readiness check or timing logs.** `/health` never touches the DB. Login logs no timing. | `app/main.py`, `auth.py` | Cold DB and slow logins can't be seen. |
| D1 | **Wrong default base domain.** If `SCHOOL_BASE_DOMAIN` is unset, the base comes from `APP_URL`, whose default is `eschool-saas.wrteam.me` (vendor domain). | `app/core/config.py` | Wrong hostnames are stored. |
| D2 | **Availability API returns only the slug**, never the full hostname. | `school_service.check_subdomain_availability`, `SubdomainAvailabilityResponse` | The frontend has to guess the base, which is where `.localhost` comes from. |

Production base domain (confirmed): **`schoolsarthi.com`**. Example: `qa-sunrise-1105.schoolsarthi.com`.

---

## Existing API folder (where changes go)

```
backend/app/
├── api/
│   ├── v1/
│   │   ├── auth.py                    ← login / logout / me  (Step 2)
│   │   ├── deps.py                    ← require_school_admin (Step 2)
│   │   ├── school_admin.py            ← /school-admin/me, /school (verify)
│   │   ├── school_registration.py     ← /subdomain-availability (Step 4)
│   │   ├── school_admin_branches.py   ← branch retest (Step 5)
│   │   ├── school_admin_erp.py        ← fees retest (Step 5)
│   │   ├── school_admin_academics.py  ← admissions/students retest (Step 5)
│   │   └── super_admin/router.py      ← super-admin login (shares limits)
│   └── (legacy) admin.py, mobile.py, ...   ← untouched
├── core/
│   ├── config.py                      ← base domain, proxy trust, DB timeout (Steps 2, 4)
│   ├── rate_limit.py                  ← client_ip fix (Step 2)
│   └── database.py                    ← connect_timeout (Step 2)
├── services/v1/
│   ├── auth_service.py                ← shared eligibility, last_used throttle (Step 2)
│   └── school_service.py              ← hostname in responses, base guard (Step 4)
├── schemas/v1/school_registration.py  ← add `hostname` (Step 4)
└── main.py                            ← /health/ready (Step 2)
tests/ , tests_offline/                ← new regression tests (Step 5)
```

---

## Step 1: Reproduce and diagnose (3 h)

**Subtasks**
1. **Time the deployed API, cold and warm** (`curl -w` timings). Use the QA School Admin credentials you'll share. Only these calls are made:
   - `GET /health`
   - `POST /api/v1/auth/login`, valid and invalid
   - `GET /api/v1/auth/me`
   - `GET /api/v1/school-admin/me` and `/school-admin/school`
   - `POST /api/v1/auth/logout`, then `/auth/me` again (expect 401)
2. **Run the same calls through the Netlify origin** (`https://<site>/api/v1/...`) to measure the proxy hop and see whether it times out.
3. **Read the Render logs** around the QA timestamps for exceptions, 5xx, 429 and slow requests.
4. **Check the QA school row** (read-only SQL): `status`, `installed`, `deleted_at`, subscription expiry, the admin user's `role`/`status`/`school_id`, and stored `domain`/`domain_type`. This confirms or rules out H2.
5. **Check Render env vars:** `SCHOOL_BASE_DOMAIN`, `APP_URL`, `FRONTEND_ORIGIN`, `APP_ENV`, `V1_SESSION_TTL_MINUTES`.
6. **Reproduce locally** against the isolated test Postgres (`TEST_DATABASE_URL`, never the live DB).

**Output:** a findings table (H1–H5, D1–D2: confirmed / not confirmed, with evidence) at the top of `backend/docs/P0_AUTH_DOMAIN_FIX_REPORT.md`.
**Depends on:** QA credentials, Render log access.

---

## Step 2: Fix the authentication backend (6 h)

**2a. One eligibility rule for login and routes (H2)**
- In `services/v1/auth_service.py`, add `school_admin_access_error(db, user) -> AuthError | None`. It covers active user, `school_id`, school exists, not deleted, `status==1`, `installed==1`, and subscription not blocked. It reuses `subscription_access.subscription_expiry_blocks_access` and the existing messages.
- `assert_school_admin_login_allowed` and `deps.require_school_admin` both call it. Login then returns a clear 403 ("awaiting approval" / "suspended" / "subscription") instead of a 200 that leads into 403s.
- Tenant isolation is unchanged: `school_id` still comes only from the session user.

**2b. Rate limit keyed by the real client IP (H3)**
- In `core/config.py`, add `trusted_proxy_hops: int = 0`.
- `rate_limit.client_ip()` takes the address that number of hops from the right end of `X-Forwarded-For` when `trusted_proxy_hops > 0`, else `request.client.host`. A client can't spoof it, because only proxy-appended entries are used.
- Set `TRUSTED_PROXY_HOPS` on Render. Handoff to Vishal: forward `x-forwarded-for` in `backendProxy.ts`.
- The per-email limit (10/15 min) stays as it is.

**2c. Cold start, timeouts, visibility (H1, H5)**
- `core/database.py`: add `connect_args={"connect_timeout": 10}`, so a suspended Neon fails fast with a clear 503 instead of hanging.
- `main.py`: add `GET /health/ready`, which runs `SELECT 1` and returns 200/503. It can be used for a Render health check and an external keep-warm ping (e.g. UptimeRobot every 10 min). That stops the free instance sleeping during QA.
- `auth.py`: log `auth.login outcome=<ok|invalid|forbidden|rate_limited> role=… ms=…`. Never log the email or the password.

**2d. Faster session checks (H4)**
- `resolve_user_from_token` writes `last_used_at` only when the stored value is more than 5 min old.

**2e. CORS check**
- Confirm `FRONTEND_ORIGIN` includes the production admin origin, plus any custom domain beyond `*.netlify.app`. Change only the env var; no code change unless a domain is missing from the regex.

**Files:** `services/v1/auth_service.py`, `api/v1/deps.py`, `api/v1/auth.py`, `core/rate_limit.py`, `core/config.py`, `core/database.py`, `main.py`.

---

## Step 3: Verify session and token handling, and hand off to Vishal (3 h)

**Backend checks** (as tests in Step 5, and live after deploy):
- Valid login → 200 with `access_token`, `expires_at`, `user.role="school_admin"`, `user.school_id`.
- Invalid password → 401 "Invalid email or password". Unknown email gives the same answer.
- Pending school → 403 with the approval message. Expired subscription → 403 with the subscription message.
- `/auth/me` and `/school-admin/me` with the token → 200. Repeating them (refresh, new tab) → still 200.
- Logout → 204, then the same token → 401. Other sessions stay valid.
- Expired session → 401. The token never works for another school's resources (`assert_school_scope`).

**Hand-off note for Vishal** (`backend/docs/P0_FRONTEND_HANDOFF.md`, no frontend edits):
1. `lib/backendProxy.ts`: add an `AbortController` timeout (~25 s) that returns 504 JSON, so the form shows an error instead of spinning. Forward `x-forwarded-for`.
2. `lib/api.ts::setSession`: give the `v1_session` presence cookie `Max-Age` from `expires_at` and `Secure` on https, so it lasts across browser restarts the same way the token does.
3. Login form: treat 403 as a readable message, not "Invalid email or password".
4. Domain preview: show `hostname` from the API, never build `slug + ".localhost"`.

---

## Step 4: School domain provisioning (4 h)

1. **Config:** set `SCHOOL_BASE_DOMAIN=schoolsarthi.com` on Render.
   - Add a production guard in `config.py` / startup: in `APP_ENV=production`, log an error and refuse domain provisioning (500 "not configured") if the resolved base is empty, `localhost`/`*.localhost`, `wrteam.me`, `onrender.com` or `netlify.app`.
2. **API returns the full hostname:**
   - `SubdomainAvailabilityResponse` gains `hostname` (e.g. `qa-sunrise-1105.schoolsarthi.com`) and `base_domain`. This is additive; `slug` stays as it is.
   - Confirm that the registration response, Super Admin school detail/list and `/school-admin/school` return the stored full `domain`. If any of them return only the prefix, add the full hostname there too (`school_service`).
3. **Storage and uniqueness:**
   - Confirm `resolve_school_domain` stores `prefix.schoolsarthi.com`, and that `_ensure_domain_available` / `_domain_taken` return 409 or "taken", ignoring case.
   - Read-only SQL lists existing schools whose `domain` ends in `.localhost`, `wrteam.me` or has no dot. That list goes in the report; nothing is rewritten without your approval.
4. **Mapping to the right school:** `public_school_lookup` resolves `qa-sunrise-1105.schoolsarthi.com` to the QA school.
5. **Deployed check:** `nslookup qa-sunrise-1105.schoolsarthi.com`, checking for a wildcard `*.schoolsarthi.com` DNS record pointing at Netlify. If DNS isn't set up yet, I record that as an infra blocker. It isn't a code defect.

**Files:** `core/config.py`, `services/v1/school_service.py`, `schemas/v1/school_registration.py`, `api/v1/school_registration.py`, `docs/SCHOOL_API_CONTRACT.md` (contract update for Vishal).

---

## Step 5: Tests, deploy, integration support (6 h)

**New regression tests**
- `tests_offline/test_p0_auth_session.py`:
  - login valid/invalid/unknown email
  - 403 for a pending school and for an expired subscription
  - login and dependency agree (the H2 case)
  - me → refresh → logout → 401
  - expiry
  - cross-school 403
  - the `last_used_at` throttle
- `tests_offline/test_p0_rate_limit_ip.py`: with trusted hops, users behind the same proxy don't share a bucket; a spoofed left-most `X-Forwarded-For` is ignored.
- `tests_offline/test_p0_school_domain.py`:
  - `hostname` is in the availability response
  - stored value is `prefix.schoolsarthi.com`
  - duplicates are blocked, ignoring case
  - the production guard rejects a `localhost`/`wrteam.me` base
- Run the existing `test_login_token_response.py`, `tests/test_role_auth.py` and the full `pytest -q` (isolated DB only).

**Deploy**
- Commit on a branch, then deploy to Render after you approve.
- Set `SCHOOL_BASE_DOMAIN`, `TRUSTED_PROXY_HOPS` and the health check path.
- Re-run the Step 1 curl script and record before/after timings.

**Integration support:** after login works, smoke-test with the QA admin token:
- **Admissions:** students create and list (`/school-admin/academics`)
- **Fees:** `/school-admin` fees routes
- **Branches:** list, create and switch with `X-Branch-Id`

Any backend defects found here get fixed and tested in the same pass, then listed in the report.

**Deliverable:** `backend/docs/P0_AUTH_DOMAIN_FIX_REPORT.md`, covering root causes, fixes, test output, live evidence (status codes and timings), the API contract changes and the open frontend items for Vishal.

---

## Estimated hours

| Step | Work | Hours |
|---|---|---|
| 1 | Reproduce and diagnose | 3 |
| 2 | Auth backend fixes | 6 |
| 3 | Session verification and hand-off | 3 |
| 4 | Domain provisioning | 4 |
| 5 | Tests, deploy, integration support | 6 |
| | **Total** | **~22 h** |

## Dependencies and risks

- QA School Admin credentials, Render dashboard/log access, and approval before the production deploy.
- **H1 isn't fully fixed by the backend alone.** The free Render tier still sleeps. A keep-warm ping or a paid instance, plus Vishal's proxy timeout, closes it fully.
- DNS for `*.schoolsarthi.com` is infrastructure. If it's missing, that gets reported, not coded around.
- No schema migrations are expected. All response changes are additive, so the existing frontend keeps working.

## Verification (end to end)

1. `pytest -q` passes on the isolated test DB, including the new P0 tests.
2. Deployed checks:
   - Login → 200 in under 2 s when warm
   - Invalid → 401
   - `/school-admin/me` → 200
   - Logout → token returns 401
   - Availability returns `hostname: "<slug>.schoolsarthi.com"`
3. Vishal confirms in the browser:
   - Login lands on `/school`
   - Refresh and a new tab stay signed in
   - Logout returns to login
   - Admissions, Fees and Branches load
