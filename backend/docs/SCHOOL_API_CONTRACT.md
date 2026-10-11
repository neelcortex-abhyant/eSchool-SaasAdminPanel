# School API contract

For frontend integration of the existing Super Admin school APIs. These routes already exist. Do not add a second `/api/v1/schools` client.

Base path: `/api/v1/super-admin/schools`

Auth: `Authorization: Bearer <opaque session token>`

Only a user with server-side `role=super_admin` may call these routes. A School Admin, a normal user, or a missing token cannot. The client cannot set `role` or school ownership in the body. Unknown JSON fields are rejected.

All JSON examples below are fictional mocks. They are not production records and contain no credentials.

## School id and school code

| Value | Meaning |
|---|---|
| `id` | Integer primary key. Use this in profile, edit, status, and delete URLs. |
| `code` | Unique school code string used by school-code login. Optional on create; the server generates one when omitted. List filter `code` is an exact match after the server uppercases it and strips characters other than letters, digits, `_`, and `-`. |

`database_name` in responses is legacy metadata. The UI should not treat it as a connection string.

## Logo

`logo` is a string of at most 255 characters. The API does not accept a file upload on these routes. Send a URL or a stored filename, or `""` when there is no logo.

## Create school

`POST /api/v1/super-admin/schools`

Status on success: `201`

The server always stores `status=1` and `installed=1`. Do not send `status`, `id`, `role`, or `school_id`.

| Field | Required | Rule |
|---|---|---|
| `name` | Yes | 1–255 characters |
| `address` | No | String, max 255. Default `""` |
| `support_phone` | No | String, max 255. No phone-format check. Default `""` |
| `support_email` | No | Blank is allowed. A non-blank value must be a valid email and must not match another school's email, ignoring case. Max 255 |
| `tagline` | No | String, max 255. Default `""` |
| `logo` | No | String, max 255. Default `""` |
| `code` | No | Unique. Normalized by the server. Generated when omitted |
| `domain` | No | String, max 255 |

Mock request:

```json
{
  "name": "Green Valley School",
  "address": "12 Lake Road",
  "support_phone": "9876543210",
  "support_email": "office@greenvalley.example",
  "tagline": "Learn well",
  "logo": "https://cdn.example.com/schools/green-valley.png",
  "code": "GVS01",
  "domain": "greenvalley.example"
}
```

Mock response (`201`):

```json
{
  "id": 41,
  "name": "Green Valley School",
  "address": "12 Lake Road",
  "support_phone": "9876543210",
  "support_email": "office@greenvalley.example",
  "tagline": "Learn well",
  "logo": "https://cdn.example.com/schools/green-valley.png",
  "admin_id": null,
  "v1_admin_id": null,
  "status": 1,
  "code": "GVS01",
  "database_name": null,
  "domain": "greenvalley.example",
  "installed": 1,
  "provisioned_at": null,
  "deleted_at": null,
  "created_at": "2026-10-09T12:00:00",
  "updated_at": "2026-10-09T12:00:00"
}
```

## School profile

`GET /api/v1/super-admin/schools/{school_id}`

`school_id` is the integer `id`. Success is `200` with the same `SchoolResponse` object as create. A missing or soft-deleted school is `404`.

## Edit school

`PATCH /api/v1/super-admin/schools/{school_id}`

Send only the fields that change. Omitted fields stay as they are. This route does not change `status` or `installed`.

| Field | Rule |
|---|---|
| `name` | 1–255 characters when sent |
| `address`, `support_phone`, `tagline`, `logo`, `domain` | Max 255. `domain` blank becomes `null` |
| `support_email` | Omit to keep the current email. `""` clears it. A non-blank value must be valid and unique among non-blank emails |
| `code` | Must stay unique |

Mock request:

```json
{
  "name": "Green Valley Public School",
  "support_phone": "5550001",
  "logo": "https://cdn.example.com/schools/green-valley-v2.png"
}
```

Mock response: `200` and the full school object, with those three fields updated and `status` still `1`.

## School listing

`GET /api/v1/super-admin/schools`

| Query | Default | Behavior |
|---|---|---|
| `page` | `1` | Page number, minimum 1 |
| `page_size` | `20` | 1–100 |
| `name` | omitted | Case-insensitive partial match |
| `code` | omitted | Exact match after code normalization |
| `support_email` | omitted | Case-insensitive partial match |
| `status` | omitted | `1` active or `0` inactive. Omit to include both. Any other value returns 422 |
| `sort` | omitted | `name`, `-name`, `created_at` (oldest first), or `-created_at` (newest first). When omitted, schools are ordered by `id` descending. `id` is always the tie-breaker, in the same direction as the chosen sort |
| `include_deleted` | `false` | `true` includes soft-deleted schools |

`created_at` may be null on older rows. Null timestamps sort last for both `created_at` and `-created_at`. Filters combine. Soft-deleted schools are hidden unless `include_deleted=true`. Pagination uses the same filters and sort for every page.

Examples:

