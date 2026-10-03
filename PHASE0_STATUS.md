# Phase 0 status

## Decision: migration repository root

| Item | Value |
| --- | --- |
| Active root | `/Users/apple/eSchool-SaasAdminPanel` |

## Checklist

- [x] Establish migration repository layout
- [x] Map legacy sources
- [x] Classify prototype scaffold
- [x] Capture dependency/client versions
- [x] Freeze public origins from Flutter AppCode (`baseline/FROZEN_ORIGINS.md`)
- [x] Capture limits placeholders
- [x] Schema fingerprint
- [x] Docker Compose config
- [x] Sanitized MySQL dumps: central + 2 tenants (`datasets/*.data.sanitized.sql`)
- [x] Local SQLite mirrors for offline work (`datasets/seed_sqlite_mirror.py`)
- [ ] Docker CLI install on this machine (operator) — load script ready
- [ ] Live origin probe on networked machine (`baseline/probe_origins.sh`)
- [ ] Measured Laravel perf numbers

## Gate

**Engineering gate: PASS** with synthetic sanitized dumps + frozen client origins.  
**Production canary gate:** still needs live probe + Docker/MySQL load verification + perf numbers.
