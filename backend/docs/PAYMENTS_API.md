# Subscription Payments API

Razorpay payments for subscription bills, payment history, and invoices. All paths are under the FastAPI `/api/v1` prefix. This document describes the code as implemented; example values are illustrative.

Related: [SUBSCRIPTION_RENEWAL_API.md](SUBSCRIPTION_RENEWAL_API.md) (plans, subscriptions, renewals, bills).

## Conventions

| Topic | Rule |
| --- | --- |
| Auth | `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`. The webhook takes no bearer token; it is authenticated by its signature. |
| Response shape | Routes return the resource JSON directly (no `{ "success": ..., "data": ... }` envelope), the same as the other v1 routes. |
| Errors | `{"detail": "<message>"}` with the HTTP status. Validation errors (422) use FastAPI's list form: `{"detail": [{"loc": [...], "msg": "...", ...}]}`. |
| Money | Integer **paise** in every payment and invoice field (`249900` = ₹2,499.00). Bills store rupees; the server converts with half-up rounding. The minimum charge is 100 paise. |
| Currency | `RAZORPAY_CURRENCY`; only `INR` is accepted for new orders. Webhook and gateway amounts must match the stored order's amount **and** currency. |
| Pagination | `page` (≥ 1, default 1) and `page_size` (1–100, default 20). Lists return `{"items": [...], "total": n, "page": p, "page_size": s}`. |
| Dates | `from_date` / `to_date` are `YYYY-MM-DD`, inclusive, in UTC. `from_date` after `to_date` is 422. |
| Secrets | `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` are never returned, logged, or stored in rows. Signatures and raw webhook bodies are not stored. |

### Roles

| Role | Scope |
| --- | --- |
| Super Admin | Every school. |
| School Admin | Only `school_id` equal to their own school, and only while that school is active and installed. Another school's `school_id` is 403; another school's resource id under their own `school_id` is 404. |
| Other users | 403. |
| No / invalid token | 401 `Not authenticated`. |

## Payment statuses

Stored as integers, returned as names.

| Value | Name | Meaning |
| --- | --- | --- |
| 0 | `created` | Order created at Razorpay; no payment attempt recorded. |
| 1 | `authorized` | A signed checkout or `payment.authorized` webhook was received. **Not paid.** |
| 2 | `captured` | Gateway confirmed capture. The bill is marked paid and an invoice issued (once). |
| 3 | `failed` | The latest attempt failed. The same order can be retried. |
| 4 | `refunded` | Fully refunded (`refund.processed`). |

Allowed transitions:

```
created ──► authorized ──► captured ──► refunded
   │            │  ▲          ▲
   │            ▼  │(new payment id)
   └────────► failed ─────────┘
```

- `captured` and `refunded` are terminal for payment events: a late `payment.failed` or `payment.authorized` does not move them.
- `failed → authorized` happens only for a **new** payment id (a retry on the same order), not for an out-of-order event for the failed payment.
- `failed → captured` is allowed (the gateway is the source of truth).
- A partial refund leaves the payment `captured`.

## One order per bill

A bill has at most one payment transaction that is not `refunded`. This is enforced in the service (the bill row is locked) and by the partial unique index `uq_payment_transactions_bill_open` (migration `20261019_0015`).

`POST /payments/initiate` for a bill:

| Bill's existing transaction | Result |
| --- | --- |
| none | A new Razorpay order is created. |
| same `idempotency_key` | That row is returned; Razorpay is not called again. |
| different key, status `created` or `failed` | That **same** order is returned (Razorpay orders accept a new attempt after a failure). |
| different key, status `authorized` | 409 `A payment for this bill is awaiting capture` |
| different key, status `captured` | 409 `Bill already has a captured payment` |

---

## POST /api/v1/payments/initiate

Create, or return the existing, Razorpay order for a bill. Role: Super Admin or School Admin (own school).

The amount always comes from the stored bill. Any extra field, including `amount`, is rejected with 422.

Request:

```json
{
  "bill_id": 42,
  "school_id": 7,
  "subscription_id": 15,
  "idempotency_key": "b4f1c2e0-6f0e-4b8b-9d1e-2a7c0e5d9f10"
}
```

`idempotency_key`: 1–64 visible ASCII characters. Generate one per payment intent (for example a UUID) and reuse it on retries of the same request.

Response `200`:

```json
{
  "order_id": "order_example123",
  "amount": 249900,
  "currency": "INR",
  "gateway": "razorpay",
  "key_id": "rzp_test_example",
  "status": "created"
}
```

`key_id` is the public key id for Razorpay Checkout. `status` is the order's current payment status (`failed` when an earlier attempt failed and the order is being reused).

