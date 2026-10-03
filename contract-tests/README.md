# Contract tests

Phase 1 locks the HTTP contract before FastAPI implementation.

## Layout

| Path | Contents |
| --- | --- |
| `manifest/` | Source extracts + reconciled route inventory |
| `ownership/` | Domain write-ownership matrix (canary Baseline) |
| `fixtures/templates/` | Auth/bootstrap capture schemas |
| `fixtures/golden/` | Sanitized golden bodies (created after dumps) |
| `scripts/` | Regenerators (e.g. Laravel route parser) |

## Start here

1. [manifest/RECONCILIATION_REPORT.md](manifest/RECONCILIATION_REPORT.md)
2. [manifest/CRITICAL_MISMATCHES.md](manifest/CRITICAL_MISMATCHES.md)
3. [ownership/DOMAIN_OWNERSHIP_MATRIX.md](ownership/DOMAIN_OWNERSHIP_MATRIX.md)
4. [../PHASE1_STATUS.md](../PHASE1_STATUS.md)

## Regenerating Laravel routes

```bash
python3 contract-tests/scripts/parse_laravel_routes.py
```
