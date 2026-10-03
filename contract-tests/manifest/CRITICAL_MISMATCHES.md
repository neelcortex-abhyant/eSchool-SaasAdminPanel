# Critical contract mismatches

## 1. Parent fee legacy paths missing from Laravel `api.php`

Flutter student app still defines and (for some) calls:

| Flutter constant | Path | Client status | Laravel status | Manifest status |
| --- | --- | --- | --- | --- |
| `addFeesTransaction` | `POST /api/parent/add-fees-transaction` | Method body commented out | Not routed | `dead_client_constant` |
| `getPaidFeesListParent` | `GET /api/parent/fees-paid-list` | `fetchFeesList` commented out | Not routed | `dead_client_constant` |
| `storeFeesParent` | `POST /api/parent/store-fees` | **Still called** (`storeFees`, transport payment repo) | Not routed | `missing_in_laravel_live_client` |
| `failPaymentTransaction` | `POST /api/parent/fail-payment-transaction` | **Still called** (fee cubit / transport repo) | Not routed | `missing_in_laravel_live_client` |

Current Laravel parent fee API under `/api/parent/fees/*`:

- `GET /api/parent/fees`
- `POST /api/parent/fees/compulsory/pay`
- `POST /api/parent/fees/optional/pay`
- `POST /api/parent/fees/manual/compulsory/pay`
- `POST /api/parent/fees/manual/optional/pay`
- receipts/transactions/manual status helpers

### Required decision before FastAPI fees port

Pick one and record in ownership matrix:

1. **Restore** the four legacy routes in FastAPI for binary compatibility (even if Laravel archive dropped them), or
2. **Confirm** production Flutter binaries no longer hit them (instrument staging), treat as dead constants, and fixture only `/api/parent/fees/*`.

Until decided, classify these rows as `missing_in_laravel` / unresolved. Do not silently omit them from the manifest.

## 2. Staff `get-image`

| Item | Finding |
| --- | --- |
| Constant | `Api.getUserImage` → `get-image` |
| Referenced by name | No |
| Hardcoded call | `trip.dart` → `https://wrteam.net/api/get-image?user_id=…&type=profile` |
| In Laravel `api.php` | **No** |

Classification: `conditional`. Confirm whether production traffic uses `wrteam.net` or the school API host before implementing or retiring.

## 3. Odd spellings (preserve)

- `student-exan-result-pdf`
- `driver-helpr/*`
- `student/guradian-details`
