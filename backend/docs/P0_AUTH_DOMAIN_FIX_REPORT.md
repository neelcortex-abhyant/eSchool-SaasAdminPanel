# P0 Report: School Admin login, session persistence, school domain provisioning

Branch: `fix/p0-school-admin-auth-domain` · Date: 2026-11-12 · Plan: [P0_AUTH_DOMAIN_FIX_PLAN.md](P0_AUTH_DOMAIN_FIX_PLAN.md) · Frontend hand-off: [P0_FRONTEND_HANDOFF.md](P0_FRONTEND_HANDOFF.md)

## 1. Findings (Step 1)

Measured against the deployed backend `https://eschool-backend-8322.onrender.com` on 2026-11-12.

| # | Finding | Status | Evidence |
|---|---|---|---|
| H1 | Cold start longer than the Netlify proxy can wait, so the form spins on "Signing in…" and no session cookie is set (new tab → login) | **Confirmed** | First `/health` took **82.9 s**; the next one 0.35 s. `backendProxy.ts` has no fetch timeout. |
| H6 | Render and Neon run in different regions, so every DB round trip crosses the Pacific | **Confirmed** (new) | Render origin `gcp-us-west1`; Neon host `…ap-southeast-1.aws.neon.tech`. A warm invalid login takes **2.6–2.8 s** (8.6 s just after the cold start). A one-query availability call takes 1.1–1.5 s. |
| H2 | Login gate ≠ route gate: login allowed `status=1, installed=0`; `/school-admin/*` then returned 403 | **Confirmed in code** | `auth_service.assert_school_admin_login_allowed` vs `deps.require_school_admin`. `create_school` accepts `status`/`installed` separately. The DB test `test_school_registration` already expected "waiting for approval", but login was saying "awaiting approval". |
| H3 | Login IP rate limit keyed on the proxy address, so 50 failures from anyone lock out everyone for 15 min | **Confirmed in code** | `rate_limit.client_ip()` used `request.client.host`. Behind Render/Netlify that's a shared proxy IP. |
| H4 | DB commit on every authenticated request (`last_used_at`) | **Confirmed in code** | `resolve_user_from_token`. Each commit is one extra cross-region round trip. |
| H5 | No DB readiness probe and no login timing logs | **Confirmed** | `/health` doesn't touch the DB. No login log line. |
| C1 | Production runs with development defaults | **Confirmed** (new) | `/health` reports `"env":"local"`, so `APP_ENV` isn't set on Render. `/health` also shows the DB host publicly, and `APP_DEBUG` defaults to true (`/docs` exposed). |
| D1 | Base domain can fall back to the vendor demo host | **Confirmed in code** | With `SCHOOL_BASE_DOMAIN` unset, the base is the `APP_URL` host, default `eschool-saas.wrteam.me`. |
| D2 | Availability returns only the slug | **Confirmed live** | `{"slug":"qa-sunrise-1105","available":true,…}`, no host. The frontend builds `slug.localhost` itself. |
| D3 | Availability and create disagreed about deleted schools | **Found** | Availability ignored deleted schools; create counted them, giving "available" followed by a 409. |
| D4 | No wildcard DNS for school subdomains | **Infra blocker** | `schoolsarthi.com` resolves (Cloudflare). `qa-sunrise-1105.schoolsarthi.com` and a random probe host don't resolve. |

Not reproduced: password verification, token generation and logout revocation behaved correctly in code review and in the tests below. The live valid-login run waits on the QA credentials (§5).

## 2. Fixes (Steps 2–4)

| Area | Change | Files |
|---|---|---|
| One access rule (H2) | New `auth_service.school_admin_access_error()` is used by **both** login and `require_school_admin`. Login now returns a clear 403 instead of a 200 that leads into 403s. Messages: pending / suspended / setup incomplete / subscription / inactive / no school. | `services/v1/auth_service.py`, `api/v1/deps.py` |
| Rate limit (H3) | `TRUSTED_PROXY_HOPS` makes `client_ip()` take the Nth-from-right `X-Forwarded-For` entry. It can't be spoofed through the left-most value. | `core/rate_limit.py`, `core/config.py` |
| Cold start and hangs (H1, H5) | New `GET /health/ready` (`SELECT 1`, returns `db_ms`, 503 on failure) for the Render health check and keep-warm pings. DB `connect_timeout=10s` and `pool_recycle=300`. One `auth.login outcome=… role=… ms=…` log line per attempt (no email or password). | `main.py`, `core/database.py`, `api/v1/auth.py` |
| Request cost (H4) | `last_used_at` is written at most once every 5 min per session. | `services/v1/auth_service.py` |
| Hostname (D1, D2) | Availability returns `hostname` and `base_domain`. Registration, `by-host` and `by-code` return `hostname`. Production refuses an empty, `localhost`, `wrteam.me`, `onrender.com` or `netlify.app` base. | `core/config.py`, `services/v1/school_service.py`, `services/v1/public_school_lookup.py`, `schemas/v1/school_registration.py`, `schemas/v1/public_schools.py`, `api/v1/school_registration.py` |
| Uniqueness (D3) | Availability uses the same rule as create: case-insensitive, and deleted schools keep their host. | `services/v1/school_service.py` |
| Docs | Render env vars, region, health check; domain contract update | `docs/RENDER.md`, `docs/SCHOOL_DOMAINS_API_CONTRACT.md` |

