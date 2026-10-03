# Limits and performance baseline

## Known product limits (from plan + Laravel UI)

| Limit | Value | Notes |
| --- | --- | --- |
| Upload size | up to 50 MB / server `upload_max_filesize` | Admin settings forms surface PHP ini limit |
| Student-web HTTP timeout | 10 seconds | Contract/perf gate in plan |
| Auth tokens | Sanctum opaque `{id}\|plain`, SHA-256 in DB | Must survive cutover |
| Password hashes | bcrypt `$2y$` | Verify in Python |
| Tenant model | 1 MySQL database per school + central DB | Bounded pools required |

## Route volume (inventory seed for Phase 1)

| Surface | Approx size |
| --- | --- |
| `routes/api.php` | ~282 `Route::` registrations |
| `routes/web.php` | ~767 `Route::` registrations |
| Flutter student `api.dart` | 535 lines |
| Flutter staff `api.dart` | 548 lines |

## Performance baseline

**Status: NOT YET MEASURED**

Record against production or staging Laravel before Phase 9 canary:

| Metric | Laravel baseline | FastAPI target | Owner |
| --- | --- | --- | --- |
| Login p95 | TBD | ≤ baseline + agreed budget | |
| Authenticated read p95 | TBD | ≤ baseline + agreed budget | |
| Authenticated write p95 | TBD | ≤ baseline + agreed budget | |
| HTTP 5xx rate | TBD | ≤ baseline | |
| Business-error rate (body codes) | TBD | parity | |
| MySQL connections under load | TBD | no pool exhaustion | |
| Queue age / depth | TBD | no dual consumers | |
| Student-web under 10s timeout | TBD | pass | |
| 50 MB upload success | TBD | pass | |

## How to capture

1. Point a load harness at frozen API origin (staging preferred).
2. Exercise student login, parent fee read, staff features-permission, one upload, one chat history.
3. Store raw results under `baseline/perf/` (create when measured).
4. Do not start Phase 9 without filled numbers and owners.
