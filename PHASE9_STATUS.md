# Phase 9 status — Canary

## Status: SCAFFOLD (gate blocked)

Proxy examples and runbook written. No live allowlist entries. Default remains 100% Laravel.

## Delivered this pass

| Item | Path |
| --- | --- |
| nginx canary example | `ops/proxy/nginx.canary.conf.example` |
| Canary runbook | `ops/proxy/CANARY_RUNBOOK.md` |
| Empty allowlist template | `ops/proxy/allowlist.empty.txt` |

## Checklist

- [x] Proxy allowlist config example + empty template
- [x] Runbook: shadow reads, no shadow writes, ownership, origin leak, rollback
- [ ] Signed ownership matrix rows for candidate domains
- [ ] Perf baseline numbers filled
- [ ] First read-only domain canary
- [ ] 24h parity green

## Gate: BLOCKED on earlier phases

| Dependency | Why |
| --- | --- |
| Phase 0 | Frozen origins + perf baseline required before canary |
| Phase 1 | Golden fixtures + ownership approvers |
| Phases 3–7 | FastAPI domains must exist and pass contract gates |
| Phase 8 | Admin canary only after `/api/admin` + admin-web readiness |

**Hard rules in force:** never shadow writes; never dual-write; empty allowlist is the rollback switch.
