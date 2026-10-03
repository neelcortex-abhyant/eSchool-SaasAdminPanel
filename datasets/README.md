# Datasets

Sanitized synthetic MySQL dumps for Phase 0/1 gates (no production PII).

## Files

| File | Purpose |
| --- | --- |
| `central.schema.sql` / `central.data.sanitized.sql` | Central DB |
| `eschool_tenant_a.*` | Tenant A (`DEMOA`) |
| `eschool_tenant_b.*` | Tenant B (`DEMOB`) |
| `generate_sanitized_dumps.py` | Regenerate dumps |
| `seed_sqlite_mirror.py` | Local SQLite mirrors for golden capture without Docker |
| `load_mysql.sh` | Load into Docker MySQL (port 3307) |
| `MANIFEST.md` | Dataset inventory |

## Seed credentials (synthetic)

- Password for all seeded users: `secret`
- Schools: `DEMOA`, `DEMOB`
- Student GR: `GR001`
- Parent: `guardian@school.test`
- Teacher: `teacher@school.test`

## Commands

```bash
# Offline regenerate + local SQLite mirrors + golden fixtures
python3 datasets/generate_sanitized_dumps.py
python3 datasets/seed_sqlite_mirror.py
python3 contract-tests/scripts/capture_golden_fixtures.py

# When Docker is installed
./datasets/load_mysql.sh
```
