# Phase 3 status — FastAPI foundation

## Done

- Backend living in `/Users/apple/eSchool-SaasAdminPanel/backend` (copied from prototype, hardened)
- `/health` and `/ready`
- Request ID middleware + structured request logs
- CORS includes `X-Tracking-Token`, `school-code`, credentials
- MySQL-default settings; SQLite only for unit tests
- `create_schema` hard-blocked unless `ALLOW_DDL=true` and not production
- Engine pools with `pool_size` / `max_overflow`
- Unit tests: **7 passed** (multipart login paths)

## Gate

Cross-tenant + connection-exhaustion tests on MySQL: **blocked** until Phase 0 dumps + MySQL/Docker available.
