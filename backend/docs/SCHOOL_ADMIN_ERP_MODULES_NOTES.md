# School Admin ERP modules 1–5 — notes & blockers

Alembic head after this wave: **`20261029_0041`** (revises `20261028_0040`).  
**Do not** run `alembic upgrade` against Neon from this delivery unless an explicit ops window approves it.

## Implemented

- Fee installments (`fee_installments`) with sum == structure total (INR 2dp, `ROUND_HALF_UP`).
- Payment allocations on new `collect_fee` calls; legacy payments without allocations remain valid.
- Fee payment cancel: soft-delete + `cancelled_at` / `cancel_reason` + allocation reverse + audit log. **No refund / money movement.**
- Report card PDF (admin + student/parent when `Exam.publish == 1`).
- Transport vehicle `driver_staff_id` / `helper_staff_id`, capacity on assignment, trips, GPS HTTP post, board/drop attendance.
- Staff driver routes under `/api/staff/transport/...`.
- Parent live bus poll: `GET /api/parent/children/{student_id}/transport/live` (no WebSockets).

## Explicit blockers / non-goals

| Topic | Status |
| --- | --- |
| GPS retention purge cron | **Not implemented.** Points may set optional `expires_at` from `GPS_RETENTION_DAYS` (default 90). History is kept until a future cron deletes expired rows. |
| Fee refunds / gateway reverse | **Not implemented.** Cancel only (status `cancelled`). No school-fee online gateway; SaaS Razorpay unchanged. |
| WebSocket live tracking | **Not implemented.** Use HTTP polling for GPS / parent live status. |
| Auto installment replace after allocations | **Blocked by design** — returns **409** if any installment already has success allocations. |

## Key paths

- Admin: `/api/v1/school-admin/report-cards/{id}/pdf`, `/fee-structures/{id}/installments`, `/fee-payments/{id}/receipt[/pdf]`, `/fee-payments/{id}/cancel`, `/fees/collection-report`, `/transport-trips...`
- Staff: `/api/staff/transport/my-trips`, `/trips/{id}/gps`, `/trips/{id}/attendance`
- Portal: `/api/student/report-cards...`, `/api/student/fees/...`, `/api/parent/children/{id}/...`
