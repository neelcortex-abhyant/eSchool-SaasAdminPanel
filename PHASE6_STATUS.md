# Phase 6 status — Mobile and staff writes

## Done

- Contract stubs include write endpoints (assignments, fees, QR, transport, payroll, diary, chat, tasks, uploads).
- Phase 1 decision: restore `POST /api/parent/store-fees` and `POST /api/parent/fail-payment-transaction` (stubbed until implemented).
- Payment/webhook design in `ops/phase2/PAYMENTS_AND_WEBHOOKS.md` (webhooks before related writes).

## Not done

- Real gateway integrations, side-effect diffs, file checksums, webhook signature verification

## Gate

**Blocked** on Phase 4/5 data + webhook implementation before enabling fee writes in canary.
