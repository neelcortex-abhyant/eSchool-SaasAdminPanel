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
| `status` | omitted | Exact integer match. `1` active, `0` inactive |
| `include_deleted` | `false` | `true` includes soft-deleted schools |

Filters combine. Soft-deleted schools are hidden unless `include_deleted=true`.

Examples:

```http
GET /api/v1/super-admin/schools?page=1&page_size=20
GET /api/v1/super-admin/schools?name=valley
GET /api/v1/super-admin/schools?code=gvs01
GET /api/v1/super-admin/schools?support_email=office@green
GET /api/v1/super-admin/schools?status=0&page=1&page_size=20
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

## Errors

Service errors use a string `detail`. Validation errors use a list.

| Status | When | Mock body |
|---|---|---|
| 401 | No token, invalid token, expired token, or revoked token | `{"detail":"Not authenticated"}` |
| 403 | Signed-in user is not `super_admin` | `{"detail":"Forbidden"}` |
| 404 | Unknown or soft-deleted school id | `{"detail":"School not found"}` |
| 409 | Duplicate school code | `{"detail":"School code already in use"}` |
| 409 | Duplicate non-blank email, ignoring case | `{"detail":"School email already in use"}` |
| 422 | Invalid body, empty name, invalid email, or an unknown field | See below |

Mock `422`:

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

Blank emails are allowed and are not unique. Several schools may have `support_email` equal to `""`.

## Authorization the UI should expect

- Super Admin school screens call the routes above.
- School Admin screens must not call them. A School Admin reads only `GET /api/v1/school-admin/school` and `GET /api/v1/school-admin/schools/{school_id}` when that id is their own server-side school. Another school's id returns `403`.

## OpenAPI

Local OpenAPI at `http://127.0.0.1:8001/openapi.json` includes `support_email` on the list query and the create/update email descriptions. That check was against the local app, not production. `/docs` is available when `APP_DEBUG` is true.
