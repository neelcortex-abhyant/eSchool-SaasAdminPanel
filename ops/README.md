# Operations

| Path | Purpose |
| --- | --- |
| `docker-compose.phase0.yml` | Local MySQL 8 + Redis for reproducible Phase 0/1 work |
| `phase2/` | Phase 2 operational design runbooks (queue, cache, storage, realtime, payments, security, deploy, acceptance) |
| `proxy/` | Phase 9 canary: `nginx.canary.conf.example`, `CANARY_RUNBOOK.md`, `allowlist.empty.txt` |
| `workers/` | Queue worker ownership transfer notes |
| `scheduler/` | Cron/schedule ownership and timezone rules |
| `monitoring/` | SLO dashboards and alert thresholds |
| `cutover/` | Phase 10: cutover, rollback, stabilization, DNS TTL runbooks |

Phase 2 status: [../PHASE2_STATUS.md](../PHASE2_STATUS.md). Gate = human review of `phase2/ACCEPTANCE_TESTS.md`.

Start local deps:

```bash
docker compose -f ops/docker-compose.phase0.yml up -d
```

MySQL is published on host port `3307`, Redis on `6380`, to avoid colliding with common local defaults.
