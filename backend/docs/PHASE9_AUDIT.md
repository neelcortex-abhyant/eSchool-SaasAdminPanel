# PHASE 9 — BLOCKED / DEFERRED

| Field | Status |
|---|---|
| Audit | COMPLETE |
| Implementation | NOT STARTED |
| Revenue | NOT AVAILABLE |
| Fake payment/revenue functionality | NOT IMPLEMENTED |

## Reason

No real payment gateway or payment transaction source exists
in the current FastAPI backend.

## Audit findings (frozen)

Live Neon (shared app DB):

- `payment_transactions` — DOES NOT EXIST
- `payment_configurations` — DOES NOT EXIST
- `subscription_bills` — EXISTS (Phase 5 bill records; status/amount only)
- `subscriptions` — EXISTS (no gateway fields)

`catalog.py` lists `payment_*` for Laravel import mapping only — not migrated DDL.

Code reality:

- No Razorpay/Stripe/Paystack/Flutterwave SDK usage in backend app code
- No gateway credentials verification / charge / refund / capture logic
- `/api/webhook/{stripe,razorpay,paystack,flutterwave}`: append raw body to
  `webhook_events.jsonl`; return `"Webhook received"` — NO signature
  verification, NO DB writes, NO bill/subscription updates
- `/api/subscription/webhook/{razorpay,stripe}`: stubs.py generic stub (501)
- Parent fee endpoints: accept payment_id fields, echo/ack only
- Dashboard marks `payment_gateway_revenue` / `payment_transactions` as unavailable

Ops docs (`ops/phase2/PAYMENTS_AND_WEBHOOKS.md`) describe intended Laravel
parity — design target, not current FastAPI behavior.

## Decision

Phase 9 stays **BLOCKED / DEFERRED** until a real provider + verified webhook
flow is explicitly scoped. No fake payment or fake revenue APIs will be added.
