# Phase execution tracker (line-by-line)

Updated during full-phase execution pass.

## Phase 0 — Repository and baseline

- [x] Establish AdminPanel migration repository
- [x] Reference legacy apps without moving them
- [x] Capture versions / fingerprint / limits
- [x] Frozen-origin inventory approved from Flutter AppCode
- [x] Docker Compose MySQL+Redis config
- [x] Sanitized MySQL dumps central + 2 tenants
- [x] SQLite mirrors for offline golden capture
- [ ] Docker CLI on this machine (operator installs; `datasets/load_mysql.sh` ready)
- [ ] Live origin probe (`baseline/probe_origins.sh`) before Phase 9
- [ ] Perf baseline numbers

## Phase 1 — Exhaustive contract lock

- [x] Reconcile Laravel / Flutter AppCode / student-web
- [x] Classify routes; verify get-image
- [x] Encoding/auth/tenant recorded
- [x] Ownership matrix Baseline approved + named approvers
- [x] Sanitization rules
- [x] Orphan decisions documented
- [x] Auth/bootstrap golden fixtures captured
- [ ] Full golden suite for every reachable route (expand next)

## Phase 2 — Operational design

- [x] All 12 runbooks under `ops/phase2/`
- [x] Engineering review sign-off (`ops/phase2/REVIEW_SIGNOFF.md`)
- [ ] Tech Lead countersignature before production canary

## Phase 3 — FastAPI foundation

- [x] Health/readiness, request IDs, CORS+X-Tracking-Token, pooled MySQL settings, DDL guard
- [x] Unit tests passing (7)
- [ ] MySQL cross-tenant / pool exhaustion — **blocked** on dumps/Docker

## Phase 4 — Authentication and middleware

- [x] Multipart student/parent/teacher/staff login + logout variants
- [x] `$2y$` bcrypt + Sanctum token shape
- [x] UserDataResource-shaped student/guardian/staff login graphs
- [x] Staff features-permission stub + golden fixtures
- [x] Unit tests passing (7)
- [ ] Nested teacher/staff salary graphs + exact trans() strings — next parity pass

## Phase 5 — Student/parent reads

- [x] Contract stub router for unported client routes
- [ ] Real read implementations — **next implementation wave**
- [ ] Student Next.js E2E — blocked on implementations + data

## Phase 6 — Writes / payments / webhooks

- [x] Stubs include writes + orphan fee paths
- [x] Webhook-before-write design documented
- [ ] Real implementations + gateway tests — blocked

## Phase 7 — Realtime / workers / schedules

- [x] Designs + folder placeholders
- [ ] Reverb publisher + ARQ workers — blocked on env

## Phase 8 — Admin Next.js

- [x] Next 15 scaffold + login shell + `/api/admin` client
- [ ] Module-by-module ports — iterative after admin API maturity

## Phase 9 — Canary

- [x] nginx canary example + runbook + empty allowlist
- [ ] Live canary — blocked until domains pass gates

## Phase 10 — Cutover

- [x] Cutover / rollback / DNS / stabilization runbooks
- [ ] Business sign-off — blocked

## Summary

Everything that does not require production dumps, Docker, or human sign-off is scaffolded or implemented at foundation level. **Gates for Phases 0–1 and 3–7/9–10 remain open** until MySQL datasets and operator approvals arrive. Multipart auth unit tests are green.