| Status | `detail` | When |
| --- | --- | --- |
| 401 | `Not authenticated` | Missing or invalid token |
| 403 | `Forbidden` | Wrong role, or another school's bill |
| 404 | `Bill not found` / `Subscription not found` | Unknown, deleted, or mismatched bill/subscription/school |
| 409 | `Bill already has a captured payment` | Captured order exists and the key differs |
| 409 | `A payment for this bill is awaiting capture` | Authorized order exists |
| 409 | `Idempotency key does not match this payment` | Key already used for another bill or amount |
| 409 | `The bill's open order does not match the bill` | Stored order amount/currency differs from the bill |
| 422 | `Bill is not payable` | Bill is paid or cancelled |
| 422 | `Bill amount is below the minimum charge of 1.00 INR` | Less than 100 paise |
| 422 | `Idempotency key must be 1 to 64 visible characters` | Bad key |
| 422 | `Unsupported currency` | `RAZORPAY_CURRENCY` is not INR |
| 502 | `Payment gateway rejected the order` | Razorpay rejected the request |
| 503 | `Payment configuration is missing` / `... does not match this environment` | Missing keys, or a `rzp_live_` key outside production (or `rzp_test_` in production) |
| 504 / 500 | `... It may already exist.` | Gateway or commit outcome unknown. Retry with the **same** key. |

## POST /api/v1/payments/verify

