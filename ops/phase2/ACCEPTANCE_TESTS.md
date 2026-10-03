# Phase 2 acceptance tests — gate checklist

Phase 2 delivers **designs and runbooks**, not production traffic. The gate is **human review** of these documents plus agreement that implementation phases can proceed against them.

Sign-off owner: ________________  
Date: ________________

---

## Document review checklist

| # | Document | Reviewer OK | Notes |
| --- | ---: | --- | --- |
| 1 | [QUEUE_AND_CRON.md](QUEUE_AND_CRON.md) | ☐ | ARQ/Celery choice accepted; attendance TZ; one-owner rule |
| 2 | [CACHE_AND_REDIS.md](CACHE_AND_REDIS.md) | ☐ | Shared Redis; key strings; tracking keys |
| 3 | [STORAGE.md](STORAGE.md) | ☐ | APP_URL; 50MB; no signed media URLs |
| 4 | [REALTIME.md](REALTIME.md) | ☐ | Keep Reverb; Pusher protocol list complete |
| 5 | [PAYMENTS_AND_WEBHOOKS.md](PAYMENTS_AND_WEBHOOKS.md) | ☐ | All api.php + web.php paths; raw body; webhooks before writes |
| 6 | [EMAIL_AND_FCM.md](EMAIL_AND_FCM.md) | ☐ | fcm_id / device_id / web_fcm parity |
| 7 | [PROVISIONING_AND_MIGRATIONS.md](PROVISIONING_AND_MIGRATIONS.md) | ☐ | Ledger; no ORM DDL in prod |
| 8 | [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | ☐ | Drill A–D requirements accepted |
| 9 | [SECURITY.md](SECURITY.md) | ☐ | CORS, CSRF admin, rate limits, open helpers |
| 10 | [OBSERVABILITY.md](OBSERVABILITY.md) | ☐ | request/school IDs; SLO placeholders owned |
| 11 | [DEPLOYMENT_AND_ROLLBACK.md](DEPLOYMENT_AND_ROLLBACK.md) | ☐ | Route canary; warm Laravel; RTO |
| 12 | [PHASE2_STATUS.md](../../PHASE2_STATUS.md) | ☐ | Status accurate |

---

## Queues & schedules

| # | Test / proof (design-level or staging when available) | OK |
| --- | --- | --- |
| Q1 | Inventory of Kernel schedules matches QUEUE_AND_CRON table | ☐ |
| Q2 | Inventory of `app/Jobs` mapped with idempotency keys | ☐ |
| Q3 | Dual-consumer forbidden rule acknowledged by ops | ☐ |
| Q4 | Staff finalize uses school TZ + end+1h due rule documented | ☐ |
| Q5 | Lock key list reviewed for collisions with Laravel | ☐ |
| Q6 | DLQ + retry policy accepted | ☐ |

---

## Cache & Redis

| # | Criterion | OK |
| --- | --- | --- |
| C1 | `systemSettings` / `schoolSettings_{id}` / features keys listed | ☐ |
| C2 | Transportation tracking key patterns listed | ☐ |
| C3 | FastAPI-only prefixes cannot collide with Laravel cache | ☐ |
| C4 | `APP_KEY` stability called out | ☐ |

---

## Storage

| # | Criterion | OK |
| --- | --- | --- |
| S1 | Shared volume/object strategy chosen (A/B/C) | ☐ |
| S2 | 50 MB + proxy body limit called out | ☐ |
| S3 | Explicit ban on signed media URLs without client release | ☐ |
| S4 | Frozen APP_URL dependency noted (Phase 0 sign-off still required) | ☐ |

---

## Realtime

| # | Criterion | OK |
| --- | --- | --- |
| R1 | Reverb retained; publish path defined | ☐ |
| R2 | `NewMessage` + `user.{id}` + ping/pong requirements listed | ☐ |
| R3 | Provision/update progress channels listed | ☐ |
| R4 | No second client-facing socket host | ☐ |

---

## Payments

| # | Criterion | OK |
| --- | --- | --- |
| P1 | All fee + subscription webhook paths (api + web) listed | ☐ |
| P2 | WhatsApp `{schoolCode}` paths listed | ☐ |
| P3 | Raw-body signature rules per gateway | ☐ |
| P4 | Idempotent state machine + row lock | ☐ |
| P5 | **Webhooks before writes** sequencing mandatory | ☐ |
| P6 | Payment return/cancel URLs preserved | ☐ |

---

## Email / FCM

| # | Criterion | OK |
| --- | --- | --- |
| E1 | Token field matrix matches Phase 1 logout fixtures | ☐ |
| E2 | Job ownership follows domain transfer | ☐ |
| E3 | Mail links use frozen origins | ☐ |

---

## Provisioning / migrations

| # | Criterion | OK |
| --- | --- | --- |
| M1 | Steps map to Laravel jobs | ☐ |
| M2 | Resumable ledger fields defined | ☐ |
| M3 | Production ORM DDL ban explicit | ☐ |
| M4 | Privileged migrator vs API pool separation | ☐ |

---

## Backup / restore

| # | Criterion | OK |
| --- | --- | --- |
| B1 | Drills A–D defined with pass criteria | ☐ |
| B2 | RTO/RPO placeholders have owners | ☐ |
| B3 | Shared storage restore across stacks required | ☐ |

---

## Security

| # | Criterion | OK |
| --- | --- | --- |
| X1 | CORS header allowlist includes `X-Tracking-Token` | ☐ |
| X2 | Admin CSRF + cookie flags defined | ☐ |
| X3 | Open helper classification table covers cron, webhooks, firebase-config, tracking | ☐ |
| X4 | Rate-limit classes defined | ☐ |

---

## Observability & deploy

| # | Criterion | OK |
| --- | --- | --- |
| O1 | request_id + school_id logging fields required | ☐ |
| O2 | SLO table placeholders assigned owners | ☐ |
| O3 | Route-level canary + warm Laravel + rollback RTO ≤ 5m domain / ≤ 15m full | ☐ |
| O4 | Incompatible DDL before Laravel archive forbidden | ☐ |

---

## Dependencies outside Phase 2 (do not block design review)

These remain open from Phase 0/1 but are called out so reviewers do not confuse design completion with production readiness:

- [ ] Frozen origins production sign-off (`baseline/FROZEN_ORIGINS.md`)
- [ ] Sanitized MySQL dumps in `datasets/`
- [ ] Laravel perf baseline numbers
- [ ] Phase 1 live orphans (`store-fees`, `fail-payment-transaction`) resolved
- [ ] Ownership matrix approvers assigned

**Phase 2 gate passes when** all document review rows are checked and this file is signed — even if the dependency list above is still open. Implementation (Phase 3+) must not take production traffic until those dependencies and later phase gates also pass.

---

## Explicit non-goals for this gate

- No FastAPI application code required
- No proxy production cutover
- No provider dashboard changes
- No Flutter / student-web source changes
