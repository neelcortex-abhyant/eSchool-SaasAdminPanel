# Security — Phase 2 operational design

## CORS

Migration plan target (stricter than archive Laravel `cors.php`, which only lists `sanctum/csrf-cookie` and `allowed_origins: *`):

| Setting | FastAPI policy |
| --- | --- |
| Allowed origins | Exact admin Next origin + student-web production origin(s); no `*` when `credentials=true` |
| Credentials | **Only** for admin cookie session routes (`/api/admin/*` and auth cookie endpoints) |
| Headers | `Authorization`, `Content-Type`, `Accept`, `school-code`, `X-Tracking-Token`, `X-Requested-With` |
| Tracking exception | `GET /api/transportation/live-tracking/session` uses `X-Tracking-Token` without bearer — CORS must allow that header |
| Mobile apps | Native apps are not browser CORS clients; do not break them with redirect quirks |

Document any temporary widening for staging and close before production canary.

---

## CSRF and admin cookies

| Surface | Auth | CSRF |
| --- | --- | --- |
| Flutter / student-web `/api/*` | Sanctum bearer | No CSRF (stateless) |
| Provider webhooks & payment return URLs | Signature / public | No CSRF (Laravel already excepts) |
| New admin Next.js → `/api/admin` | Server-side session cookies (`HttpOnly`, `Secure`, `SameSite`) | **Double-submit or synchronizer token required** |
| Legacy Blade (until retired) | Laravel session | Existing `VerifyCsrfToken` |

Rules:

- Admin cookies must not replace Flutter bearer tokens.
- Cookie `Domain` / `Path` scoped so student-web cannot receive admin session.
- 2FA, email verified, password reset remain enforced in FastAPI for admin login parity.
- Next.js middleware is navigation-only; **authorization is always server-side**.

---

## Rate limits

| Route class | Guidance |
| --- | --- |
| Login / forgot-password | Tight per IP + per identifier (match or exceed Laravel throttle) |
| Tracking session | Preserve Laravel HTTP `429` behavior on `X-Tracking-Token` routes |
| Webhooks | High ceiling but per-IP abuse shield; never drop valid signed bursts without monitoring |
| Authenticated API | Per-user / per-school fair limits; avoid breaking bulk school admin imports — raise with ownership approval |
| Provisioning / restore | Operator-only; strict concurrency 1 per school |

Use Redis (`fastapi:ratelimit:`) during canary. Record exact Laravel throttle values from route middleware during Phase 3 and copy numbers into this doc’s appendix.

---

## Open / helper route classification

Classify every unauthenticated or lightly protected route before canary. Initial inventory:

| Class | Examples | Policy |
| --- | --- | --- |
| **A — Provider callback** | `/api/webhook/*`, `/webhook/*`, `/subscription/webhook/*`, `/api/whatsapp/webhook/{schoolCode}` | Public; signature/verify only; no CSRF; raw body |
| **B — Payment browser return** | `/payment/status`, `/payment/cancel`, success/cancel groups | Public; no secrets in query beyond what Laravel uses; frozen redirects |
| **C — Cron helper** | `GET /subscription/cron-job` | Treat as **sensitive open helper**: require shared secret header/query if Laravel already does; if none today, add network allowlist or secret **before** FastAPI ownership (security improvement allowed if behavior for callers is preserved via documented secret distribution) |
| **D — Public config** | `GET /api/firebase-config`, languages/settings endpoints that are auth:none | Return only intended public fields; no payment secrets |
| **E — Auth entry** | `POST /api/student/login`, `parent/login`, `teacher/login`, forgot-password | Rate limited; multipart parity |
| **F — Tracking** | Live tracking session with `X-Tracking-Token` | Real HTTP 401/410/429; signed token + Redis revocation |
| **G — Ambiguous / odd** | `GET /api/get-image` (hardcoded host concern), dead/orphan fee helpers | Resolve in Phase 1; do not canary until classified |
| **H — Contact / CMS** | `contact` (CSRF-excepted in Laravel) | Port or retain with spam controls |

Each class gets an owner, rate-limit profile, and logging redaction rule. **Open helper** means reachable without Sanctum — not “safe.”

---

## Additional controls

- Trusted proxies: configure so client IP/rate limits and HTTPS redirects are correct behind the canary reverse proxy.
- Tenant isolation: school A token + school B `school-code` denied (body code parity).
- Secrets: gateway keys, `APP_KEY`, Reverb secret, SMTP, FCM — never in client bundles or logs.
- Demo/maintenance middleware responses preserved.
- Disable prototype DDL helpers in any deployed image.

---

## Acceptance pointers

CORS preflight for student-web and tracking header; CSRF failure on admin POST without token; webhook POST without CSRF succeeds with valid signature; login brute-force returns throttle; open-helper inventory signed by security reviewer.
