# Phase 1 contract decisions

Recorded during full phase execution so FastAPI implementation is not blocked on ambiguous orphans.

## Live orphans → restore in FastAPI

Flutter AppCode still calls these paths; Laravel `api.php` no longer routes them.

| Path | Decision |
| --- | --- |
| `POST /api/parent/store-fees` | **Restore** in FastAPI for binary compatibility. Re-implement using commented Laravel `ParentApiController` logic / current fee payment models. |
| `POST /api/parent/fail-payment-transaction` | **Restore** in FastAPI for binary compatibility. |

Ownership: `parent` domain remains Laravel until these routes are fixture-tested on FastAPI; then transfer as one fee-payment lifecycle with webhooks.

## Dead client constants → do not implement unless traffic proves otherwise

| Path | Decision |
| --- | --- |
| `POST /api/parent/add-fees-transaction` | Retire from FastAPI contract (call site commented). Keep in manifest as `dead_client_constant`. |
| `GET /api/parent/fees-paid-list` | Retire (call site commented). Prefer `/api/parent/fees` family. |

## get-image → conditional external

| Path | Decision |
| --- | --- |
| `GET /api/get-image` | Not on school Laravel API. Staff `trip.dart` hardcodes `https://wrteam.net/api/get-image`. Do **not** implement on school FastAPI unless production traffic shows school-host usage. |

## Odd spellings

Preserve exactly: `student-exan-result-pdf`, `driver-helpr/*`, `student/guradian-details`.