Report a completed Razorpay Checkout. Role: Super Admin or School Admin (own school's order).

Request (the three fields from the Checkout `handler` callback):

```json
{
  "razorpay_order_id": "order_example123",
  "razorpay_payment_id": "pay_example456",
  "razorpay_signature": "9f2c…"
}
```

Processing:

1. The checkout signature `HMAC_SHA256(order_id + "|" + payment_id, key_secret)` is checked. This proves the payment belongs to the order.
2. The server fetches the payment from Razorpay (`GET /v1/payments/{id}`) and requires the same payment id, order id, amount (paise), and currency as the stored order.
3. The gateway status decides the result:
   - `captured`: the payment becomes `captured`, the bill is marked paid once, and one invoice is issued.
   - `authorized`: the payment becomes `authorized`. The webhook will finish it.
   - `failed`: the payment becomes `failed`.
   - Gateway unreachable: the payment becomes `authorized`; the webhook will finish it.

Checkout success alone never marks a bill paid. Repeating the same verify call is safe: it returns the current state and writes nothing.

Response `200`:

```json
{
  "order_id": "order_example123",
  "payment_id": "pay_example456",
  "amount": 249900,
  "currency": "INR",
  "status": "captured"
}
```

| Status | `detail` | When |
| --- | --- | --- |
| 400 | `Payment signature is invalid` | Signature or ids malformed or wrong |
| 403 | `Forbidden` | Another school's order |
| 404 | `Payment not found` | Unknown `razorpay_order_id` |
| 409 | `Payment does not match the order` | Gateway amount, currency, or order differs (recorded as audit `payment.verify_mismatch`) |
| 409 | `Payment is linked to a different transaction` | The payment id belongs to another order, or the order already has a different active payment |
| 503 | `Payment configuration is missing` | Keys not configured |

## POST /api/v1/payments/webhook/razorpay

Razorpay → server. No bearer token. Point the Razorpay webhook **directly at the backend host** (for example `https://<backend>/api/v1/payments/webhook/razorpay`). The Next.js same-origin proxy does not forward the `X-Razorpay-*` headers.

Headers used: `X-Razorpay-Signature` (HMAC-SHA256 of the exact raw body with `RAZORPAY_WEBHOOK_SECRET`) and `X-Razorpay-Event-Id` (deduplication key). Body limit: 256 KiB.

Events:

| Event | Effect |
| --- | --- |
| `payment.authorized` | `created`/`failed` → `authorized` |
| `payment.captured` | → `captured`; bill marked paid once; one invoice issued |
| `payment.failed` | → `failed` (not after capture) |
| `payment.pending` | Payment id recorded; no status change |
| `refund.processed` | Full refund of a captured payment → `refunded`; partial refund recorded only |
| anything else (e.g. `order.paid`) | Recorded as `ignored` |

Safety rules:

- **Invalid signature** → 400 `Webhook signature is invalid`; nothing is written.
- **Duplicate `X-Razorpay-Event-Id`** → 200; nothing changes.
- **Repeat capture under a new event id** → 200; no second bill update or invoice.
- **Amount or currency mismatch** → 200; the payment and bill are not changed; recorded with outcome `amount_mismatch` and audit `payment.mismatch`.
- **Capture on a cancelled or deleted bill** → payment stored as `captured` (money was taken), bill **not** paid, **no invoice**; audit `payment.captured_unpayable_bill` with `refund_required: true`.
- **Payment id owned by another order**, or a second capture on an already captured order → 409 `Payment is linked to a different transaction`, recorded with outcome `payment_conflict` and audit `payment.conflict`. Razorpay's retry of that event then gets 200.
- **Order not yet stored locally** → 503 `Payment order is not available yet`, so Razorpay retries.
- **Refund** for a payment that is not ours → 200, outcome `unknown_payment`.

Each processed event stores `event_id`, `event_type`, gateway order and payment ids, amount, currency, and `outcome` (`applied`, `ignored`, `stale`, `amount_mismatch`, `payment_conflict`, `bill_not_payable`, `partial_refund`, `unknown_payment`) in `payment_webhook_events`.

Response `200`: `{"received": true}`

## Payment history

Item shape (`PaymentTransactionResponse`):

```json
{
  "id": 3,
  "school_id": 7,
  "bill_id": 42,
  "gateway": "razorpay",
  "order_id": "order_example123",
  "payment_id": "pay_example456",
  "amount": 249900,
  "currency": "INR",
  "status": "captured",
  "invoice_id": 11,
  "created_at": "2026-10-19T09:30:00",
  "updated_at": "2026-10-19T09:31:12"
}
```

`payment_id` is null until a payment attempt is known. `invoice_id` is null until an invoice is issued. Idempotency keys and signatures are never returned. Ordering: newest `created_at` first.

| Method | Path | Role | Query |
| --- | --- | --- | --- |
| GET | `/api/v1/super-admin/payments` | Super Admin | `page`, `page_size`, `school_id`, `status` (0–4), `from_date`, `to_date` |
| GET | `/api/v1/super-admin/payments/{payment_id}` | Super Admin | – |
| GET | `/api/v1/schools/{school_id}/payments` | Super Admin, School Admin (own) | `page`, `page_size`, `status` (0–4), `from_date`, `to_date` |

Errors: 401, 403, 404 `Payment not found` / `School not found`, 422 for bad query values or date range.

## Invoices

An invoice is issued exactly once per captured payment transaction (unique `payment_transaction_id`). Because a bill has only one non-refunded transaction, a bill gets at most one invoice. Invoices are immutable snapshots of the school, plan, and period at issue time; later edits to the school or plan do not change them. A refund does not change or void the invoice. Tax fields are `null` because no tax configuration exists; `null` does not mean zero-rated.

Number format: `SUB-YYYY-NNNNNN`, sequential per calendar year (UTC).

Item shape (`SubscriptionInvoiceResponse`):

```json
{
  "id": 11,
  "invoice_number": "SUB-2026-000011",
  "issued_at": "2026-10-19T09:31:12",
  "payment_transaction_id": 3,
  "bill_id": 42,
  "school_id": 7,
  "subscription_id": 15,
  "package_id": 2,
  "gateway": "razorpay",
  "order_id": "order_example123",
  "payment_id": "pay_example456",
  "currency": "INR",
  "amount": 249900,
  "tax_label": null,
  "tax_rate_percent": null,
  "tax_amount": null,
  "total_amount": 249900,
  "school_name": "Example School",
  "school_address": "12 School Road",
  "school_email": "office@example.com",
  "school_phone": "9000000000",
  "plan_name": "Standard",
  "plan_description": "Monthly subscription",
  "cycle": "monthly",
  "period_start": "2026-10-01",
  "period_end": "2026-11-01"
}
```

| Method | Path | Role | Query |
| --- | --- | --- | --- |
| GET | `/api/v1/super-admin/invoices` | Super Admin | `page`, `page_size`, `school_id`, `bill_id`, `subscription_id`, `from_date`, `to_date` (on `issued_at`) |
| GET | `/api/v1/super-admin/invoices/{invoice_id}` | Super Admin | – |
| GET | `/api/v1/super-admin/invoices/{invoice_id}/pdf` | Super Admin | – |
| GET | `/api/v1/schools/{school_id}/invoices` | Super Admin, School Admin (own) | `page`, `page_size`, `bill_id`, `subscription_id`, `from_date`, `to_date` |
| GET | `/api/v1/schools/{school_id}/invoices/{invoice_id}` | Super Admin, School Admin (own) | – |
| GET | `/api/v1/schools/{school_id}/invoices/{invoice_id}/pdf` | Super Admin, School Admin (own) | – |

Lists are newest `issued_at` first.

PDF response `200` headers:

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="SUB-2026-000011.pdf"
Cache-Control: private, no-store
X-Content-Type-Options: nosniff
```

The filename keeps only letters, digits, and `-` from the invoice number.

Errors: 401, 403, 404 `Invoice not found` (including another school's invoice under your own `school_id`) / `School not found`, 422 bad query.

## Subscription behaviour (current rules)

- A payment **does not activate, renew, or extend** a subscription. The Super Admin renewal endpoint (`POST /api/v1/super-admin/schools/{school_id}/subscriptions/{id}/renew`) extends the term and creates the pending bill *before* payment; capture only marks that bill paid.
- Renewal happens once per period: the subscription row is locked (`NOWAIT`) and `(subscription_id, period_start)` is unique, so duplicate requests get 409.
- Failed, pending, authorized, duplicate, and refunded payment events never change a subscription.
- Only `active` subscriptions can be renewed; expired or inactive subscriptions cannot be renewed or reactivated by payment.
- A refund does not change the bill or subscription.

These rules are pending product approval; see "Open decisions".

## Environment and Razorpay sandbox setup

| Variable | Required | Notes |
| --- | --- | --- |
| `RAZORPAY_KEY_ID` | yes | `rzp_test_…` outside production; `rzp_live_…` only with `APP_ENV=production`. Returned to clients as `key_id`. |
| `RAZORPAY_KEY_SECRET` | yes | Server only. Used for orders, the checkout signature, and the payment fetch. |
| `RAZORPAY_WEBHOOK_SECRET` | yes for webhooks | Server only. Must equal the secret entered in the Razorpay webhook settings. |
| `RAZORPAY_CURRENCY` | no (default `INR`) | Only `INR` is accepted. |

Sandbox steps:

1. In the Razorpay Dashboard, switch to **Test Mode** and generate API keys (Settings → API Keys). Put them in `backend/.env` (never commit it).
2. Settings → Webhooks → Add: URL `https://<backend-host>/api/v1/payments/webhook/razorpay`, a strong secret (copy it to `RAZORPAY_WEBHOOK_SECRET`), and events `payment.authorized`, `payment.captured`, `payment.failed`, `refund.processed`. For local work, expose the backend with a tunnel (for example ngrok) and use that URL.
3. Enable automatic capture for payments (Account & Settings → Payment capture) so authorized payments become captured.
4. Pay with Razorpay's test cards, UPI ids, or netbanking options from the Razorpay test-mode documentation. No real money moves.
5. Apply migration `20261019_0015` before using these routes on a database (see "Migrations").

## Frontend integration guide (no frontend code is included)

1. Find the bill to pay (`bill_id`, `school_id`, `subscription_id`). At present only Super Admin bill routes exist (`GET /api/v1/super-admin/schools/{school_id}/subscriptions/{id}/bills`); see "Open decisions".
2. Generate one `idempotency_key` per payment intent and call `POST /payments/initiate`. Reuse the key when retrying the same request after a timeout or 5xx.
3. Load `https://checkout.razorpay.com/v1/checkout.js` and open Checkout with `key: key_id`, `order_id`, `amount`, `currency`. Do not compute or send an amount yourself.
4. In the Checkout `handler`, send the three `razorpay_*` fields to `POST /payments/verify`.
5. If the verify `status` is `captured`, the bill is paid. If `authorized`, show "processing" and poll `GET /schools/{school_id}/payments?…` (or the bill) until the status is `captured` or `failed`; the webhook completes it.
6. On `payment.failed` in Checkout, the user can retry: call initiate again (any key) and the same order is returned.
7. Show history from the payments list; when `invoice_id` is set, link to the invoice JSON or download `/invoices/{invoice_id}/pdf` with the bearer token (fetch as a blob; the PDF is not a public URL).
8. Treat 409 from initiate as "already paid or in progress", not as an error to retry.

## Migrations

| Revision | File | Parent | Adds |
| --- | --- | --- | --- |
| `20261017_0013` | `20261017_0013_payment_transactions.py` | `6bfcc3198722` | `payment_transactions`, `payment_webhook_events` |
| `20261017_0014` | `20261017_0014_subscription_invoices.py` | `20261017_0013` | `subscription_invoices`, `subscription_invoice_counters` |
| `20261019_0015` | `20261019_0015_payment_bill_guard.py` | `20261017_0014` | Partial unique index `uq_payment_transactions_bill_open` on `bill_id` where `status <> 4`; nullable diagnostic columns on `payment_webhook_events` |

Single head: `20261019_0015`. Before applying `0015` to a database with payment data, run the duplicate check in the migration docstring.

## Open decisions

- Should a captured payment activate or extend a subscription (pay-then-activate), instead of the current renew-then-pay rule?
- Can a School Admin start a renewal, and can an expired or inactive subscription be renewed through payment?
- Should a full refund change the bill status (for example back to pending or to cancelled)? Currently it does not.
- School Admins have no read endpoint for their own subscription or bills, which a "Pay" screen needs to find `bill_id`.
