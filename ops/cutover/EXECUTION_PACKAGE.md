# Canary / cutover execution package

## Status

| Item | Path | Status |
| --- | --- | --- |
| Nginx canary example | `ops/proxy/nginx.canary.conf.example` | Ready |
| Empty allowlist (rollback default) | `ops/proxy/allowlist.empty.txt` | Ready |
| Read-only candidate allowlist | `ops/proxy/allowlist.read_candidates.txt` | Ready (commented) |
| Canary runbook | `ops/proxy/CANARY_RUNBOOK.md` | Ready |
| Cutover runbook | `ops/cutover/CUTOVER_RUNBOOK.md` | Ready |
| Rollback runbook | `ops/cutover/ROLLBACK_RUNBOOK.md` | Ready |
| DNS TTL checklist | `ops/cutover/DNS_TTL_CHECKLIST.md` | Ready |
| Stabilization checklist | `ops/cutover/STABILIZATION_CHECKLIST.md` | Ready |
| Ownership matrix | `contract-tests/ownership/DOMAIN_OWNERSHIP_MATRIX.md` | Baseline approved |
| Frozen origins | `baseline/FROZEN_ORIGINS.md` | Engineering approved |

## Production cutover rule

Flutter URLs stay unchanged. Switch reverse-proxy upstreams for the frozen API and WebSocket hosts only.

## Go / no-go before enabling any allowlist line

1. Live origin probe (`baseline/probe_origins.sh`) passes
2. MySQL dumps loaded (`./datasets/load_mysql.sh`)
3. Domain ownership row moved to CanaryRead with approver
4. Golden fixtures green for that domain
5. 24h shadow-read parity acceptable
6. Rollback drill completed using empty allowlist
