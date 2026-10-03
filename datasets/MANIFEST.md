# Sanitized dataset manifest

Generated offline for Phase 0/1 gates.

| Database | Files | Purpose |
| --- | --- | --- |
| `eschool_central` | `central.schema.sql`, `central.data.sanitized.sql` | Central schools/settings |
| `eschool_tenant_a` | `eschool_tenant_a.schema.sql`, `eschool_tenant_a.data.sanitized.sql` | Tenant A (`DEMOA`) |
| `eschool_tenant_b` | `eschool_tenant_b.schema.sql`, `eschool_tenant_b.data.sanitized.sql` | Tenant B (`DEMOB`) |

All emails/phones/addresses are synthetic. Password for seeded users: `secret`.

Load: `./datasets/load_mysql.sh` (requires Docker MySQL from `ops/docker-compose.phase0.yml`).
Local SQLite mirror for golden capture: `python3 datasets/seed_sqlite_mirror.py`.
