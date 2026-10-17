# Super Admin dashboard API

Base path: `/api/v1/super-admin/dashboard`

Auth: `Authorization: Bearer <opaque session token>`

Every route below uses `require_super_admin` and the central database session. A missing or invalid token returns HTTP 401. An authenticated user who is not a Super Admin returns HTTP 403 with `{"detail":"Forbidden"}`. Responses are the JSON object itself. There is no `success` or `data` wrapper.

All JSON examples below are fictional mocks. They are not production records and contain no credentials.

## Shared rules

- Soft-deleted schools have `schools.deleted_at` set. They are excluded from school counts, recent schools, registration months, school status, and subscription distribution.
- School `status` `1` is active. School `status` `0` is inactive. Suspended schools (`status=0`, `installed=1`) and deactivated schools (`status=0`, `installed=0`) are both inactive. This contract does not add a separate pending or deactivated chart category.
- A qualifying active subscription has `subscriptions.status = 1` and `subscriptions.deleted_at IS NULL`. `end_date` does not change that rule.
- Timestamps stored by this application are naive UTC.
- These routes do not return email, phone, address, database name, actor email, actor id, raw audit metadata, tokens, or bill amounts.

## Existing platform dashboard

`GET /api/v1/super-admin/dashboard`

No query parameters. This response is unchanged. It returns platform totals, including legacy keys `schools`, `schools_active`, `packages`, `packages_active`, and `super_admins`, plus later keys such as `schools_inactive`, `schools_deactivated`, `students`, subscription status totals, add-on counts, and bill totals.

`subscriptions_active` counts qualifying subscription rows. It includes duplicate rows and rows whose school was later soft-deleted. `students` counts student rows with `deleted_at IS NULL` and does not also require the school to be non-deleted. `schools_deactivated` is the subset of non-deleted schools with `status=0` and `installed=0`. `unavailable_metrics` lists `payment_gateway_revenue` and `payment_transactions`. Those are not collected here.

## Statistics

`GET /api/v1/super-admin/dashboard/stats`

No query parameters.

```json
{
  "total_schools": 2,
  "active_schools": 1,
  "inactive_schools": 1,
  "total_students": 1,
  "total_teachers": 1,
  "active_subscriptions": 1
}
```

| Field | Rule |
|---|---|
| `total_schools` | `schools.deleted_at IS NULL` |
| `active_schools` | non-deleted and `status = 1` |
| `inactive_schools` | non-deleted and `status = 0` |
| `total_students` | `students.deleted_at IS NULL` and the student's school is non-deleted |
| `total_teachers` | distinct legacy users with the Teacher role, `users.deleted_at IS NULL`, and `users.school_id` pointing at a non-deleted school |
| `active_subscriptions` | qualifying subscription rows, including duplicates and rows on soft-deleted schools |

`active_schools` and `inactive_schools` match `GET /dashboard/school-status` for the same database state. `total_students` is narrower than `GET /dashboard` `students`, which does not drop students of a deleted school. `active_subscriptions` matches `GET /dashboard` `subscriptions_active`: both count rows, not distinct schools.

An empty database returns zeros. A Super Admin account does not increment these six fields.

## Recent schools

`GET /api/v1/super-admin/dashboard/recent-schools?limit=10`

`limit` defaults to 10 and must be an integer from 1 through 50. Any other value returns HTTP 422.

Schools are ordered by `created_at DESC NULLS LAST`, then `id DESC`. The response includes `limit`.

```json
{
  "items": [
    {
      "id": 41,
      "name": "Green Valley School",
      "code": "GVS01",
      "created_at": "2026-10-09T12:00:00",
      "status": 1,
      "installed": 1,
      "package_id": null,
      "plan_name": null
    }
  ],
  "limit": 10
}
```

`package_id` and `plan_name` are set only when that school has exactly one qualifying active subscription. Zero or more than one qualifying row makes both fields null. A past `end_date` does not remove a `status = 1` row. A soft-deleted package can still supply `plan_name` when it is the only qualifying subscription. A null package name is returned as `plan_name: null`.

## Registration analytics

`GET /api/v1/super-admin/dashboard/registrations?year=2026`

`year` is required and must be an integer from 2000 through 2100. A missing or invalid year returns HTTP 422.

Months use the naive-UTC calendar. The window is inclusive of `year-01-01 00:00:00` and exclusive of the next year's `01-01 00:00:00`. All 12 months are returned in order. `total` is the sum of those 12 counts. Non-deleted schools with null `created_at` are counted in `unscheduled` for every requested year and are not included in `total`.

