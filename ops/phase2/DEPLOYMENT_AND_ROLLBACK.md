# Deployment and rollback — Phase 2 operational design

## Topology

```
Clients (Flutter, student-web, admin)
        → frozen public HTTPS / WSS hosts
        → reverse proxy (route + school allowlists)
              ├─ Laravel :8000  (default / warm standby)
              └─ FastAPI :8001  (canary allowlist only)
Shared: MySQL (central + tenants), Redis, /storage, Reverb
```

Proxy configs live under `ops/proxy/` (Phase 9 fleshes out concrete nginx/Caddy snippets). Phase 2 locks the **rules**.

---

## Route-level canary

### Mechanics

1. Default upstream = **Laravel**.
2. Allowlist entries: `{method, path_pattern, school_cohort?, owner=fastapi}`.
3. School cohort optional: internal staff schools first, then expanding codes.
4. Each mutable domain has rollback switch id from ownership matrix, e.g. `proxy:domain:webhook`.
5. **Read shadow:** duplicate GET to FastAPI without committing; compare; never shadow writes.
6. Reject responses that leak temporary FastAPI/media/socket origins (middleware or contract assert).

### Canary states (from plan)

| State | Traffic |
| --- | --- |
| Baseline | 100% Laravel |
| Read shadow | Laravel serves; FastAPI shadow reads |
| Route read canary | Allowlisted reads → FastAPI |
| Domain write canary | Entire domain lifecycle → FastAPI (API+admin+webhook+worker+schedule) |
| Admin module canary | Blade mutations frozen for that module |
| Rolled back | Allowlist removed; Laravel serves |

### Deploy sequence for a domain

1. Ship FastAPI build capable of the domain (no traffic).
2. Approve ownership matrix row.
3. Enable read canary / shadow; watch SLOs 24h.
4. Move webhooks if payment-related **before** writes.
5. Stop Laravel workers/schedules for that domain; drain queues.
6. Flip proxy write allowlist + enable FastAPI workers.
7. Freeze conflicting Blade routes.
8. Hold for error-budget window; expand school cohort.

---

## Warm Laravel

During the entire canary and post-cutover rollback window:

| Keep running | Why |
| --- | --- |
| Laravel PHP-FPM/Octane + nginx | Instant proxy rollback |
| Laravel queue workers for **domains not yet transferred** | Avoid stalled jobs |
| Laravel scheduler | Until each command transfers |
| Reverb | Shared realtime |
| DB credentials / `.env` parity | Same data plane |

Do **not** deprovision Laravel VMs, revoke DB users, or drop Horizon until Phase 10 stabilization + separate archive approval.

Warm does **not** mean dual-consuming transferred queues — transferred jobs stay FastAPI-only.

---

## RTO / RPO (design targets)

| Scenario | RTO (target) | RPO | Mechanism |
| --- | --- | --- | --- |
| Single route/domain rollback | **≤ 5 minutes** | 0 (shared DB) | Proxy allowlist revert + re-enable Laravel worker if needed |
| Full API rollback to Laravel | **≤ 15 minutes** | 0 | Default upstream Laravel; disable FastAPI allowlists |
| Bad migration / data | Per [BACKUP_RESTORE.md](BACKUP_RESTORE.md) | Last backup | Restore drill |
| Redis flush incident | **≤ 30 minutes** | Cache rebuild + tracking link invalidation | Regenerate links; settings rewarm |

Fill measured RTOs after the first staging rollback drill; update this table and Phase 9 gate.

---

## Rollback runbook (short)

1. Declare incident; note `request_id`s and domain.
2. Flip proxy switch `proxy:domain:{name}` → Laravel (or remove all FastAPI allowlists).
3. If workers were FastAPI-owned: stop FastAPI consumers; start Laravel workers/schedule for that domain.
4. Verify health: login, one write, webhook test ping, queue depth.
5. Leave FastAPI deployed but dark for forensics.
6. Postmortem before re-canary.

DNS TTL: reduce in advance of Phase 10 hostname retention cutover (hosts stay frozen; TTL matters for any edge CDN change).

---

## Deploy hygiene

- Version both stacks; proxy logs `owner` + build SHA.
- Config/secrets via same vault; `APP_KEY` and Redis identical.
- Migrations: ledger only ([PROVISIONING_AND_MIGRATIONS.md](PROVISIONING_AND_MIGRATIONS.md)); never block rollback on FastAPI-only schema that Laravel cannot read — **avoid incompatible DDL until Laravel archived**.
- Health: `/health` liveness, `/ready` checks MySQL+Redis; proxy uses ready for canary upstream.

---

## Acceptance pointers

Staging drill: flip one read route to FastAPI and back within RTO; flip webhook domain with payment sandbox; confirm Laravel warm serves within 5 minutes; no dual finalize locks.
