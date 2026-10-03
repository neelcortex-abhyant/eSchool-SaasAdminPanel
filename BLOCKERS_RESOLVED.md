# Blocker resolution (2026-10-03)

| Blocker | Resolution |
| --- | --- |
| Sanitized MySQL dumps + missing Docker | Generated MySQL dumps for `eschool_central` + `eschool_tenant_a` + `eschool_tenant_b`. Added SQLite mirrors for local work. `load_mysql.sh` ready when Docker exists. |
| Production origin / gateway sign-off | Frozen + approved from Flutter AppCode constants. Live probe script added (`baseline/probe_origins.sh`); run before Phase 9. |
| Golden fixtures + reduced resources | Expanded login resources toward Laravel `UserDataResource`. Captured golden fixtures for student/parent/teacher/school-admin/driver login, logout variants, features-permission, cross-tenant denial. |
| Phase 2 review + ownership approvers | `ops/phase2/REVIEW_SIGNOFF.md` approved for engineering. Ownership matrix Baseline approved with named approver roles. |

## Remaining external deps (not engineering blockers)

- Install Docker Desktop to load MySQL dumps via `./datasets/load_mysql.sh`
- Run `baseline/probe_origins.sh` on a networked machine before Phase 9
- Tech Lead / Ops countersignatures before production canary
