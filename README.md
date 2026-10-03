# eSchool SaaS — FastAPI + Next.js migration

Canonical migration repository for Phase 0 onward.

Original plan path `/Users/apple/eSchool-Saas` does not exist. This empty GitHub repo is the active migration root:

- Remote: `https://github.com/neelcortex-abhyant/eSchool-SaasAdminPanel.git`
- Local: `/Users/apple/eSchool-SaasAdminPanel`

## Layout

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI service (port 8001 while Laravel owns 8000) |
| `admin-web/` | New Next.js admin UI (port 3000) |
| `contract-tests/` | Black-box compatibility tests and sanitized fixtures |
| `ops/` | Proxy, workers, scheduler, monitoring, cutover, Phase 2 designs |
| `baseline/` | Phase 0 inventories (versions, origins, limits, schema) |
| `datasets/` | Sanitized MySQL dumps (gitignored secrets; placeholders only in git) |

Line-by-line progress: [PHASE_EXECUTION.md](PHASE_EXECUTION.md) and `PHASE0_STATUS.md` … `PHASE10_STATUS.md`.

## Related repositories (do not rewrite Flutter)

| Repo | Role |
| --- | --- |
| `/Users/apple/eSchool-SaasAppCode` | Canonical Flutter student + staff working repo (all app edits here) |
| `/Users/apple/eSchool-SaasStudentWebCode` | Student Next.js target repo |
| `/Users/apple/eSchool-SaasDocMain` | Migration/operator docs target repo |
| `/Users/apple/eSchool-Saas-V1.11.0/...` | Legacy Laravel/admin/student/doc source trees |

## Non-negotiables

- Preserve production API and WebSocket hostnames; cut over by reverse proxy only.
- No Flutter Dart source changes for this migration.
- Laravel remains authoritative until each route group passes its gate.
- Do not dual-write between backends.
- Production startup must never call `create_schema()` or emit DDL.

## Phase status

| Phase | Doc |
| --- | --- |
| 0 | [PHASE0_STATUS.md](PHASE0_STATUS.md) |
| 1 | [PHASE1_STATUS.md](PHASE1_STATUS.md) |
| 8 (admin-web scaffold) | [PHASE8_STATUS.md](PHASE8_STATUS.md) |
| 9 (canary scaffold) | [PHASE9_STATUS.md](PHASE9_STATUS.md) |
| 10 (cutover scaffold) | [PHASE10_STATUS.md](PHASE10_STATUS.md) |

Master checklist: [PHASE_EXECUTION.md](PHASE_EXECUTION.md). Also [LEGACY_SOURCES.md](LEGACY_SOURCES.md) and [baseline/](baseline/).
