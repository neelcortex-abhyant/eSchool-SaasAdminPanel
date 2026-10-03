# Phase 7 status — Realtime, workers, schedules

## Done

- Design: `ops/phase2/REALTIME.md`, `QUEUE_AND_CRON.md`
- Folders ready: `ops/workers/`, `ops/scheduler/`

## Scaffold notes

| Item | Plan |
| --- | --- |
| Realtime | Keep Reverb; FastAPI publishes Pusher-compatible events |
| Workers | Redis + ARQ (see Phase 2); one owner vs Laravel |
| Schedules | School-local timezone for attendance finalization |

## Gate

**Blocked** until FastAPI can publish through Reverb and a 24h shadow comparison environment exists.