Tenant isolation is unchanged. `school_id` still comes only from the session user, and `assert_school_scope` and branch resolution are untouched. There are no schema migrations, and every response change is additive.

## 3. Tests (Step 5)

**New DB-free regression tests:** 47 passed.
- `tests_offline/test_p0_auth_session.py`:
  - login and route gate agree for every school state
  - subscription block applies to both
  - invalid password and unknown email give the same 401
  - a pending school gets 403 and no session is created
  - token reuse across refresh and new tab
  - `last_used_at` throttle
  - revoked/expired/deactivated tokens are refused
  - logout revokes the session
  - cross-school access gets 403
- `tests_offline/test_p0_rate_limit_ip.py`: hop parsing, spoof resistance, users behind one proxy no longer share a bucket.
- `tests_offline/test_p0_school_domain.py`:
  - full hostname is returned
  - FQDN is stored
  - production base guard (6 bad bases)
  - local dev may still use localhost
  - case-insensitive 409
  - availability matches create for deleted schools
  - public payload includes `hostname`

**Full offline suite:** 170 passed (123 before this change, plus 47 new).

**DB suite (isolated `eschool_saas_test`, never the live DB):** **278 passed, 12 failed, 3 errors** across 16 auth, school-admin, registration, domain, subscription and branch files (run time 4 h 48 min: every test DDL crosses the Pacific, see H6). **None of the failures come from this branch:**
- 11 × `tests/v1/test_role_login.py` (pre-existing). The fixtures use `@role.test` addresses, and the installed `email-validator` rejects the reserved `.test` TLD with a 422 before login runs. The login schema isn't touched here. Fix: switch the fixtures to e.g. `@role-test.com`.
- 1 × `test_phase3_school_admin.py::test_school_admin_blocked_when_school_suspended_or_deactivated` (pre-existing). It expects "School access is suspended" for a *deactivated* school (`status=0, installed=0`). Since 42a0399 (2026-10-11) the route gate has answered "waiting for approval" for that state, and `tests/test_admin_context_unit.py` asserts the same. The new shared rule keeps that behaviour, so the stale assertion should be updated. A deactivated school can't be told apart from a pending registration without a new column.
- 3 errors: Neon closed the connection during `CREATE INDEX` in test setup (infra; transient).

Every P0-relevant DB test passed, including `test_school_registration` (pending school refused with "waiting for approval"), `test_auth_limits`, `test_auth_profile`, `test_super_admin_auth`, `test_subscription_expiry`, `test_school_admin_management` and the branch IDOR tests.

## 4. Deployment steps (needs your go-ahead)

1. Merge or deploy the branch to Render.
2. Set these Render env vars:
   - `SCHOOL_BASE_DOMAIN=schoolsarthi.com`
   - `APP_ENV=production`
   - `APP_DEBUG=false`
   - `TRUSTED_PROXY_HOPS=1` (change to `2` after Vishal's proxy change)
3. Set the Render health check path to `/health/ready`. Add an uptime monitor that pings `/health/ready` every 10 min, or move off the free instance type.
4. **Move Render to Singapore** (same region as Neon). This alone should cut login from about 2.7 s to well under 1 s.
5. DNS: add `*.schoolsarthi.com` (CNAME to the Netlify site) and add the wildcard as a Netlify domain alias. Set `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN=schoolsarthi.com` on Netlify.
6. Run `bash backend/scripts/p0_live_auth_check.sh` with `P0_API`, `P0_EMAIL` and `P0_PASSWORD` set, and paste the output into §5.

## 5. Live verification

**Before deploy** (2026-11-12, no credentials):
```
      /health 0.332963s
PASS  health (200)
      /health/ready 0.267478s {"detail":"Not Found"}
FAIL  health-ready expected=200 got=404
      invalid login 4.052468s {"detail":"Invalid email or password"}
PASS  invalid-login-401 (401)
SKIP  valid-login checks (P0_EMAIL / P0_PASSWORD not set)
      availability 2.260708s {"slug":"qa-sunrise-1105","available":true,"problem":null,"suggestions":[]}
PASS  availability-200 (200)
FAIL  hostname-is-production expected=qa-sunrise-1105.<base> got=<missing>
== 3 passed, 2 failed
```
The two failures are what this branch adds (`/health/ready`, `hostname`).

**After deploy:** pending. Needs the deploy and the QA School Admin credentials.

## 6. Integration support (admissions, fees, branches)

After login works, the live check script's token is used to smoke-test:
- Admissions: students list and create via `/api/v1/school-admin/academics`
- Fees: `/api/v1/school-admin` fee routes
- Branches: list, and switch with `X-Branch-Id`

Results go here after the deploy. Any backend defect found gets fixed on this branch with a test.

## 7. Open items for Vishal

See [P0_FRONTEND_HANDOFF.md](P0_FRONTEND_HANDOFF.md):
1. Proxy fetch timeout, and forward `x-forwarded-for`
2. Give the `v1_session` cookie a `Max-Age` from `expires_at`
3. Show the 403 `detail` text
4. Preview shows the API's `hostname`
