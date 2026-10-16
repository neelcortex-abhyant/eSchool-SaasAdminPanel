# Subscription and plan API

Super Admin plan and school-subscription routes. These endpoints do not collect a payment and do not call a payment gateway.

Authentication is the existing opaque Bearer session. The caller must be a Super Admin (`require_super_admin`). The database dependency is `central_db`. Responses are direct JSON. They are not wrapped in `success` or `data`.

| HTTP | When |
| --- | --- |
| 401 | Missing or unknown Bearer token. `detail` is `Not authenticated`. |
| 403 | The signed-in user is not a Super Admin. `detail` is `Forbidden`. |

A path id that is not an integer follows the existing FastAPI 422 validation response. Request bodies use `extra = forbid`, so an unknown field is also 422.

`GET /api/admin/packages` is a separate legacy list. It is not this API.

## Plans

Plans are rows in `packages`. There is no separate plans table. A new plan is created with `status = 0` (unpublished). `1` is published. Deactivating a plan does not change subscriptions already assigned to it.

| Method | Path | Success |
| --- | --- | --- |
| POST | `/api/v1/super-admin/plans` | 201 |
| GET | `/api/v1/super-admin/plans` | 200 |
| GET | `/api/v1/super-admin/plans/{plan_id}` | 200 |
| PATCH | `/api/v1/super-admin/plans/{plan_id}` | 200 |
| PATCH | `/api/v1/super-admin/plans/{plan_id}/status` | 200 |

There is no plan delete route.

### Create body

```json
{
  "name": "Standard",
  "description": "",
  "monthly_price": 0,
  "yearly_price": 0,
  "student_limit": null,
  "staff_limit": null
}
```

`name` is required, 1 through 255 characters, then trimmed. `description` defaults to `""` and is stored up to 255 characters. `monthly_price` and `yearly_price` default to `0` and must be at least `0`. After rounding half up to cents, each price must be from 0 through 9999999999.99. `student_limit` and `staff_limit` are optional and, when sent, must be at least `0`.

The stored and returned price is that rounded cent value, as a JSON number.

### Update body

Every field is optional. Omitted fields stay unchanged. `student_limit` or `staff_limit` sent as `null` clears that limit. A sent price is checked together with the price that is already stored.

### Status body

```json
{"status": 1}
```

`status` must be `0` or `1`.

### Plan response

```json
{
  "id": 3,
  "name": "Standard",
  "description": "",
  "status": 0,
  "monthly_price": 10.0,
  "yearly_price": 100.0,
  "student_limit": null,
  "staff_limit": null,
  "deleted_at": null,
  "created_at": "2026-10-01T00:00:00",
  "updated_at": "2026-10-01T00:00:00"
}
```

`name` and `description` may be null on older rows.

### List

`GET /api/v1/super-admin/plans`

| Parameter | Default | Rules |
| --- | --- | --- |
| `page` | `1` | Integer, minimum 1. |
| `page_size` | `20` | Integer, 1 through 100. |
| `status` | omitted | Optional integer. Rows with that `packages.status` are returned. The route does not restrict it to 0 or 1. |
| `name` | omitted | Optional case-insensitive partial match on plan name. An empty value is ignored. |
| `include_deleted` | `false` | When false, soft-deleted plans are omitted. |

Order is `id` descending. The response is `items`, `total`, `page`, and `page_size`. `total` counts matches before pagination. A missing plan id, or a soft-deleted plan when deleted rows are excluded, is 404 `Plan not found`.

| HTTP | When |
| --- | --- |
| 409 | `Plan name already in use`. The check is the trimmed name, exact and case-sensitive, among plans that are not soft-deleted. |
| 422 | Empty name after trim (`Plan name is required`), a price outside 0 through 9999999999.99, a negative limit, or a status outside 0 or 1. |

