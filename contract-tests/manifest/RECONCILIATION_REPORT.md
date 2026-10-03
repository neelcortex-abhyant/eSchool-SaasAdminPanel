# Phase 1 — API contract reconciliation

## Counts

- **flutter_student_constants**: 106
- **flutter_staff_constants**: 139
- **student_web_endpoints**: 60
- **laravel_api_routes**: 253
- **laravel_web_payment_routes**: 11
- **reconciled_api_rows**: 258
- **client_reachable_rows**: 216
- **by_status** (refined):
  - `active`: 211
  - `active_external`: 8
  - `conditional`: 1 (`get-image`)
  - `dead_or_admin_only`: 34
  - `dead_client_constant`: 2
  - `missing_in_laravel_live_client`: 2

## get-image (staff)

- Constant `Api.getUserImage` → `/api/get-image` is **not referenced** by name.
- `trip.dart` hardcodes `https://wrteam.net/api/get-image?user_id=…&type=profile`.
- Present in Laravel api.php: **False**.
- Classification: `conditional`. Confirm whether production uses wrteam.net host or school API host; do not drop until verified.

## Odd spellings to preserve

- `student-exan-result-pdf`
- `driver-helpr`
- `guradian-details`
- `get-image`

## Encoding exceptions

- `/api/delete/message`: JSON or multipart (student-web JSON exception; Flutter multipart)
- `/api/certificate/generate`: multipart request, `text/html` response
- `/api/transportation/live-tracking/session`: `X-Tracking-Token`, real HTTP 401/410/429
- `/api/set-languages`: read-like POST returning translation data

## Missing / orphan client paths

See [CRITICAL_MISMATCHES.md](CRITICAL_MISMATCHES.md).

| Path | Status |
| --- | --- |
| `POST /api/parent/store-fees` | `missing_in_laravel_live_client` — still called |
| `POST /api/parent/fail-payment-transaction` | `missing_in_laravel_live_client` — still called |
| `POST /api/parent/add-fees-transaction` | `dead_client_constant` — call site commented |
| `GET /api/parent/fees-paid-list` | `dead_client_constant` — call site commented |

## Method mismatches

_None_

## Client-reachable routes without fixture yet

Total client-reachable: 216. Fixture templates seeded for auth/bootstrap only; full golden bodies require MySQL dumps (Phase 0 gate).

## Files

- `reconciled_manifest.json` / `reconciled_manifest.csv`
- `flutter_student_paths.json` / `flutter_staff_paths.json`
- `student_web_endpoints.json`
- `laravel_api_routes.json` / `laravel_web_payment_routes.json`
- `CRITICAL_MISMATCHES.md`
