# MySQL schema fingerprint — v1.11 baseline

## Policy

- Do not regenerate the v1.11 schema from scratch.
- Mark v1.11 as the migration baseline.
- Future changes use a migration ledger for central + tenant DBs.

## Migration file fingerprint (local archive)

| Field | Value |
| --- | --- |
| Path | `.../PHP_CODE_V1.11.0/database/migrations` |
| File count | 26 PHP migrations (27 entries including directory listing) |
| Name+size SHA-256 | `4a4129f22386553a69113cac0e77adf673b18645c1c52dedf46a85321f6ff072` |
| First | `2014_10_12_000000_create_users_table.php` |
| Last | `2026_08_03_144725_version_1_10_0.php` |

Note: product is labeled v1.11.0 while the newest migration filename ends at `version_1_10_0`. Treat the archive contents as the authoritative baseline, not the filename alone.

## Live schema dump

**Status: BLOCKED — MySQL client not available and no sanitized dump provided yet.**

Required for Phase 0 gate:

1. Central database dump (structure + sanitized seed)
2. Tenant A dump
3. Tenant B dump
4. `SHOW CREATE TABLE` fingerprint file for both central and one tenant

Place dumps under `datasets/` (gitignored). Keep only sanitized fixtures in git under `contract-tests/fixtures/`.

### Capture commands (run where MySQL is available)

```bash
mysqldump --no-data --routines --triggers central_db > datasets/central.schema.sql
mysqldump --no-data --routines --triggers tenant_a > datasets/tenant_a.schema.sql
mysqldump --no-data --routines --triggers tenant_b > datasets/tenant_b.schema.sql
# sanitized data dumps separately; strip secrets, real emails, tokens, payment keys
```

## Schema rules FastAPI must preserve

- `utf8mb4` collation
- generated columns, enums, soft deletes
- money as `Decimal` (no float)
- SQL mode parity with Laravel
- `personal_access_tokens` Sanctum columns including `tokenable_type`, abilities, expiry, `last_used_at`