```json
{
  "year": 2026,
  "total": 0,
  "unscheduled": 0,
  "months": [
    {"month": 1, "count": 0},
    {"month": 2, "count": 0},
    {"month": 3, "count": 0},
    {"month": 4, "count": 0},
    {"month": 5, "count": 0},
    {"month": 6, "count": 0},
    {"month": 7, "count": 0},
    {"month": 8, "count": 0},
    {"month": 9, "count": 0},
    {"month": 10, "count": 0},
    {"month": 11, "count": 0},
    {"month": 12, "count": 0}
  ]
}
```

## School status

`GET /api/v1/super-admin/dashboard/school-status`

No query parameters. Only two counts, for charts:

```json
{
  "active_schools": 1,
  "inactive_schools": 1
}
```

`active_schools` is non-deleted and `status = 1`. `inactive_schools` is non-deleted and `status = 0`. A non-deleted school whose status is neither 0 nor 1 is in neither count. Deleted schools are in neither count. These two numbers match the Stats API.

## Subscription distribution

`GET /api/v1/super-admin/dashboard/subscriptions`

No query parameters.

```json
{
  "by_plan": [
    {
      "package_id": 1,
      "plan_name": "Basic",
      "school_count": 2
    }
  ],
  "schools_with_active_subscription": 2,
  "schools_without_active_subscription": 1
}
```

`by_plan` is one row per package, ordered by `package_id`. `school_count` is the number of distinct non-deleted schools with a qualifying subscription on that package. Duplicate qualifying rows for the same school and plan count once. A school with qualifying subscriptions on two plans appears in both plan rows and once in `schools_with_active_subscription`, so the sum of `school_count` can be larger than `schools_with_active_subscription`.

`schools_without_active_subscription` is the number of non-deleted schools with no qualifying subscription. Soft-deleted schools are in neither total. An inactive, expired, cancelled, or soft-deleted subscription does not qualify. A past `end_date` on a `status = 1` row still qualifies.

A null package name is `plan_name: null`. A soft-deleted package still appears when a qualifying subscription points at it, because the package row and the subscription remain.

This is not the Stats API count. `GET /dashboard/stats` `active_subscriptions` counts qualifying rows, including duplicates and rows on soft-deleted schools. This route counts distinct non-deleted schools. Empty data returns `by_plan: []` and both school totals `0`.

No payment, revenue, or renewal fields are returned.

## Recent activities

`GET /api/v1/super-admin/dashboard/recent-activities?limit=10`

`limit` defaults to 10 and must be an integer from 1 through 50. Any other value returns HTTP 422. The response body does not repeat `limit`.

Rows come from `audit_logs`, ordered by `id` descending. That is the same order as `GET /api/v1/super-admin/audit-logs`. The query selects only `id`, `action`, `entity_type`, `entity_id`, `school_id`, and `created_at`. Titles and descriptions are fixed text for known actions. Unknown actions return title `Activity recorded` and description `An activity was recorded.`

```json
{
  "items": [
    {
      "id": 12,
      "action": "school.activate",
      "entity_type": "school",
      "entity_id": "41",
      "school_id": 41,
      "created_at": "2026-10-13T12:00:00",
      "title": "School activation",
      "description": "A school was activated."
    }
  ]
}
```

Known dashboard titles include `school.register` ("New school registration"), `school.activate` ("School activation"), `school.deactivate` ("School deactivation"), and `subscription.create` ("Subscription creation"). `subscription.update` is "Subscription updated". It is not a renewal. `subscription.renew` is "Subscription renewed". `subscription.expire` is "Subscriptions expired".

`subscriptions.auto_renew` is only a stored flag. This route shows a renewal when an audit row has action `subscription.renew`, and an expiry batch when an audit row has action `subscription.expire`. It does not invent those rows.

An empty audit log returns `{"items": []}`.

## Known limitations

- A renewal appears in recent activities only after `subscription.renew` is written. `subscription.update` is still not a renewal.
- Stats `active_subscriptions` and subscription-distribution school counts answer different questions and are not required to be equal.
- Stats `total_students` excludes students of soft-deleted schools. The original dashboard `students` field does not.
- School status does not separate suspended schools from deactivated schools.
- Registration `unscheduled` is not limited to the requested year.
- Recent activities follow audit-log id order. `created_at` is not the sort key.