Create writes audit `plan.create`. Update writes `plan.update`. Status writes `plan.status`. Each audit row uses `entity_type` `plan` and the plan id. Dashboard recent activities show those as **Plan created**, **Plan updated**, and **Plan status changed**. See [Commits and audit rows](#commits-and-audit-rows).

## School subscriptions

| Method | Path | Success |
| --- | --- | --- |
| POST | `/api/v1/super-admin/schools/{school_id}/subscriptions` | 201 |
| GET | `/api/v1/super-admin/schools/{school_id}/subscriptions` | 200 |
| GET | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}` | 200 |
| PATCH | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}` | 200 |
| PATCH | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/status` | 200 |

Subscription status: `0` inactive, `1` active, `2` expired, `3` cancelled.

### Assign body

```json
{
  "package_id": 3,
  "start_date": "2026-01-01",
  "end_date": "2026-06-30",
  "cycle": "monthly",
  "auto_renew": 1,
  "status": 1
}
```

`package_id` is required and at least 1. `cycle` is `monthly` or `yearly` and defaults to `monthly`. `auto_renew` is `0` or `1` and defaults to `1`. `status` defaults to `1` and must be 0 through 3. `end_date` must be on or after `start_date`.

The plan must have `status = 1` and `deleted_at` null. An inactive plan is 422 `Plan is not active`. A missing or soft-deleted plan is 404 `Plan not found`. A missing or soft-deleted school is 404 `School not found`.

If the new row is status `1`, the school row is locked for this transaction, then other non-deleted active subscriptions for that school are set to `3` in the same database commit. A second activation waits for that lock, then cancels the active row it finds, including one inserted by the transaction that just committed. Those cancelled rows do not get their own audit events. There is still no unique index, so active rows inserted outside this service can remain side by side.

### Subscription response

This is also the per-school list item. It does not include `school_name` or `plan_name`.

```json
{
  "id": 4,
  "school_id": 12,
  "package_id": 3,
  "status": 1,
  "start_date": "2026-01-01",
  "end_date": "2026-06-30",
  "cycle": "monthly",
  "auto_renew": 1,
  "agreed_price": 10.13,
  "deleted_at": null,
  "created_at": "2026-10-01T00:00:00",
  "updated_at": "2026-10-01T00:00:00"
}
```

### Per-school list

| Parameter | Default | Rules |
| --- | --- | --- |
| `page` | `1` | Integer, minimum 1. |
| `page_size` | `20` | Integer, 1 through 100. |
| `status` | omitted | Optional integer. The route does not restrict it to 0 through 3. |

Soft-deleted subscriptions are excluded. Order is `id` descending. The response is `items`, `total`, `page`, and `page_size`. A subscription that belongs to another school, or a soft-deleted subscription, is 404 `Subscription not found`.

`agreed_price` is the cent-rounded plan price for the subscription's cycle at assignment. It is a JSON number, or `null` when the row was stored before that snapshot existed. Editing the plan does not change it. Changing this subscription's `package_id` or `cycle` stores a new snapshot from the plan price after that change. Renewal does not change it. Renewal history and the renewal bill still use the plan price at renewal time, not `agreed_price`. A plan price outside 0 through 9999999999.99 is 422 `Plan price exceeds the supported amount` and does not create or rebind the subscription.

### Update body

Every field is optional. This route cannot change `school_id` or `status`.

```json
{
  "package_id": 3,
  "start_date": "2026-01-01",
  "end_date": "2026-06-30",
  "cycle": "monthly",
  "auto_renew": 1
}
```

A sent `package_id` must refer to a plan that is not soft-deleted. Unlike assignment, the plan does not have to be status `1`. The resulting `end_date` must still be on or after `start_date`.

### Status body

```json
{"status": 1}
```

`status` must be 0 through 3. Setting it to `1` locks the school row, then cancels other non-deleted active subscriptions for that school in the same commit, excluding this row. A competing activation waits on that lock. Those other rows are not given separate audit events.

Create writes `subscription.create` with metadata `package_id` and `status`. Update writes `subscription.update` with metadata `package_id`. Status writes `subscription.status` with metadata `status`. `entity_type` is `subscription`. Dashboard recent activities show create as **Subscription creation**, update as **Subscription updated**, and status as **Subscription status changed**. Update is not a renewal.

## Bills

| Method | Path | Success |
| --- | --- | --- |
| POST | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills` | 201 |
| GET | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills` | 200 |
| GET | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills/{bill_id}` | 200 |
| PATCH | `/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills/{bill_id}/status` | 200 |

Bill status: `0` pending, `1` paid, `2` overdue, `3` cancelled. Changing a bill status does not collect a payment.

### Create body

```json
{
  "period_start": "2026-01-01",
  "period_end": "2026-02-01",
  "amount": 10.0,
  "due_date": null,
  "description": null,
  "status": 0
}
```

`period_end` must be on or after `period_start`. `amount`, when sent, is rounded half up to cents and must be from 0 through 9999999999.99. The stored and returned amount is that rounded value, as a JSON number. When `amount` is omitted, the bill uses the subscription plan's monthly or yearly price for the subscription's `cycle`, quantized to cents. A stored plan price outside 0 through 9999999999.99 is 422 `Plan price exceeds the supported amount`. `status` defaults to `0` and must be 0 through 3. `description` is stored up to 255 characters.

