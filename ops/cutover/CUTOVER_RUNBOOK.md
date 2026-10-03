# Phase 10 — Cutover runbook

Cut over by **reverse proxy / DNS upstream change only**. Do not edit Flutter Dart constants for this migration.

## Preconditions

- [ ] All in-scope domains FastAPIOwned (or explicitly deferred with business sign-off)
- [ ] Phase 9 24h+ canary green; allowlist covers production traffic for owned domains
- [ ] Frozen origins approved; no origin leaks in canary window
- [ ] Sanctum tokens and bcrypt hashes verified compatible
- [ ] Workers/schedulers ownership transferred without dual consumers
- [ ] Payment gateway + WhatsApp webhooks still pointed at frozen public paths
- [ ] DNS TTL lowered per [DNS_TTL_CHECKLIST.md](DNS_TTL_CHECKLIST.md)
- [ ] Rollback drill completed per [ROLLBACK_RUNBOOK.md](ROLLBACK_RUNBOOK.md)
- [ ] Business + engineering sign-off recorded below

## Cutover sequence

1. **Freeze window** — announce maintenance/soft freeze for schema and risky deploys.
2. **Final backup** — central DB + sample tenants; confirm restore tested recently.
3. **Drain dual paths** — ensure no Laravel cron/queue still owns a FastAPIOwned domain.
4. **Proxy flip** — default upstream → FastAPI for owned surfaces; keep Laravel available for instant rollback.
5. **Admin UI** — point admin traffic at Next.js (`admin-web`) only after `/api/admin` production readiness.
6. **Smoke** — student login, staff login, parent fee read, one webhook ping, one upload ≤ 50 MB, Reverb connect.
7. **Watch** — error budgets and origin-leak alerts for the stabilization window ([STABILIZATION_CHECKLIST.md](STABILIZATION_CHECKLIST.md)).
8. **Raise TTL** — only after stabilization sign-off.

## Sign-off

| Role | Name | Date | Result |
| --- | --- | --- | --- |
| Engineering | | | |
| Operations | | | |
| Business / product | | | |

## Gate

Blocked on Phase 9 canary success and earlier phase gates. See [PHASE10_STATUS.md](../../PHASE10_STATUS.md).
