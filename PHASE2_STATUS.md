# Phase 2 status — operational design

## Summary

Phase 2 **design deliverables are complete** and ready for **human review**. No application code was implemented in this pass. The Phase 2 gate is review/sign-off of the runbooks under `ops/phase2/`, not production traffic.

## Deliverables

| Document | Path |
| --- | --- |
| Queue & cron | [ops/phase2/QUEUE_AND_CRON.md](ops/phase2/QUEUE_AND_CRON.md) |
| Cache & Redis | [ops/phase2/CACHE_AND_REDIS.md](ops/phase2/CACHE_AND_REDIS.md) |
| Storage | [ops/phase2/STORAGE.md](ops/phase2/STORAGE.md) |
| Realtime | [ops/phase2/REALTIME.md](ops/phase2/REALTIME.md) |
| Payments & webhooks | [ops/phase2/PAYMENTS_AND_WEBHOOKS.md](ops/phase2/PAYMENTS_AND_WEBHOOKS.md) |
| Email & FCM | [ops/phase2/EMAIL_AND_FCM.md](ops/phase2/EMAIL_AND_FCM.md) |
| Provisioning & migrations | [ops/phase2/PROVISIONING_AND_MIGRATIONS.md](ops/phase2/PROVISIONING_AND_MIGRATIONS.md) |
| Backup & restore | [ops/phase2/BACKUP_RESTORE.md](ops/phase2/BACKUP_RESTORE.md) |
| Security | [ops/phase2/SECURITY.md](ops/phase2/SECURITY.md) |
| Observability | [ops/phase2/OBSERVABILITY.md](ops/phase2/OBSERVABILITY.md) |
| Deployment & rollback | [ops/phase2/DEPLOYMENT_AND_ROLLBACK.md](ops/phase2/DEPLOYMENT_AND_ROLLBACK.md) |
| Acceptance checklist | [ops/phase2/ACCEPTANCE_TESTS.md](ops/phase2/ACCEPTANCE_TESTS.md) |

## Design highlights (for reviewers)

- **Workers:** Redis + **ARQ** recommended (Celery acceptable fallback); shared Redis with Laravel; one owner per job/schedule.
- **Attendance:** School-local timezone; finalize at school end + 1 hour; distributed locks; no dual consumers.
- **Cache:** Preserve Laravel key strings (`systemSettings`, `schoolSettings_{id}`, transportation tracking keys).
- **Storage:** Shared `/storage` + frozen `APP_URL`; 50 MB; no signed media URLs without client release.
- **Realtime:** Keep **Reverb**; FastAPI publishes; exact Pusher/`NewMessage` contract.
- **Payments:** All `api.php` + `web.php` webhook/return paths; raw-body signatures; **migrate webhooks before writes**.
- **DDL:** Resumable tenant ledger; **no production ORM DDL**.
- **Canary:** Route-level proxy; warm Laravel; domain RTO ≤ 5 minutes.

## Gate status: ENGINEERING REVIEW PASSED

| Gate item | Status |
| --- | --- |
| Queue/cron/cache/storage/realtime/payment/email/provision/backup/security/observability/deploy designs written | **Done** |
| Acceptance checklist published | **Done** |
| Migration Engineer review | **Passed** — see [ops/phase2/REVIEW_SIGNOFF.md](ops/phase2/REVIEW_SIGNOFF.md) |
| Ownership matrix Baseline + named approvers | **Passed** |
| Tech Lead countersignature | Required before production canary |

| Human review sign-off on [ACCEPTANCE_TESTS.md](ops/phase2/ACCEPTANCE_TESTS.md) | **Pending** |
| Production traffic / FastAPI implementation | Out of scope for Phase 2 |

## Upstream dependencies (do not confuse with Phase 2 gate)

Still open from Phase 0/1 — required before later production canaries, not before design review:

1. Frozen origins production confirmation  
2. Sanitized central + 2 tenant dumps  
3. Perf baseline numbers  
4. Phase 1 orphan fee routes + ownership approvers  

## Next after sign-off

Proceed to **Phase 3 — FastAPI foundation** (health, logs, request/school IDs, CORS, Redis/MySQL pools, no DDL), implementing against these runbooks.
