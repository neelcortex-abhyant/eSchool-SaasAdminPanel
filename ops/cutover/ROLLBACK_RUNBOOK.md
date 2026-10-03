# Phase 10 — Rollback runbook

Goal: restore Laravel as the sole public upstream within minutes, without Flutter client changes.

## Triggers (any one)

- Elevated 5xx or business-error rate vs baseline
- Origin leak (temporary FastAPI/media host in client-visible payloads)
- Auth/token breakage (Sanctum opacity / logout / bootstrap mismatch)
- Payment or webhook failure
- Cross-tenant data incident
- Queue/schedule dual-consumer or lost jobs

## Immediate rollback (proxy)

1. Set canary/cutover allowlist to empty (`ops/proxy/allowlist.empty.txt`).
2. Point default upstream to Laravel (`127.0.0.1:8000` or current Laravel pool).
3. Reload nginx/gateway.
4. Confirm health on frozen public hostname.
5. Page on-call; open incident channel.

## DNS rollback (if DNS was flipped)

1. Re-point records to the previous Laravel edge/VIP.
2. Respect TTL — if TTL was not lowered, expect longer client convergence ([DNS_TTL_CHECKLIST.md](DNS_TTL_CHECKLIST.md)).
3. Keep FastAPI up but **out of path** until root cause is known.

## Post-rollback checks

- [ ] Student/staff/parent login
- [ ] Fee read + one payment webhook (sandbox/staging first if possible)
- [ ] Media URLs use frozen origin
- [ ] Queues draining on Laravel only
- [ ] Cron/schedule ownership back on Laravel for affected domains
- [ ] Ownership matrix rows reverted to Baseline / CanaryRead as appropriate
- [ ] No dual-writes occurred; if they did, execute domain restore plan

## Data caution

Because the migration forbids dual-write, rollback should not require merge conflict resolution **if** write ownership was exclusive. If FastAPI wrote during a partial cutover, restore from pre-cutover backup for affected tenant DBs and document lost-window impact.

## Communication

- Status page / stakeholder notice: rolled back to Laravel; Flutter apps unchanged.
- Do not ship emergency Flutter baseUrl changes unless an unrelated incident requires it.
