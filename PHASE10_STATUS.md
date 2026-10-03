# Phase 10 status — Cutover

## Status: SCAFFOLD (gate blocked)

Cutover/rollback/stabilization/DNS runbooks drafted. No production flip authorized.

## Delivered this pass

| Item | Path |
| --- | --- |
| Cutover runbook | `ops/cutover/CUTOVER_RUNBOOK.md` |
| Rollback runbook | `ops/cutover/ROLLBACK_RUNBOOK.md` |
| Stabilization checklist | `ops/cutover/STABILIZATION_CHECKLIST.md` |
| DNS TTL checklist | `ops/cutover/DNS_TTL_CHECKLIST.md` |

## Checklist

- [x] Cutover / rollback / stabilization / DNS docs
- [ ] Business + engineering sign-off
- [ ] Rollback drill on staging
- [ ] TTL lowered (if DNS flip required)
- [ ] Production cutover executed
- [ ] Stabilization window closed; TTL raised

## Gate: BLOCKED on earlier phases

| Dependency | Why |
| --- | --- |
| Phases 0–1 | Origins, fixtures, ownership |
| Phases 3–7 | FastAPI parity for in-scope domains |
| Phase 8 | Admin Next.js ready if admin is in cutover scope |
| Phase 9 | 24h canary green; allowlist proven; rollback switch rehearsed |

Cutover changes reverse-proxy/DNS upstreams only. Flutter source stays untouched.
