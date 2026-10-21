# School Admin management, roles and password recovery — API contract

For frontend integration of the Super Admin Panel (School Admin users) and the admin login pages. All routes below are live in the backend. They extend the existing v1 routes; there is no `/api/v1/admin/...` prefix, so do not build a client for one.

All JSON examples are fictional mocks. They are not production records and contain no credentials.

## Contents

1. [Conventions](#conventions)
2. [Differences from the task brief](#differences-from-the-task-brief)
3. [Endpoint list](#endpoint-list)
4. [Roles and permissions](#roles-and-permissions)
5. [School Admin object](#school-admin-object)
6. [Create a School Admin](#create-a-school-admin)
7. [List School Admins](#list-school-admins)
8. [Get, edit, status, roles, invite](#get-edit-status-roles-invite)
9. [Forgot and reset password](#forgot-and-reset-password)
10. [School Admin access rules](#school-admin-access-rules)
11. [Errors and status codes](#errors-and-status-codes)
12. [Limitations](#limitations)

## Conventions

| Topic | Rule |
|---|---|
| Base URL | `/api/v1` |
| Auth | `Authorization: Bearer <access_token>` from `POST /api/v1/super-admin/login` (Super Admin) or `POST /api/v1/auth/login` (any role). The token is opaque; do not decode it. |
| Who may call `/super-admin/...` | Only `role=super_admin`. A School Admin or plain user gets `403`. |
| Success body | The object itself. No `{success, data}` wrapper. |
| Lists | `{"items": [...], "total": 0, "page": 1, "page_size": 20}` |
| Errors | `{"detail": "message"}`. FastAPI validation errors use `{"detail": [ ... ]}` (see [Errors](#errors-and-status-codes)). |
| Unknown JSON fields | Rejected with `422` on every request body. Never send `role`, `school_id` or `id` in bodies. |
| School Admin `id` | UUID string |
| School `id` | Integer |
| Dates | ISO 8601 in UTC, e.g. `2026-10-16T10:00:00Z` |
| Account `status` | Integer: `1` active, `0` inactive |

## Differences from the task brief

The brief's proposed shapes were illustrative. The backend follows the existing v1 conventions instead:

| Brief | Backend | Why |
|---|---|---|
| `/api/v1/admin/school-admins...` | `/api/v1/super-admin/schools/{school_id}/admins...` plus `/api/v1/super-admin/school-admins` for the cross-school list | These routes already existed. No duplicate API. |
| `/api/v1/admin/roles`, `/permissions` | `/api/v1/super-admin/roles`, `/permissions` | Same `super-admin` prefix |
| `{"success": true, "data": {...}}` | Plain object | Matches every other v1 route |
| `name` | `first_name` + `last_name` | Existing user fields. Display as `first_name + " " + last_name`. |
| `phone` | `mobile` | Existing field name |
| `"status": "active"` | `"status": 1` | Existing convention (`1`/`0`) |
| `"id": "usr_001"`, `"school_id": "sch_001"` | UUID and integer | Real key types |
| `role` (single) | `role` is always `"school_admin"` (platform role); `roles` lists the admin roles | See [Roles](#roles-and-permissions) |

## Endpoint list

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/super-admin/schools/{school_id}/admins` | Create a School Admin (password or invitation) | Super Admin |
| GET | `/super-admin/schools/{school_id}/admins` | List one school's admins | Super Admin |
| GET | `/super-admin/school-admins` | List admins across all schools (`school_id` filter) | Super Admin |
| GET | `/super-admin/schools/{school_id}/admins/{admin_id}` | Admin profile | Super Admin |
| PATCH | `/super-admin/schools/{school_id}/admins/{admin_id}` | Edit name, mobile, password | Super Admin |
| PATCH | `/super-admin/schools/{school_id}/admins/{admin_id}/status` | Activate / deactivate | Super Admin |
| PATCH | `/super-admin/schools/{school_id}/admins/{admin_id}/roles` | Replace the admin's roles | Super Admin |
| POST | `/super-admin/schools/{school_id}/admins/{admin_id}/invite` | Re-send the password-setup email | Super Admin |
| GET | `/super-admin/roles` | Role catalog with permissions | Super Admin |
| GET | `/super-admin/permissions` | Permission catalog | Super Admin |
| POST | `/auth/forgot-password` | Request a reset email | Public |
| POST | `/auth/reset-password` | Set a password from a reset or invitation link | Public |

Existing auth routes, unchanged in shape: `POST /auth/login`, `POST /super-admin/login`, `POST /auth/logout` (`204`), `GET /auth/me`, `POST /auth/change-password`. Login routes are now rate limited (see [Limitations](#limitations)).

## Roles and permissions

Every School Admin has the platform role `role: "school_admin"`. On top of that, `roles` holds one or more **admin roles**, which decide the modules the admin can use. An admin created without `roles` gets `school_admin` (full access). Super Admin is never an admin role and cannot be assigned.

### Roles

| Key | Label | Permissions |
|---|---|---|
| `school_admin` | School Admin | All nine permissions |
| `academic_admin` | Academic Admin | `dashboard.view`, `students.manage`, `teachers.manage`, `exams.manage`, `attendance.manage`, `reports.view` |
| `accounts_admin` | Accounts Admin | `dashboard.view`, `fees.manage`, `reports.view` |

An admin with several roles gets the union of their permissions.

### Permissions

| Key | Label | What it unlocks in the backend |
|---|---|---|
| `dashboard.view` | Dashboard | Academics summary, own profile, own school, session years. Read-only academic structure (classes, sections, subjects, mediums, sessions, class-sections, class-subjects). |
| `school.manage` | School Management | Create/edit/delete academic structure; session activate; notices |
| `students.manage` | Student Management | Students, parents |
| `teachers.manage` | Teacher Management | Teachers, leaves, teacher-assignments |
| `fees.manage` | Fees | Fees, expenses |
| `exams.manage` | Exams | Exams |
| `attendance.manage` | Attendance | Attendance |
| `reports.view` | Reports | Reserved. No School Admin report endpoint exists yet. |
| `settings.manage` | Settings | Subscription payments and invoices (`/schools/{id}/payments`, `/schools/{id}/invoices`, `/payments/initiate`, `/payments/verify`) |

Use `GET /super-admin/roles` and `GET /super-admin/permissions` to build pickers instead of hard-coding these tables.

`GET /api/v1/super-admin/roles` — mock `200`:

```json
{
  "items": [
    {
      "key": "school_admin",
      "label": "School Admin",
      "permissions": ["dashboard.view", "school.manage", "students.manage", "teachers.manage", "fees.manage", "exams.manage", "attendance.manage", "reports.view", "settings.manage"]
    },
    {
      "key": "academic_admin",
      "label": "Academic Admin",
      "permissions": ["dashboard.view", "students.manage", "teachers.manage", "exams.manage", "attendance.manage", "reports.view"]
    },
    {
      "key": "accounts_admin",
      "label": "Accounts Admin",
      "permissions": ["dashboard.view", "fees.manage", "reports.view"]
    }
  ]
}
```

`GET /api/v1/super-admin/permissions` — mock `200`:

```json
{
  "items": [
    {"key": "dashboard.view", "label": "Dashboard"},
    {"key": "school.manage", "label": "School Management"},
    {"key": "students.manage", "label": "Student Management"},
    {"key": "teachers.manage", "label": "Teacher Management"},
    {"key": "fees.manage", "label": "Fees"},
    {"key": "exams.manage", "label": "Exams"},
    {"key": "attendance.manage", "label": "Attendance"},
    {"key": "reports.view", "label": "Reports"},
    {"key": "settings.manage", "label": "Settings"}
  ]
}
```

## School Admin object

Returned by create, get, edit, status, roles, invite, and inside list `items`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID string | |
| `email` | string | Lowercase. Cannot be changed. |
| `first_name`, `last_name` | string | |
| `mobile` | string or `null` | |
| `role` | string | Always `"school_admin"` |
| `school_id` | integer | Cannot be changed |
| `school_name` | string or `null` | |
| `status` | `1` or `0` | |
| `roles` | string[] | Admin role keys, catalog order |
| `permissions` | string[] | Union of the roles' permissions, catalog order |
| `created_at` | ISO datetime | |
| `invite_sent` | `true`, `false` or `null` | Only set by create-without-password and `/invite`. `true` = the mail server accepted the email. `false` = not sent (mail not configured, delivery failed, or account inactive). `null` on every other response. |

Never present: `password`, `password_hash`, tokens.

Mock:

```json
{
  "id": "6f1c2a9e-3b7d-4c11-9a2e-5d8f0b1c7e42",
  "email": "rahul@abcschool.example",
  "first_name": "Rahul",
  "last_name": "Sharma",
  "mobile": "9876543210",
  "role": "school_admin",
  "school_id": 12,
  "school_name": "ABC Public School",
  "status": 1,
  "roles": ["school_admin"],
  "permissions": ["dashboard.view", "school.manage", "students.manage", "teachers.manage", "fees.manage", "exams.manage", "attendance.manage", "reports.view", "settings.manage"],
  "created_at": "2026-10-16T10:00:00Z",
  "invite_sent": null
}
```

## Create a School Admin

`POST /api/v1/super-admin/schools/{school_id}/admins` → `201`

| Field | Required | Rule |
|---|---|---|
| `email` | Yes | Valid email. Must not belong to any account (case-insensitive, across all schools and roles). |
| `first_name` | Yes | 1–128 characters, not only spaces |
| `last_name` | Yes | 1–128 characters, not only spaces |
| `mobile` | No | Max 32 characters. `""` or omitted = `null` |
| `password` | No | 8–128 characters. **Omit it to send an invitation instead.** |
| `roles` | No | 1–10 keys from `/super-admin/roles`. Omit for `["school_admin"]`. |
| `status` | No | `1` (default) or `0` |

The school must exist and not be deleted. A pending or inactive school is allowed (public registration and the school form create admins before activation); the admin can sign in once the school is active.

### With a password

```json
{
  "email": "rahul@abcschool.example",
  "password": "Str0ngPass!",
  "first_name": "Rahul",
  "last_name": "Sharma",
  "mobile": "9876543210",
  "roles": ["academic_admin"]
}
```

Response `201`: the [School Admin object](#school-admin-object) with `"invite_sent": null`.

### With an invitation (no password)

```json
{
  "email": "priya@abcschool.example",
  "first_name": "Priya",
  "last_name": "Nair",
  "roles": ["accounts_admin"]
}
```

Response `201`:

```json
{
  "id": "0b8e7d6c-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  "email": "priya@abcschool.example",
  "first_name": "Priya",
  "last_name": "Nair",
  "mobile": null,
  "role": "school_admin",
  "school_id": 12,
  "school_name": "ABC Public School",
  "status": 1,
  "roles": ["accounts_admin"],
  "permissions": ["dashboard.view", "fees.manage", "reports.view"],
  "created_at": "2026-10-20T09:15:00Z",
  "invite_sent": true
}
```

The account is created even when `invite_sent` is `false`. Show a warning such as "Invitation email was not sent" and offer **Resend invitation** (`/invite`) or **Set password** (edit). The invited admin cannot sign in until they set a password through the emailed link.

The email links to `ADMIN_RESET_URL?token=...` (the same page as password reset). The link is valid for 72 hours (`INVITE_TTL_MINUTES`) and works once.

Errors: `401`, `403`, `404` `School not found`, `409` `Email already registered`, `422` (validation, or `Unknown role: owner`), `500` `School admin could not be created`.

## List School Admins

`GET /api/v1/super-admin/schools/{school_id}/admins` — one school (404 if the school does not exist)

`GET /api/v1/super-admin/school-admins` — all schools

| Query | Default | Rule |
|---|---|---|
| `page` | `1` | ≥ 1 |
| `page_size` | `20` | 1–100 |
| `q` | — | Case-insensitive partial match on first name, last name, full name (`"Rahul Sharma"`) or email |
| `status` | — | `1` or `0`. Omit for both. |
| `role` | — | One role key. `school_admin` also matches admins created before roles existed. |
| `sort` | `-created_at` | `name`, `-name`, `created_at`, `-created_at`. `name` sorts by first name, then last name. |
| `school_id` | — | Cross-school list only. Unknown school → `404`. |

Example: `GET /api/v1/super-admin/school-admins?q=sharma&status=1&role=academic_admin&sort=name&page=1&page_size=20`

Mock `200`:

```json
{
  "items": [
    {
      "id": "6f1c2a9e-3b7d-4c11-9a2e-5d8f0b1c7e42",
      "email": "rahul@abcschool.example",
      "first_name": "Rahul",
      "last_name": "Sharma",
      "mobile": "9876543210",
      "role": "school_admin",
      "school_id": 12,
      "school_name": "ABC Public School",
      "status": 1,
      "roles": ["academic_admin"],
      "permissions": ["dashboard.view", "students.manage", "teachers.manage", "exams.manage", "attendance.manage", "reports.view"],
      "created_at": "2026-10-16T10:00:00Z",
      "invite_sent": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`total` counts all matches, not just this page. Pages = `ceil(total / page_size)`.

Errors: `401`, `403`, `404` (school), `422` (`Invalid sort`, `Invalid role`, or out-of-range `page`/`page_size`/`status`).

## Get, edit, status, roles, invite

All paths start with `/api/v1/super-admin/schools/{school_id}/admins/{admin_id}`. If the admin does not belong to that school, the answer is `404` `School admin not found`. All return the [School Admin object](#school-admin-object).

### Get

`GET .../admins/{admin_id}` → `200`

### Edit

`PATCH .../admins/{admin_id}` → `200`

| Field | Rule |
|---|---|
| `first_name`, `last_name` | 1–128 characters |
| `mobile` | Max 32. Send `null` or `""` to clear. |
| `password` | 8–128. Signs the admin out of every session and cancels pending reset/invite links. |

Send only the fields that change. `email`, `school_id`, `role`, `roles` and `status` are rejected with `422` — use the dedicated endpoints.

```json
{"last_name": "Verma", "mobile": "9123456780"}
```

Errors: `401`, `403`, `404`, `422`, `500` `School admin could not be updated`.

### Activate / deactivate

`PATCH .../admins/{admin_id}/status` → `200`

```json
{"status": 0}
```

Deactivating (`0`) immediately ends every session of that admin (their next request gets `401`), cancels pending reset/invite links, and blocks login (`403` `Account inactive`). The account and the school's data are kept; nothing is deleted. Activating (`1`) lets them sign in again with their existing password.

Errors: `401`, `403`, `404`, `422`, `500` `School admin status could not be changed`.

### Change roles

`PATCH .../admins/{admin_id}/roles` → `200`

```json
{"roles": ["academic_admin", "accounts_admin"]}
```

Replaces the whole set. Duplicates are removed; the response lists roles in catalog order. Takes effect on the admin's next request, without signing them out.

Errors: `401`, `403` (including a School Admin trying to change roles), `404`, `422` (`[]`, `["super_admin"]`, unknown key, or extra fields), `500` `School admin roles could not be changed`.

### Resend invitation

`POST .../admins/{admin_id}/invite` → `200`, no body

Sends a new password-setup link; earlier links stop working. Check `invite_sent` in the response.

Errors: `401`, `403`, `404`, `422` `Activate the account before sending an invitation`, `500` `Invitation could not be created`.

## Forgot and reset password

Public endpoints used by the login page and the reset page (`/login/reset?token=...`). Available to active School Admins (whose school is active) and Super Admins.

### Forgot password

`POST /api/v1/auth/forgot-password` → **always `202`**

```json
{"email": "rahul@abcschool.example", "app_origin": "https://admin.example.com"}
```

`app_origin` is optional and ignored; the link always uses the server's `ADMIN_RESET_URL`.

```json
{"message": "If an account exists for that email, a reset link has been sent."}
```

The response is identical for unknown, inactive and valid emails, so show the `message` as-is and never tell the user whether the account exists. The link is valid for 60 minutes and works once. Asking again cancels the earlier link.

Errors: `422` (invalid email), `429` (rate limit).

### Reset password

`POST /api/v1/auth/reset-password` → `200`

Read `token` from the page URL query string.

```json
{"token": "<token from the link>", "new_password": "N3wPassword!", "confirm_password": "N3wPassword!"}
```

```json
{"message": "Password has been reset."}
```

The same endpoint completes invitations. On success every existing session is signed out; send the user to the login page.

| Status | `detail` | Show |
|---|---|---|
| `400` | `Invalid or expired reset link.` | "This link is invalid or has expired. Request a new one." |
| `422` | `New password and confirmation must match.` | Field error |
| `422` | validation array | Password shorter than 8 or longer than 128 |
| `429` | `Too many attempts. Try again later.` | Retry later |
| `500` | `Password could not be reset` | Generic error |

## School Admin access rules

These apply to School Admin tokens on `/api/v1/school-admin/...`, `/api/v1/schools/{id}/payments|invoices` and `/api/v1/payments/...`. The backend enforces them; hiding menus in the UI is only cosmetic.

| Situation | Status | `detail` |
|---|---|---|
| No or bad token, logged out, session ended by deactivation or password change | `401` | `Not authenticated` |
| Account deactivated (token still valid) | `403` | `Account inactive` |
| Not a School Admin (Super Admin or plain user) | `403` | `Forbidden` |
| School pending approval | `403` | `This school is waiting for approval. You can sign in after it is activated.` |
| School suspended or deactivated | `403` | `School access is suspended` |
| Subscription expired | `403` | `Subscription access is not available` |
| Role lacks the module's permission | `403` | `Permission denied` |
| Record belongs to another school | `404` | `Record not found` |
| Filter id (`medium_id`, `class_id`, …) belongs to another school | `404` | `Record not found` |
| Edit points at another school's class/session/user etc. | `422` | e.g. `Medium does not belong to this school` |
| Body includes `school_id` / other forbidden ownership fields | `422` | Validation / extra fields forbidden |

The school is always taken from the signed-in admin's account, never from the request body, query, path, or headers. A School Admin cannot reach another school's data by changing an id. Direct `/school-admin/...` academic routes and legacy `/school-admin/academics/...` routes use the same auth dependencies and school-scoped services.

To decide which School Admin menus to show, the Super Admin side has `roles` and `permissions` on each admin. The School Admin panel can treat a `403` `Permission denied` as "hide this module".

## Errors and status codes

| Code | Meaning |
|---|---|
| `200` | OK |
| `201` | Created |
| `202` | Accepted (forgot password) |
| `204` | Logged out |
| `400` | Invalid or expired reset link |
| `401` | Missing, invalid, expired or revoked token; wrong email or password |
| `403` | Wrong role, inactive account, school not active, or missing permission |
| `404` | School or School Admin not found, or not in that school |
| `409` | Email already registered |
| `422` | Validation error |
| `429` | Too many attempts. Has a `Retry-After` header (seconds). |
| `500` | Change not saved (the message says which); nothing partial is stored |

Message errors:

```json
{"detail": "Email already registered"}
```

Validation errors (FastAPI) — map `loc` to form fields:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": {"min_length": 8}
    }
  ]
}
```

Unknown fields appear as `"type": "extra_forbidden"`.

## Limitations

| Area | Current behaviour |
|---|---|
| Rate limits | Failed logins: 10 per email or 50 per IP in 15 min (shared by `/auth/login` and `/super-admin/login`; successful logins do not count). Forgot password: 5 per email or 20 per IP per hour. Reset password: 10 per IP in 15 min. Counts are kept per server process. |
| Email | Sent only when SMTP and `ADMIN_RESET_URL` are configured on the server. Otherwise `invite_sent` is `false` and forgot-password sends nothing (same `202`). `invite_sent: true` means the mail server accepted the email, not that it reached the inbox. |
| Reports / Settings | `reports.view` has no School Admin endpoint yet. `settings.manage` covers subscription billing only. |
| School Admin self-permissions | `GET /school-admin/me` does not yet return `roles`/`permissions`. |
| Legacy admin API | The older cookie-based `/api/admin/*` routes are not covered by these roles. |
| Search | `%` and `_` in `q` act as wildcards. |

### Server settings (for whoever deploys)

`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `ADMIN_RESET_URL` (e.g. `https://admin.example.com/login/reset`), `PASSWORD_RESET_TTL_MINUTES` (60), `INVITE_TTL_MINUTES` (4320). Database migration `20261020_0016` must be applied before these routes are used.
