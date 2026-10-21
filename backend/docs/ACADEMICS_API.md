# School Admin Academic Structure API

For Vishal / School Admin Panel integration. All School Admin routes (including academics) use the Swagger tag **`v1-school-admin`**. Academic URLs remain under `/api/v1/school-admin/academics/...`.

Related: [SCHOOL_ADMIN_RBAC_API.md](SCHOOL_ADMIN_RBAC_API.md) · **Shareable contract (Phase 10):** [ACADEMICS_FRONTEND_CONTRACT.md](ACADEMICS_FRONTEND_CONTRACT.md) (endpoint inventory, samples, dropdown map, open questions).

## Conventions

| Topic | Rule |
|---|---|
| Auth | `Authorization: Bearer <token>` from School Admin login |
| School context | Always from the signed-in admin’s `school_id`. Never send `school_id` in the body. |
| Success body | Resource object or `{items, total, page, page_size}` |
| Errors | `{"detail": "..."}` (never SQL / constraint text) |
| Soft delete | Structure rows set `deleted_at`; they stay in the database for history |
| Pagination | `page` ≥ 1 (default 1), `page_size` 1–50 (default 20) |

### Permissions (unchanged role catalog)

| Operation | Permission |
|---|---|
| Read structure (`sessions`, `classes`, `sections`, `subjects`, `mediums`, `class-sections`, `class-subjects`) | `dashboard.view` |
| Write structure (create/update/delete/activate) | `school.manage` |
| Teacher people + teacher-assignments (read and write) | `teachers.manage` |

`teachers.manage` already exists. Role definitions were not changed. `academic_admin` can manage teacher assignments but cannot write structure (no `school.manage`). `accounts_admin` can read structure (`dashboard.view`) but cannot write structure or open teacher-assignments.

### Authentication & tenant isolation (Phase 9)

- All academic routes under `/api/v1/school-admin/` require a School Admin bearer token (`401` if missing/invalid).
- School ownership is resolved only from `auth.user.school_id` (server session). Path/query/body `school_id` is never trusted; write bodies use `extra=forbid` and a server-side blocklist (`school_id`, `id`, `deleted_at`, `staff_id`, …).
- Foreign-school **resources** and **filter ids** (`medium_id`, `class_id`, …) → `404` `Record not found` (existence concealment).
- Foreign-school **references in create/update bodies** → `422` (e.g. medium/class/subject does not belong to this school).
- Direct routes and `/academics/...` legacy routes share the same services and permission model.
- Intentionally public (not School Admin academic): auth login/forgot-password routes only — see [SCHOOL_ADMIN_RBAC_API.md](SCHOOL_ADMIN_RBAC_API.md).

## Compact sessions (unchanged)

`GET /api/v1/school-admin/sessions`

```json
{ "items": [ { "id": 1, "name": "2026-27", "default": 1 } ] }
```

Do not rely on this endpoint for dates or CRUD. Full session management uses the academics paths below.

## Class management (direct routes)

Preferred School Admin class API. Paths are under `/api/v1/school-admin/classes` (not `/academics/classes`). Swagger tag: `v1-school-admin`.

Equivalent list/create/update under `/api/v1/school-admin/academics/classes` remain for existing clients and share the same service layer.

| Method | Path | Permission |
|---|---|---|
| GET | `/api/v1/school-admin/classes` | `dashboard.view` |
| POST | `/api/v1/school-admin/classes` | `school.manage` |
| GET | `/api/v1/school-admin/classes/{class_id}` | `dashboard.view` |
| PATCH | `/api/v1/school-admin/classes/{class_id}` | `school.manage` |

Soft delete stays on `DELETE /api/v1/school-admin/academics/classes/{id}` (sets `deleted_at`). Direct routes do not expose delete.

### Model fields (`classes` / `SchoolClass`)

