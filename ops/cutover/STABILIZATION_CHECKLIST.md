# Phase 10 — Stabilization checklist

Run after cutover flip. Minimum watch window: **24 hours** (extend for fee-due dates / exam windows).

## Traffic and errors

- [ ] HTTP 5xx ≤ Laravel baseline
- [ ] Business-error body codes at parity (not masked as 200 with wrong shape)
- [ ] Login p95 within agreed budget
- [ ] Authenticated read/write p95 within budget
- [ ] Student-web requests complete under 10s timeout

## Auth and tenancy

- [ ] Existing Sanctum tokens still work (no mass logout)
- [ ] Logout variants behave per role
- [ ] Cross-tenant isolation spot checks (two schools)
- [ ] Super-admin vs school-admin session boundaries

## Origins and media

- [ ] No FastAPI temporary host in JSON/HTML/redirects
- [ ] `/storage/...` absolute URLs match frozen media origin
- [ ] Emails / FCM / payment sessions show public host only

## Payments and webhooks

- [ ] Gateway dashboards still hit frozen paths
- [ ] Razorpay/Stripe/Paystack/Flutterwave webhooks succeed
- [ ] Subscription webhooks succeed
- [ ] WhatsApp webhook verify + delivery for a sample school

## Async and realtime

- [ ] Single consumer per queue
- [ ] Scheduler ownership matches matrix (timezone-aware)
- [ ] Reverb/WebSocket connect using frozen `reverbUrl`

## Admin

- [ ] Next.js admin login via `/api/admin`
- [ ] Critical admin writes (students, fees, schools) verified if in scope

## Exit criteria

All boxes checked + engineering/ops sign-off → raise DNS TTL and close cutover incident.
