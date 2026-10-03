# Phase 9 — Canary runbook

Default traffic stays on **Laravel**. FastAPI receives only **allowlisted** path prefixes. Empty allowlist = full rollback.

## Preconditions (do not skip)

- [ ] Phase 0 frozen origins signed (`baseline/FROZEN_ORIGINS.md`)
- [ ] Laravel perf baseline filled (`baseline/LIMITS_AND_BASELINE.md`)
- [ ] Phase 1 golden fixtures for the candidate domain
- [ ] Ownership matrix row signed for the domain (`contract-tests/ownership/`)
- [ ] FastAPI readiness: health, tenant DB, Redis, no production DDL
- [ ] Monitoring dashboards wired for 5xx, p95, business-error body codes, origin-leak alerts

## Shadow reads (allowed)

Shadow = duplicate a **safe GET/HEAD** (or idempotent read) to FastAPI **without** returning FastAPI’s response to the client.

1. Client request still served by Laravel (source of truth).
2. Async or sidecar copy of the read hits FastAPI with the same auth/tenant context.
3. Diff status codes, JSON shape, and media URL hosts against Laravel.
4. Fail the canary candidate if FastAPI emits a temporary hostname, wrong tenant, or schema drift.
5. Cap shadow rate; never shadow payment confirmations or anything with side effects.

**Never shadow writes.** No POST/PUT/PATCH/DELETE shadowing, no webhook replays to both backends, no dual queue consumers.

## Live canary (allowlist)

1. Start with **read-only** domains.
2. Add one path prefix to the nginx allowlist (see `nginx.canary.conf.example`).
3. Reload nginx; confirm `allowlist.empty.txt` remains the rollback artifact.
4. Watch 24h parity: error rates, p95 vs Laravel baseline, golden fixture spot checks.
5. Only after read parity + signed write ownership: allowlist write paths for that domain **as one lifecycle** (API + admin + webhook + worker/schedule).

## Ownership enforcement

- Matrix state must move Baseline → CanaryRead → CanaryWrite → FastAPIOwned with approver + date.
- Rollback switch id is `proxy:domain:<name>` (see ownership matrix).
- Reject any change that leaves Laravel writing the same workflow as FastAPI.

## Origin leak rejection

During canary, responses from FastAPI must use the **frozen public origin** only.

Reject / page the domain if any of the following appear in JSON, HTML, redirects, emails, notifications, or payment sessions:

- Temporary FastAPI host / container DNS
- `127.0.0.1:8001` or internal service URLs
- Mismatched media/`APP_URL` vs signed frozen origins

Primary fix is application config; proxy hide/filter is defense in depth only.

## Rollback switch

| Action | Steps |
| --- | --- |
| Immediate | Replace live allowlist with `allowlist.empty.txt` (or empty the map) and `nginx -s reload` |
| Verify | Spot-check previously canaried paths hit Laravel; confirm no FastAPI access logs for those paths |
| Matrix | Revert domain row to Baseline; record incident notes |
| Data | No dual-write cleanup expected if write canary was never enabled; if writes leaked, follow domain-specific restore from Laravel backups |

## Gate

24h parity green + no origin leaks + ownership signed. Blocked until FastAPI domain implementations and Phase 0/1 baselines exist. See [PHASE9_STATUS.md](../../PHASE9_STATUS.md).