| Field | Notes |
|---|---|
| `id` | Integer PK |
| `name` | Required, trimmed, max 512 |
| `medium_id` | Required; must belong to the same school |
| `include_semesters` | `0` or `1` (default `0`) |
| `school_id` | From auth only; never accepted from the client |
| `deleted_at` | Soft-delete marker; active listings exclude these rows |

No `session_id` / status column on `classes`. Academic session is not a class field in the current schema.

### Uniqueness

Active class names are unique per **school + medium** (case-insensitive). Soft-deleted names may be reused. Same name under a different medium in the same school is allowed.

### List query parameters

| Param | Default | Notes |
|---|---|---|
| `q` | `""` | Case-insensitive substring match on `name` |
| `medium_id` | omitted | Filter by medium |
| `page` | `1` | ≥ 1 |
| `page_size` | `20` | 1–50 |

Response:

```json
{
  "items": [
    { "id": 3, "name": "Grade 1", "medium_id": 1, "include_semesters": 0 }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Create

```http
POST /api/v1/school-admin/classes
```

```json
{ "name": "Grade 1", "medium_id": 1, "include_semesters": 0 }
```

```json
{ "id": 3, "name": "Grade 1", "medium_id": 1, "include_semesters": 0 }
```

### Detail

```http
GET /api/v1/school-admin/classes/{class_id}
```

Includes linked `class_sections` and `class_subjects` for this school (batch-loaded). Missing or other-school id → `404`.

```json
{
  "id": 3,
  "name": "Grade 1",
  "medium_id": 1,
  "include_semesters": 0,
  "sections": [
    { "id": 10, "section_id": 2, "section_name": "A", "medium_id": 1 }
  ],
  "subjects": [
    { "id": 5, "subject_id": 9, "subject_name": "Math" }
  ]
}
```

### Update (PATCH)

Only `name`, `medium_id`, and `include_semesters` may change. Omitted fields are preserved. Changing name or medium rechecks uniqueness. Does not cascade to sections or subjects.

### Class errors

| Status | When |
|---|---|
| 409 | Active duplicate name for the same school + medium |
| 422 | Blank name, missing `medium_id` on create, invalid `include_semesters`, or medium not in this school |
| 404 | Class missing, soft-deleted, or belongs to another school |

## Section management (direct routes)

Preferred School Admin section API. Paths are under `/api/v1/school-admin/sections` (not `/academics/sections`). Swagger tag: `v1-school-admin`.

### Relationship model

- `sections` (`Section`): school-scoped name catalog — `id`, `name`, `school_id`, `deleted_at`. **No `class_id` column.**
- `class_sections` (`ClassSection`): links `class_id` + `section_id` + `medium_id` + `school_id`.

Direct create requires `class_id` and creates/reuses a `Section`, then adds a `ClassSection` using the class’s `medium_id`. Academics `POST /academics/sections` still creates a bare school section without a class link (compat).

| Method | Path | Permission |
|---|---|---|
| GET | `/api/v1/school-admin/sections` | `dashboard.view` |
| POST | `/api/v1/school-admin/sections` | `school.manage` |
| GET | `/api/v1/school-admin/sections/{section_id}` | `dashboard.view` |
| PATCH | `/api/v1/school-admin/sections/{section_id}` | `school.manage` |

No DELETE on direct routes. Soft delete remains on `DELETE /api/v1/school-admin/academics/sections/{id}`.

### Uniqueness

Active section **names** are unique per **class** (case-insensitive), enforced via `sections` ⨝ `class_sections`. Soft-deleted mappings/sections do not block reuse. The same name may be linked to different classes (shared `Section` row when the name already exists in the school).

### List query parameters

| Param | Default | Notes |
|---|---|---|
| `q` | `""` | Case-insensitive substring on section `name` |
| `class_id` | omitted | Only sections linked to this class; class must belong to the school (`404` otherwise) |
| `page` | `1` | ≥ 1 |
| `page_size` | `20` | 1–50 |

Without `class_id`, items are `{id, name}`. With `class_id`, items also include `class_id`, `class_name`, `medium_id`, `class_section_id`.

### Create

```http
POST /api/v1/school-admin/sections
```

```json
{ "name": "A", "class_id": 3 }
```

```json
{
  "id": 2,
  "name": "A",
  "class_id": 3,
  "class_name": "Grade 1",
  "medium_id": 1,
  "class_section_id": 10
}
```

### Detail

```http
GET /api/v1/school-admin/sections/{section_id}
```

```json
{
  "id": 2,
  "name": "A",
  "classes": [
    {
      "class_id": 3,
      "class_name": "Grade 1",
      "medium_id": 1,
      "class_section_id": 10
    }
  ]
}
```

### Update (PATCH)

- `name`: renames the school `Section` (shared across linked classes); rechecks name uniqueness in each linked class.
- `class_id`: if the section has no mapping, creates one; if exactly one mapping, reassigns it (updates `class_sections.class_id` / `medium_id`); if multiple mappings and the target class is not already linked → `422` (use `/academics/class-sections`).

Does not cascade-delete classes or other records.

### Section errors

| Status | When |
|---|---|
| 409 | Active duplicate section name for the same class |
| 422 | Blank name, missing `class_id` on create, or multi-class reassignment not supported |
| 404 | Section/class missing, soft-deleted, or other school |

## Subject management (direct routes)

Preferred School Admin subject API. Paths are under `/api/v1/school-admin/subjects`. Swagger tag: `v1-school-admin`.

Academics `/academics/subjects` and `/academics/class-subjects` remain for existing clients and share the same service layer for create/update/list.

| Method | Path | Permission |
|---|---|---|
| GET | `/api/v1/school-admin/subjects` | `dashboard.view` |
| POST | `/api/v1/school-admin/subjects` | `school.manage` |
| GET | `/api/v1/school-admin/subjects/{subject_id}` | `dashboard.view` |
| PATCH | `/api/v1/school-admin/subjects/{subject_id}` | `school.manage` |
| GET | `/api/v1/school-admin/subjects/{subject_id}/classes` | `dashboard.view` |
| PUT | `/api/v1/school-admin/subjects/{subject_id}/classes` | `school.manage` |

No hard delete. Soft delete remains on `DELETE /api/v1/school-admin/academics/subjects/{id}` (`deleted_at`). Soft-deleted subjects are excluded from lists/details and cannot be newly mapped.

### Model fields (`subjects` / `Subject`)

| Field | Notes |
|---|---|
| `id` | Integer PK |
| `name` | Required, trimmed, max 512 |
| `code` | Optional, trimmed, max 64; blank → `null` |
| `type` | `Theory` or `Practical` (schema default `Theory`). **Not** Compulsory/Elective |
| `medium_id` | Required; must belong to the school |
| `school_id` | From auth only |
| `deleted_at` | Soft-delete / deactivation |
| `bg_color`, `image` | Exist on the table; not exposed on these direct write routes |

Class association uses `class_subjects` (`ClassSubject`): `school_id`, `class_id`, `subject_id`, `deleted_at`.

### Uniqueness

Active non-blank subject **codes** are unique per **school + medium** (case-insensitive). Null/blank codes may repeat. Soft-deleted codes may be reused.

### List query parameters

| Param | Default | Notes |
|---|---|---|
| `q` | `""` | Matches `name` or `code` (ilike) |
| `medium_id` | omitted | Filter by medium |
| `class_id` | omitted | Subjects linked via active `class_subjects`; foreign class → `404` |
| `page` / `page_size` | 1 / 20 | `page_size` 1–50 |

```json
{
  "items": [
    { "id": 9, "name": "Math", "code": "M1", "type": "Theory", "medium_id": 1 }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Create

```json
{ "name": "Math", "code": "M1", "type": "Theory", "medium_id": 1 }
```

### Detail

Includes active `classes[]` (`class_id`, `class_name`, `medium_id`, `class_subject_id`).

### Update (PATCH)

May change `name`, `code`, `type`, `medium_id`. Does **not** change class associations (use PUT `…/classes`).

### Class associations

`GET …/subjects/{id}/classes` — paginated active links.

`PUT …/subjects/{id}/classes` with `{ "class_ids": [3, 4] }`:

- Validates the full set before commit (one transaction).
- Every class must belong to the school and match the subject’s `medium_id`.
- Links not in the set are **soft-deleted** (`deleted_at` set); never hard-deleted.
- Previously soft-deleted mappings for a desired class are **revived**.
- Empty `class_ids` clears all active associations.
- Does not delete the subject or any class.

Academics `POST /class-subjects` remains available for single-link create.

### Subject errors

| Status | When |
|---|---|
| 409 | Duplicate active code for the same school + medium |
| 422 | Invalid name/type/code, missing fields, or class medium mismatch |
| 404 | Subject/class missing, soft-deleted, or other school |

## Academic sessions

Base path: `/api/v1/school-admin/academics`

| Method | Path | Permission |
|---|---|---|
| GET | `/sessions` | `dashboard.view` |
| POST | `/sessions` | `school.manage` |
| GET | `/sessions/{id}` | `dashboard.view` |
| PATCH | `/sessions/{id}` | `school.manage` |
| DELETE | `/sessions/{id}` | `school.manage` (soft delete; clears `default`) |
| POST | `/sessions/{id}/activate` | `school.manage` |

Rules:

- `name` required, trimmed, max 512 characters.
- `end_date` must be on or after `start_date`.
- Active session names are unique per school (case-insensitive). Soft-deleted names may be reused.
- At most one `default: 1` session per school. `POST …/activate` and create/patch with `default: 1` clear other defaults in the same school, using row locks where supported.
- School id always comes from the authenticated School Admin.

## Structure resources

| Resource | List filters | Notes |
|---|---|---|
| `sessions` | `q` | List includes `default`, `start_date`, `end_date` |
| `classes` | `q`, `medium_id` | |
| `sections` | `q` | |
| `subjects` | `q`, `medium_id` | |
| `mediums` | `q` | |
| `class-sections` | `class_id`, `medium_id` | Includes `class_name`, `section_name` |
| `class-subjects` | `class_id`, `subject_id` | New mapping table |
| `teacher-assignments` | `teacher_id`, `subject_id`, `class_section_id`, `session_year_id` | `teacher_id` = id from `GET …/teachers` |

### Common CRUD

- `GET /{resource}`
- `POST /{resource}` → `201`
- `PATCH /{resource}/{id}`
- `DELETE /{resource}/{id}` → `{"deleted": true}` (soft delete)

### Session activation

`POST /api/v1/school-admin/academics/sessions/{id}/activate`

- Sets this session’s `default` to `1`
- Sets every other non-deleted session for the same school to `default` `0`
- One database transaction (service commit)
- Permission: `school.manage`

Creating a session with `"default": 1` also clears other defaults.

`PATCH …/sessions/{id}` with `"default": 1` calls the same activation logic after applying other field updates.

### Class–subject

```json
POST /class-subjects
{ "class_id": 3, "subject_id": 9 }
```

Duplicate active mapping → `409` `This subject is already mapped to the class`.

### Teacher assignments (academics paths)

Teacher identity: **`teacher_id` is the legacy `users.id`** returned by `GET /academics/teachers`. The server resolves the matching `staffs` row for that user in the school and stores `staff_id` + `teacher_user_id`.

```json
POST /academics/teacher-assignments
{
  "teacher_id": 41,
  "subject_id": 9,
  "class_section_id": 12,
  "session_year_id": 2
}
```

`class_section_id` and `session_year_id` are optional. When a class section is set, the subject must already be mapped to that class via `class_subjects`. Duplicate open assignment → `409`.

## Teacher–subject assignments (direct routes)

Preferred School Admin assignment API under `/api/v1/school-admin/teacher-assignments`. Swagger tag: `v1-school-admin`.

Reuses existing `teacher_assignments` (`TeacherAssignment`). Class + section are stored as `class_section_id` (via `class_sections`). Session is `session_year_id` (also exposed as `session_id`).

| Method | Path | Permission |
|---|---|---|
| GET | `/api/v1/school-admin/teacher-assignments` | `teachers.manage` |
| POST | `/api/v1/school-admin/teacher-assignments` | `teachers.manage` |
| GET | `/api/v1/school-admin/teacher-assignments/{assignment_id}` | `teachers.manage` |
| PATCH | `/api/v1/school-admin/teacher-assignments/{assignment_id}` | `teachers.manage` |
| DELETE | `/api/v1/school-admin/teacher-assignments/{assignment_id}` | `teachers.manage` |

Permission matches the existing academics `teacher-assignments` resource (not `dashboard.view` / `school.manage`). Role catalog unchanged. `academic_admin` can manage assignments; `accounts_admin` cannot.

### Create

```json
{
  "teacher_id": 41,
  "subject_id": 9,
  "class_id": 3,
  "section_id": 2,
  "session_id": 5
}
```

Compat aliases: `class_section_id`, `session_year_id`. `class_id` and `section_id` must be provided together and must already be linked in `class_sections`. When a class section is present, an active `class_subjects` row for that class + subject is required.

### Uniqueness and team-teaching

Active uniqueness: `(school_id, staff_id, subject_id, class_section_id, session_year_id)` where `deleted_at IS NULL` (migration `0017` + app checks).

**Team-teaching is allowed:** different teachers may share the same session/class/section/subject. Duplicate is only the same teacher + same combination.

### List filters

`teacher_id`, `class_id`, `section_id`, `subject_id`, `session_id` plus `page` / `page_size` (1–50). Soft-deleted assignments are excluded. Envelope: `{items, total, page, page_size}`.

### Response fields

Includes `teacher_id`, `staff_id`, `teacher_name`, `subject_id`, `subject_name`, `class_section_id`, `class_id`, `class_name`, `section_id`, `section_name`, `session_id` / `session_year_id`, `session_name`.

### Removal

`DELETE` soft-deletes (`deleted_at`). Not reversible via API today (no revive endpoint). No FK from attendance/exams/timetable to `teacher_assignments`; soft-delete does not cascade-delete academic history. Soft-deleted rows return `404` on detail and are omitted from lists.

### Assignment errors

| Status | When |
|---|---|
| 409 | Duplicate active assignment for the same teacher + subject + class-section + session |
| 422 | Invalid/foreign refs, class/section mismatch, subject not mapped to class, inactive teacher |
| 404 | Missing/soft-deleted/foreign-school assignment |
| 403 | Missing `teachers.manage` |

## Errors

| Status | When |
|---|---|
| 401 | Missing/invalid token |
| 403 | Wrong role or missing permission |
| 404 | Unknown resource or row not in this school |
| 409 | Duplicate link / assignment |
| 422 | Related id not in this school, or invalid dates |

## Dependent dropdowns (frontend coordination)

Use existing list endpoints; no dedicated `/options/*` routes exist. Full mapping and samples: [ACADEMICS_FRONTEND_CONTRACT.md](ACADEMICS_FRONTEND_CONTRACT.md) §4.

| UI step | Endpoint | Key params | Option id | Label |
|---|---|---|---|---|
| Session | `GET /school-admin/sessions` (compact) or `GET …/academics/sessions` | — / `q,page` | `id` | `name` |
| Medium | `GET …/academics/mediums` | `q,page,page_size` | `id` | `name` |
| Class | `GET /school-admin/classes` | `medium_id` | `id` | `name` |
| Section | `GET /school-admin/sections` | `class_id` | `id` (+ `class_section_id`) | `name` |
| Subject | `GET /school-admin/subjects` | `class_id`, `medium_id` | `id` | `name` |
| Teacher | `GET …/academics/teachers` | `q,page,page_size` | `id` (= `teacher_id`) | `name` |
| Assignment submit | `POST /school-admin/teacher-assignments` | compose from above | — | — |

Foreign filter ids → `404`. Soft-deleted rows are omitted. Pagination default `page_size=20` (max 50); compact sessions are unpaginated.

## Database schema (Phase 8 audit)

### Models reused (no duplicates)

| Model | Table | Role |
|---|---|---|
| `SessionYear` | `session_years` | Academic sessions |
| `SchoolClass` | `classes` | Classes (per medium) |
| `Section` | `sections` | School-level section names |
| `ClassSection` | `class_sections` | Class ↔ section map |
| `Subject` | `subjects` | Subjects (per medium) |
| `ClassSubject` | `class_subjects` | Class ↔ subject map |
| `TeacherAssignment` | `teacher_assignments` | Teacher ↔ subject (+ optional class-section + session) |
| `Medium` | `mediums` | Medium catalog |

### Uniqueness scopes (active = `deleted_at IS NULL`)

| Constraint | Scope |
|---|---|
| `uq_session_years_school_name_active` | `(school_id, lower(btrim(name)))` |
| `uq_session_years_school_default_active` | one row with `default = 1` per school (zero allowed) |
| `uq_classes_school_medium_name_active` | `(school_id, medium_id, lower(btrim(name)))` |
| `uq_class_sections_school_class_section_active` | `(school_id, class_id, section_id)` |
| `uq_subjects_school_medium_code_active` | `(school_id, medium_id, lower(btrim(code)))` when code non-blank |
| `uq_class_subjects_school_class_subject_active` | `(school_id, class_id, subject_id)` |
| `uq_teacher_assignments_active` | `(school_id, staff_id, subject_id, class_section_id, session_year_id)` — team-teaching OK |

Section **name** uniqueness within a class remains **application-level** (join `sections` ⨝ `class_sections`). No denormalized name column on `class_sections`.

### Foreign keys and soft delete

- **New tables** (`class_subjects`, `teacher_assignments`): real FKs to `schools`, `classes`, `subjects`, `staffs`, `users`, `class_sections`, `session_years`. No `ON DELETE CASCADE` in migrations (default RESTRICT/NO ACTION). Soft-delete via `deleted_at`; history preserved.
- **Legacy tables** (`session_years`, `classes`, `sections`, `subjects`, `class_sections`, `mediums`): `school_id` / `medium_id` / `class_id` / `section_id` are **integers without DB FKs**. Cross-school / orphan refs are rejected in services. Adding FKs is a separate approved change after orphan audit.
- Soft-deleted mappings/assignments do not appear in active API lists; rows are not hard-deleted.

### Known gaps (approval required)

1. Legacy integer references → optional FKs after orphan cleanup.
2. Composite school-scoped FKs (e.g. `(school_id, class_id)`) — not present; would require composite unique keys on parents first.
3. Session `end_date >= start_date` — app-validated; no DB check constraint yet.
4. Compulsory/Elective subject types — not in schema (`type` is Theory/Practical).

## Migrations

Linear head: **`20261021_0022`**.

| Revision | Parent | Purpose |
|---|---|---|
| `20261021_0017` | `20261020_0016` | `class_subjects`, `teacher_assignments` + unique active indexes |
| `20261021_0018` | `20261021_0017` | Unique active session name per school |
| `20261021_0019` | `20261021_0018` | Unique active class name per school + medium |
| `20261021_0020` | `20261021_0019` | Unique active `class_sections` (school, class, section) |
| `20261021_0021` | `20261021_0020` | Unique active subject code per school + medium |
| `20261021_0022` | `20261021_0021` | Lookup indexes + at-most-one default session per school |

**Local app DB (`APP_ENV=local`, database name `eschool_saas_v1`):** applied `20261020_0016` → `20261021_0022` during the final release audit after read-only preflight (0 conflict groups). Other environments (staging/production) must not assume this; confirm identity, run preflight, then upgrade separately. Downgrades drop only indexes/tables introduced by these revisions.
