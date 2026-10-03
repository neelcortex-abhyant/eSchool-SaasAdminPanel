# Payments and webhooks — Phase 2 operational design

## Scope

Four fee/subscription gateways + WhatsApp Meta webhooks:

- **Stripe, Razorpay, Paystack, Flutterwave** — school fee payments and SaaS subscriptions
- **WhatsApp Cloud API** — per-school verify/receive

Preserve gateway dashboard URLs; change only reverse-proxy upstream when ownership transfers.

---

## Path inventory (frozen)

### API (`routes/api.php`) — must keep

| Method | Path | Controller | Domain |
| --- | --- | --- | --- |
| POST | `/api/webhook/razorpay` | `WebhookController@razorpay` | webhook (fees) |
| POST | `/api/webhook/stripe` | `WebhookController@stripe` | webhook (fees) |
| POST | `/api/webhook/paystack` | `WebhookController@paystack` | webhook (fees) |
| POST | `/api/webhook/flutterwave` | `WebhookController@flutterwave` | webhook (fees) |
| POST | `/api/subscription/webhook/stripe` | `SubscriptionWebhookController@stripe` | subscription |
| POST | `/api/subscription/webhook/razorpay` | `SubscriptionWebhookController@razorpay` | subscription |
| GET+POST | `/api/whatsapp/webhook/{schoolCode}` | `WhatsAppWebhookController` verify/receive | whatsapp |

(Confirm Paystack/Flutterwave subscription API duplicates if present in live `api.php`; web list below is authoritative for public SaaS.)

### Web (`routes/web.php`) — also public

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/webhook/razorpay` | Fee webhook |
| POST | `/webhook/stripe` | Fee webhook |
| POST | `/webhook/paystack` | Fee webhook |
| POST | `/webhook/flutterwave` | Fee webhook |
| POST | `/subscription/webhook/stripe` | SaaS subscription |
| POST | `/subscription/webhook/razorpay` | SaaS subscription |
| POST | `/subscription/webhook/paystack` | SaaS subscription |
| POST | `/subscription/webhook/flutterwave` | SaaS subscription |
| GET | `/payment/status` | App return URL (defined twice in web.php — preserve both registrations’ behavior) |
| GET | `/payment/cancel` | Cancel URL |
| GET | `/subscription/cron-job` | Public subscription cron trigger |
| GET | school-admin payment success/cancel routes | Exact prefixes per Laravel groups — inventory into fixtures; do not rename |

CSRF: Laravel `VerifyCsrfToken` already excepts `webhook/*`, `subscription/webhook/*`, `payment/status`, `payment/cancel`, `api/*`. FastAPI must not impose CSRF on these provider callbacks.

---

## Raw body and signature verification

**Critical:** Signature checks must use the **raw request body bytes**, not a re-serialized JSON object.

| Gateway | Signature material (Laravel parity) | FastAPI requirement |
| --- | --- | --- |
| Stripe | `Stripe-Signature` header + endpoint webhook secret (per school metadata / payment config) | `stripe.Webhook.construct_event(payload, sig_header, secret)` on raw body |
| Razorpay | `X-Razorpay-Signature` + webhook secret; `verifyWebhookSignature(raw, signature, secret)` | Same HMAC over raw body |
| Paystack | `x-paystack-signature` = `HMAC SHA512(raw_body, secret_key)` | Compare to header with constant-time equality |
| Flutterwave | Verif-hash / HMAC over raw body per current controller logic | Port exact header name and algorithm from `WebhookController@flutterwave` |
| WhatsApp | Meta verify challenge (GET) + `X-Hub-Signature-256` (POST) per Meta docs | Preserve `{schoolCode}` path tenancy |

Disable JSON middleware that parses then re-dumps body before verification. In Starlette/FastAPI: read `await request.body()` once; pass same bytes to verifier and then `json.loads`.

School resolution: fee webhooks often carry `metadata.school_id` (Stripe) or notes (Razorpay); load `PaymentConfiguration` for that school **before** trusting business fields. WhatsApp uses path `schoolCode`.

---

## Idempotency and transaction states

Subscription controller comments already describe an **idempotent** pipeline — FastAPI must match:

1. Verify signature → reject invalid with provider-appropriate HTTP status (do not 500-loop).
2. Resolve `payment_transactions` / subscription transaction row (Razorpay may pre-create and reference id in notes).
3. **Row lock** (`SELECT … FOR UPDATE`) on the transaction.
4. If already terminal success/failed matching event → return 200, no double credit.
5. Apply state transition exactly once; write receipts / fees paid rows in same DB transaction.
6. Side effects (FCM, email, WhatsApp) after commit, via idempotent jobs.

Test matrix per gateway: invalid signature, duplicate delivery, delayed delivery, out-of-order (fail then success), success then duplicate success, rollback of canary mid-flight.

Stripe subscription note from Laravel: plan may activate on **success redirect** with webhook as confirm — preserve that split behavior; do not double-activate.

Gateway response shapes for mobile (Stripe/Razorpay vs Paystack/Flutterwave) are **not interchangeable** — golden fixtures per gateway.

---

## Migrate webhooks before writes

Hard rule for fees and subscriptions:

```
webhook ownership → FastAPI
        ↓ proven
payment write APIs + admin fee mutations → FastAPI
```

Never canary `parent`/`staff` fee initiation or subscription purchase writes to FastAPI while webhooks still hit Laravel (or the reverse). Dual ownership causes double credit or stuck pending.

WhatsApp: migrate verify+receive before FastAPI becomes the sole sender of WhatsApp jobs for that school cohort.

---

## Redirects and deep links

Preserve status codes, `Location` headers, query parameters, and encoding for:

- `/payment/status`, `/payment/cancel`
- School-admin and subscription success/cancel URLs
- Mobile deep links embedded in sessions

Frozen-origin assertion: no FastAPI ephemeral host in payment session URLs.

---

## Ownership transfer checklist

1. Approve matrix rows: `webhook`, `subscription`, `whatsapp`, related `parent`/`staff` fee domains.
2. Point proxy allowlist for **webhook paths only** to FastAPI; run replay tests in staging with provider test clocks.
3. 24h dual-run observation (webhooks on FastAPI, writes still Laravel) **only if** writes remain Laravel and FastAPI webhooks are the single consumer — preferred pattern for cutover.
4. Then move payment write routes.
5. Rollback: proxy webhooks back to Laravel; drain in-flight; verify no duplicate credits via transaction audit.

---

## Acceptance pointers

See [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md) § Payments. Phase 6 plan gate: webhooks pass before related payment writes.