If the subscription's plan is missing or soft-deleted, bill creation is 404 `Plan not found`.

Create writes no audit row.

### Bill response

```json
{
  "id": 8,
  "subscription_id": 4,
  "school_id": 12,
  "amount": 10.0,
  "status": 0,
  "period_start": "2026-01-01",
  "period_end": "2026-02-01",
  "due_date": null,
  "description": null,
  "deleted_at": null,
  "created_at": "2026-10-01T00:00:00",
  "updated_at": "2026-10-01T00:00:00"
}
```

`amount` is a JSON number from the float column. See [Amounts](#amounts).

### List and detail

List parameters are `page` (default 1, minimum 1), `page_size` (default 20, 1 through 100), and optional `status`. The list route does not restrict `status` to 0 through 3. Soft-deleted bills are excluded. Order is `id` descending. A bill for another subscription or school, or a soft-deleted bill, is 404 `Subscription bill not found`.

### Status body

```json
{"status": 1}
```

`status` must be 0 through 3. The audit action is `bill.status`, `entity_type` is `subscription_bill`, and metadata is `status` and `amount`. Dashboard recent activities show **Bill status changed**.

## Renewal

`POST /api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/renew`

There is no request body. The response is the subscription object above. The same subscription row and id are kept. Status stays `1`. `cycle`, `package_id`, and `auto_renew` are unchanged. `auto_renew` is only a stored flag. This route does not read it.

### Accepted subscription status

Only status `1` can be renewed.

| Status | Meaning | Renewal |
| --- | --- | --- |
| 0 | inactive | 422 `Only an active subscription can be renewed` |
| 1 | active | allowed, including when `end_date` is already before today |
| 2 | expired | 422 `Only an active subscription can be renewed` |
| 3 | cancelled | 422 `Only an active subscription can be renewed` |

A soft-deleted subscription, a subscription that belongs to another school, or a missing id returns 404 `Subscription not found`. A missing or soft-deleted school returns 404 `School not found`.

### Plan requirement

The subscription's current plan must have `status = 1` and `deleted_at` null.

- Inactive plan: 422 `Plan is not active`. The subscription is not changed.
- Soft-deleted plan: 404 `Plan not found`.

A stored `cycle` other than `monthly` or `yearly` is 422 `cycle must be monthly or yearly`.

### Renewal dates

Today is the naive UTC calendar date, the same clock used for stored timestamps. Local time is not used.

- If `end_date` is today or later, the new period starts the day after `end_date`. Time remaining until the current `end_date` is kept.
- If `end_date` is before today, the new period starts today.
- `monthly` adds one calendar month to the new start. Day 31 clamps to the last day of the target month. 31 January 2026 renews through 28 February 2026.
- `yearly` adds one calendar year. 29 February 2024 renews through 28 February 2025.
- `end_date` is inclusive.

Examples, with today 15 October 2026:

| Current `end_date` | Cycle | New `start_date` | New `end_date` |
| --- | --- | --- | --- |
| 31 December 2026 | monthly | 1 January 2027 | 1 February 2027 |
| 15 June 2099 | yearly | 16 June 2099 | 16 June 2100 |
| 15 January 2026 | monthly | 15 October 2026 | 15 November 2026 |
| 30 January 2026, if today is 31 January 2026 | monthly | 31 January 2026 | 28 February 2026 |
| 28 February 2024, if today is 29 February 2024 | yearly | 29 February 2024 | 28 February 2025 |

### History and pending bill

One successful renewal writes:

- one `subscription_renewals` row with the plan name, cycle, and amount taken at renewal time
- one pending bill (`status = 0`) for the same period, description `Subscription renewal`, `due_date` null

Monthly uses `packages.monthly_price`. Yearly uses `packages.yearly_price`. The history amount is `numeric(12,2)`. The bill column is a float. Both values come from that same cent-rounded amount. Later edits to the plan name or price do not change the history row or that bill.

The subscription date change, history insert, and bill insert stay uncommitted until the audit write. `record_audit` commits that transaction, including `subscription.renew`. If the audit insert or its commit fails, the route rolls the transaction back and returns 500 `Renewal could not be recorded`. Nothing from that renewal is saved, and no `subscription.renew` row is left. `record_audit` refreshes the audit row after the commit. A failure at that refresh cannot undo the commit.

Repeating the same `(subscription_id, period_start)` returns 409 `This subscription period has already been renewed`. A second request that arrives while the subscription row is locked returns 409 `A renewal for this subscription is already in progress`.

A stored price outside 0 through 9999999999.99 is 422 `Plan price exceeds the supported amount` and does not change the subscription.

After a successful renewal the audit row is:

- `action`: `subscription.renew`
- `entity_type`: `subscription`
- `entity_id`: the existing subscription id
- `school_id`: the school id
- metadata: `package_id`, `cycle`, `start_date`, `end_date`, `status`

Dashboard recent activities show that action as **Subscription renewed**.

Older subscriptions are not given a fabricated history row.

### Read history

`GET /api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/renewals`

Super Admin only. There is no request body. `page` defaults to 1 and must be at least 1. `page_size` defaults to 20 and must be 1 through 100. Order is `id` descending. The envelope is `items`, `total`, `page`, and `page_size`.

Each item is the stored snapshot: `id`, `subscription_id`, `school_id`, `package_id`, `plan_name`, `cycle`, `amount`, `period_start`, `period_end`, and `created_at`. `amount` is a JSON number. Renewal rows are not soft-deleted. A missing or soft-deleted school, a missing or soft-deleted subscription, or a subscription that belongs to another school is 404 `Subscription not found`. An existing subscription with no renewals is 200 and `items` is empty. This route does not write an audit row.

| HTTP | When |
| --- | --- |
| 404 | School, subscription, or plan is missing or soft-deleted, or the subscription is not for that school. |
| 409 | That period was already renewed, or another renewal holds the subscription row. |
| 422 | Subscription status is not active, the plan is inactive, the stored cycle is not `monthly` or `yearly`, or the plan price is outside 0 through 9999999999.99. |
| 500 | The renewal and its audit row could not be committed together. A failure before that commit saves nothing. |

## Expiry

`POST /api/v1/super-admin/subscriptions/expire-due`

There is no request body. The response is the count of rows changed by this call:

```json
{"expired": 2}
```

A subscription is expired only when all of these are true:

- `status` is `1` (active)
- `deleted_at` is null
- `end_date` is before today's naive UTC calendar date

`end_date` equal to today stays active. Statuses `0`, `2`, and `3` are not changed. Soft-deleted rows are not changed. `schools.status` and `schools.installed` are not changed. No school or subscription row is deleted.

The update is one SQL statement. A repeated call returns `{"expired": 0}` for subscriptions already expired. Concurrent calls lock the updated rows, so the same row is counted by only one call.

When the count is greater than zero, one audit row is committed in the same transaction:

- `action`: `subscription.expire`
- `entity_type`: `subscription`
- `entity_id`: null
- `school_id`: null
- metadata: `{"expired": <count>}`

Dashboard recent activities show that action as **Subscriptions expired**. A run that expires nothing commits that no-op update and does not write an audit row. If the update or the audit commit fails, the route rolls the transaction back and returns 500 `Subscriptions could not be expired`. No status change from that call is saved. A failure after the audit commit, during the audit row refresh, cannot undo that commit.

No scheduler is running. Celery, Redis, and an in-process worker are not configured. Automatic expiry starts only after an external cron or scheduler is deployed to call this endpoint. Until then, subscriptions remain active past `end_date` unless a Super Admin calls it.

| HTTP | When |
| --- | --- |
| 500 | The expiry update could not be committed. A failure before that commit saves no status change from that call. |

## Platform listing

`GET /api/v1/super-admin/subscriptions`

This is a read. It does not change subscription status, school activation, renewal history, or plan prices, and it does not write an audit row.

The per-school list above is a different route. Dashboard `GET /api/v1/super-admin/dashboard/subscriptions` is the distribution chart, not this list.

### Query parameters

| Parameter | Default | Rules |
| --- | --- | --- |
| `page` | `1` | Integer, minimum 1. |
| `page_size` | `20` | Integer, 1 through 100. |
| `q` | omitted | Optional. Case-insensitive partial match on school name only. Blank is ignored. |
| `status` | omitted | Optional subscription status `0`, `1`, `2`, or `3`. |
| `package_id` | omitted | Optional plan id, minimum 1. |
| `school_id` | omitted | Optional school id, minimum 1. |
| `sort` | `end_date` | `end_date`, `-end_date`, `created_at`, or `-created_at`. |

Filters and search run before pagination. A leading `-` sorts that date descending. Subscription `id` is the tie-breaker, ascending when the date sort is ascending and descending when the date sort is descending.

`subscriptions.end_date` is required, so expiry sorting has no nulls. `created_at` may be null. Null `created_at` values sort last for both `created_at` and `-created_at`.

Soft-deleted subscriptions are excluded. Subscriptions whose school is soft-deleted are excluded. A soft-deleted plan is still listed, and `plan_name` is that plan's name, which may be null.

### Response

```json
{
  "items": [
    {
      "id": 9,
      "school_id": 4,
      "package_id": 2,
      "status": 1,
      "start_date": "2026-01-01",
      "end_date": "2026-06-30",
      "cycle": "monthly",
      "auto_renew": 1,
      "deleted_at": null,
      "created_at": "2026-01-01T00:00:00",
      "updated_at": "2026-01-01T00:00:00",
      "school_name": "North High",
      "plan_name": "Standard"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`total` is the number of matching rows, not the page length. An empty match is `{"items": [], "total": 0, "page": 1, "page_size": 20}`.

### Examples

Soonest expiry first, active subscriptions whose school name contains `north`:

`GET /api/v1/super-admin/subscriptions?q=north&status=1&sort=end_date&page=1&page_size=20`

Newest created first for one plan:

`GET /api/v1/super-admin/subscriptions?package_id=2&sort=-created_at`

| HTTP | When |
| --- | --- |
| 422 | `page`, `page_size`, `status`, `package_id`, `school_id`, or `sort` is outside the rules above. |

## Amounts

`packages.monthly_price`, `packages.yearly_price`, and `subscription_bills.amount` are floats. `subscription_renewals.amount` is `numeric(12,2)`.

Renewal rounds the selected plan price half up to cents. That rounded value is stored on the history row. The pending renewal bill stores `float` of the same rounded value. A plan create or update, and a manual bill amount, store the same half-up cent rounding. Values that round above 9999999999.99 are rejected. Responses stay JSON numbers.

`subscriptions.agreed_price` is `numeric(12,2)` and nullable. Rows that existed before that column stay `null`. Plan prices and bill amounts stay floats. No column type change in this document converts those floats.

## Plan features

Plan feature permissions are not implemented. `ROLE_FEATURES` in `app/api/student_reads.py` is a staff-role menu for `GET /api/staff/features-permission`. It is not a plan catalog. `app/models/catalog.py` names legacy tables `features`, `package_features`, and `subscription_features`, and this backend has no model or allowlist for them.

A later phase needs a product decision before any schema is added: the allowlist of plan feature identifiers, whether those identifiers are separate from the staff-role menu, and whether a school's effective permissions are the plan's features, the staff role's features, or both.

## Expiry operations

`POST /api/v1/super-admin/subscriptions/expire-due` is the only expiry operation. The application lifespan does not start a scheduler. Requirements do not include Celery, Redis, or APScheduler. Render can run more than one worker, so an in-process scheduler is not used.

Automatic expiry is not operational until an operator schedules an external job that sends an authenticated Super Admin `POST` to that path. The job must not delete school rows. Repeating it is safe: a row already set to status `2` no longer matches. Two overlapping calls update each due row once. Until that job exists, a past `end_date` stays status `1`.

## Subscription access

`require_school_admin` checks the School Admin role, the user status, and the school's `status` and `installed` values. `subscription_expiry_blocks_access` in `app/services/v1/subscription_access.py` is called only after those school checks pass. It currently returns false for every school and does not read subscription rows. Expired, cancelled, and inactive subscriptions do not block School Admin, Super Admin, public `POST /api/v1/schools/register`, or legacy `/api/student`, `/api/staff`, and `/api/admin` routes.

The unresolved decision is which subscription statuses, if any, should block which of those route groups. School activation stays independent of that decision. No school row is deleted when a subscription expires.

## Commits and audit rows

`record_audit` adds the audit row. By default it commits the current session, then refreshes that row. `commit=False` only flushes the row. A refresh failure after a successful commit does not undo that commit.

Plan create, plan update, plan status, subscription create, subscription update, subscription status, and bill status leave the business change uncommitted. The matching audit write commits both. A failure before that commit rolls both back. The response is 500 `Plan could not be recorded`, `Subscription could not be recorded`, or `Bill status could not be recorded`. The response does not include the internal error.

Renewal, and expiry when at least one row changes, use the same single commit. A failure before that commit rolls both back. A failure after that commit, during the refresh, leaves the committed rows in place.

Bill create commits the bill and writes no audit row. Expiry of zero rows commits that no-op update and writes no audit row. Other Super Admin routes still use the default audit commit and are not part of this subscription transaction.

Cancelling the school's other active subscriptions, when assignment or a status change creates a new active row, is part of that same commit. Those cancelled rows do not get their own audit events. If the commit fails, those cancellations are rolled back too.