```http
GET /api/v1/super-admin/schools?page=1&page_size=20
GET /api/v1/super-admin/schools?name=valley
GET /api/v1/super-admin/schools?code=gvs01
GET /api/v1/super-admin/schools?support_email=office@green
GET /api/v1/super-admin/schools?status=0&page=1&page_size=20
GET /api/v1/super-admin/schools?sort=name
GET /api/v1/super-admin/schools?sort=-created_at&status=1
```

Mock response (`200`):

```json
{
  "items": [
    {
      "id": 41,
      "name": "Green Valley School",
      "address": "12 Lake Road",
      "support_phone": "9876543210",
      "support_email": "office@greenvalley.example",
      "tagline": "Learn well",
      "logo": "https://cdn.example.com/schools/green-valley.png",
      "admin_id": null,
      "v1_admin_id": null,
      "status": 1,
      "code": "GVS01",
      "database_name": null,
      "domain": "greenvalley.example",
      "installed": 1,
      "provisioned_at": null,
      "deleted_at": null,
      "created_at": "2026-10-09T12:00:00",
      "updated_at": "2026-10-09T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

Use `total`, `page`, and `page_size` for the pager. `items` is only the current page.

## Status and delete

These return the full school object. They do not take a JSON body.

| Method | Path | Result |
|---|---|---|
| POST | `/api/v1/super-admin/schools/{school_id}/activate` | `status=1`, `installed=1` |
| POST | `/api/v1/super-admin/schools/{school_id}/suspend` | `status=0`. `installed` stays as it was |
| POST | `/api/v1/super-admin/schools/{school_id}/deactivate` | `status=0`, `installed=0` |
| DELETE | `/api/v1/super-admin/schools/{school_id}` | Sets `deleted_at`. The row remains. Later GET and the normal list hide it |

`status` for the list filter and badges: `1` active, `0` inactive. `installed` is separate. Suspend leaves `installed` at its previous value. Deactivate sets it to `0`.

Each successful activate, suspend, and deactivate writes one Super Admin audit record. The action is `school.activate`, `school.suspend`, or `school.deactivate`. Metadata contains `previous_status`, `previous_installed`, `status`, and `installed`. The actor is the authenticated Super Admin, and `school_id` is the school in the URL. A failed status change, such as an unknown school, does not write that success record.

`GET /api/v1/super-admin/audit-logs` lists those rows for a Super Admin. Query parameters are `page` (default 1), `page_size` (default 20, maximum 100), `action`, `entity_type`, `school_id`, and `actor_id`. `entity_id` is a string. `metadata` is the stored object.

Mock response (`200`) after suspending school `41`:

```json
{
  "items": [
    {
      "id": 12,
      "actor_id": "11111111-1111-1111-1111-111111111111",
      "actor_email": "platform@greenvalley.example",
      "action": "school.suspend",
      "entity_type": "school",
      "entity_id": "41",
      "school_id": 41,
      "metadata": {
        "previous_status": 1,
        "previous_installed": 1,
        "status": 0,
        "installed": 1
      },
      "created_at": "2026-10-09T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

## Errors

Service errors use a string `detail`. Validation errors use a list.

| Status | When | Mock body |
|---|---|---|
| 401 | No token, invalid token, expired token, or revoked token | `{"detail":"Not authenticated"}` |
| 403 | Signed-in user is not `super_admin` | `{"detail":"Forbidden"}` |
| 404 | Unknown or soft-deleted school id | `{"detail":"School not found"}` |
| 409 | Duplicate school code | `{"detail":"School code already in use"}` |
| 409 | Duplicate non-blank email, ignoring case | `{"detail":"School email already in use"}` |
| 422 | Invalid body, empty name, invalid email, an unknown field, or `status` other than `0` or `1` | Validation list, see below |
| 422 | Unknown `sort`, such as `updated_at` | `{"detail":"Invalid sort"}` |

Mock `422` for an invalid email:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "support_email"],
      "msg": "Value error, Invalid support email",
      "input": "not-an-email"
    }
  ]
}
```

Mock `422` for `GET /api/v1/super-admin/schools?sort=updated_at`:

```json
{"detail":"Invalid sort"}
```

Blank emails are allowed and are not unique. Several schools may have `support_email` equal to `""`.

## Authorization the UI should expect

- Super Admin school screens call the routes above.
- School Admin screens must not call them. A School Admin reads only `GET /api/v1/school-admin/me`, `GET /api/v1/school-admin/school`, and `GET /api/v1/school-admin/schools/{school_id}` when that id is their own server-side school. Another school's id returns `403` with `{"detail":"Forbidden"}`.
- Those School Admin routes also return `403` with `{"detail":"School access is suspended"}` when the admin's own school is suspended (`status=0`), deactivated (`status=0`, `installed=0`), or not installed. `installed` must be `1`, so `status=1` with `installed=0` is denied as well. A missing or soft-deleted school is denied the same way. Reactivating the school with `POST /api/v1/super-admin/schools/{school_id}/activate` sets `status=1` and `installed=1` and restores access for a still-valid School Admin session. Super Admin school routes stay available while the school is suspended or deactivated.

## OpenAPI

Local OpenAPI at `http://127.0.0.1:8000/openapi.json` includes `support_email` on the list query and the create/update email descriptions. That check is against the local app, not production. `/docs` is available when `APP_DEBUG` is true.
