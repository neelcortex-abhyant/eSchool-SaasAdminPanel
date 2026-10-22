# School Admin academics API contract

This is the contract the School Admin "Academic structure" pages expect. The UI code is in `admin-web/lib/academics/http.ts`. Until a feature's endpoints are deployed, its page uses mock data that follows these same rules (`admin-web/lib/academics/mock.ts`).

The routes extend the existing `app/api/v1/school_admin_academics.py` router instead of adding a separate `/api/v1/school/...` tree.

Base path: `/api/v1/school-admin/academics`

Auth: `Authorization: Bearer <session token>`, using `require_school_admin`. The school is always `auth.user.school_id`. The UI never sends `school_id`, and the server should reject it as an unknown field (`extra="forbid"`). A record id from another school returns `404`, the same as a missing record. A referenced id from another school, such as a `class_id` in a body, returns `422`.

All JSON below is fictional.

## Status of each route

| Route | Today | Needed |
|---|---|---|
| `GET/POST /sessions`, `PATCH /sessions/{id}` | Exists | Return `default` in list rows. Validate dates on PATCH. Reject overlapping sessions with `409`. Add `status` filter |
| `POST /sessions/{id}/activate` | Missing | **New** |
| `GET /mediums` | Exists | None |
| `GET/POST /classes`, `PATCH /classes/{id}` | Exists | Add `session_year_id` (nullable) and `status` columns, `medium_name`/`session_name` in rows, and filters. Return `409` for a duplicate name in the same medium |
| `GET/POST /class-sections`, `PATCH /class-sections/{id}` | GET/POST exist, PATCH missing | POST takes `section_name` (find or create the `sections` row). Add `status`, names in rows, the `class_id` filter and PATCH. Unique `(school_id, class_id, section_id)` among rows that aren't deleted, returning `409` |
| `GET/POST /subjects`, `PATCH /subjects/{id}` | Exists | Add `status`, `classes` mapping (needs a `class_subjects` table), filters, and a unique code per school (`409`) |
| `GET /teachers` | Exists | None |
| `GET/POST /teacher-assignments`, `PATCH/DELETE /teacher-assignments/{id}` | Missing | **New**, needs a `subject_teachers` table |

The admin-web build chooses live or mock per page with `NEXT_PUBLIC_ACADEMICS_API_MODE`, for example `sessions:live,classes:live`. Switch a page to live once its row in this table is done.

## Lists

Every list returns:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20 }
```

Common query parameters are `page` (default 1), `page_size` (1–50, default 20), `q` (case-insensitive partial match) and `status` (`1` or `0`, omit for both). Filters combine.

## Errors

The same shapes as the rest of v1:

| Status | Body |
|---|---|
| 401 | `{"detail":"Not authenticated"}` |
| 403 | `{"detail":"Forbidden"}` or `{"detail":"School access is suspended"}` |
| 404 | `{"detail":"Record not found"}` |
| 409 | `{"detail":"Section A already exists in Class 5"}`, a sentence the UI shows as is |
| 422 | Pydantic list. The UI places each message next to the field named by the last `loc` entry |

```json
{ "detail": [ { "loc": ["body", "end_date"], "msg": "Value error, End date must be after the start date", "type": "value_error" } ] }
```

## Academic sessions

Row:

```json
{ "id": 2, "name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1 }
```

`default: 1` marks the active session. Exactly one session per school is active. The UI also accepts `is_active: true`.

- `POST /sessions` with body `{ "name", "start_date", "end_date" }` returns `201` and the row. `end_date` must be after `start_date` (`422` on `end_date`). A duplicate name or overlapping dates return `409`. When the school has no other session, the new one is active.
- `PATCH /sessions/{id}` takes the same body and rules.
- `POST /sessions/{id}/activate` takes no body. In one transaction it sets this session to `default=1` and every other session of the school to `0`, then returns the row. This matches the existing `POST /super-admin/schools/{id}/activate` style.
- Filter: `status=1` returns only the active session.

## Classes

Row:

```json
{ "id": 3, "name": "Class 5", "medium_id": 1, "medium_name": "English", "session_year_id": 2, "session_name": "2026-27", "status": 1 }
```

`session_year_id: null` means the class runs in every session.

- `POST /classes` with body `{ "name", "medium_id", "session_year_id": number|null, "status": 0|1 }`. `medium_id` and `session_year_id` must belong to the school (`422`). A duplicate name in the same medium returns `409`.
- `PATCH /classes/{id}` takes the same body.
- Filters: `session_year_id` (returns classes in that session plus classes with `null`), `medium_id`, `status`, `q`.

## Sections (class sections)

Row:

```json
{ "id": 4, "class_id": 3, "class_name": "Class 5", "section_id": 1, "section_name": "A", "status": 1 }
```

- `POST /class-sections` with body `{ "class_id", "section_name", "status" }`. The server finds the school's `sections` row by name, ignoring case, or creates it, and copies `medium_id` from the class. A duplicate section in the same class returns `409`. An inactive class returns `422` on `class_id`.
- `PATCH /class-sections/{id}` takes the same body. `class_id` can't change, and the UI locks it.
- Filters: `class_id`, `status`, and `q` (matches the class or section name).

## Subjects

Row:

```json
{
  "id": 5, "name": "Computer Science", "code": "CS", "type": "Theory",
  "medium_id": 1, "medium_name": "English", "status": 1,
  "classes": [ { "class_id": 5, "class_name": "Class 10", "type": "Elective" } ]
}
```

- `type` is `Theory` or `Practical`, as in the current model. `classes[].type` is `Compulsory` or `Elective`, kept per class mapping as in legacy `class_subjects`.
- `POST /subjects` with body `{ "name", "code", "type", "medium_id", "classes": [{ "class_id", "type" }], "status" }`. `code` is optional and stored uppercased. A code already used in the school returns `409`. Each class must be in the subject's medium (`422` on `classes`).
- `PATCH /subjects/{id}` takes the same body. `classes` replaces the full mapping. Removing a class that still has teacher assignments for this subject returns `409` with `Remove the teacher assignments for <subject> in <class> before unmapping it`.
- Filters: `class_id`, `kind` (`Compulsory` or `Elective`, applied to the `class_id` mapping when given, otherwise to any mapping), `type`, `status`, and `q` (name or code).

## Teachers

`GET /teachers` already exists. The UI reads `id`, `name` (or `first_name` + `last_name`) and `email`.

## Teacher assignments

Row:

```json
{
  "id": 1, "session_year_id": 2, "session_name": "2026-27",
  "class_id": 3, "class_name": "Class 5", "class_section_id": 4, "section_name": "A",
  "subject_id": 2, "subject_name": "Mathematics", "teacher_id": 102, "teacher_name": "Rahul Mehta"
}
```

- `POST /teacher-assignments` with body `{ "session_year_id", "class_section_id", "subject_id", "teacher_id" }` returns `201`.
- `PATCH /teacher-assignments/{id}` takes the same body, and `DELETE /teacher-assignments/{id}` returns `{"deleted": true}`.
- Validation (`422` on the named field):
  - every id belongs to the school,
  - the section and its class are active,
  - the class runs in that session (its `session_year_id` is null or equal),
  - the subject is active and mapped to the section's class, and
  - `teacher_id` is a staff member of the school.
- Conflict (`409`): one teacher per `(session_year_id, class_section_id, subject_id)`. Add a unique index for this. Message example: `Mathematics in Class 5 A is already assigned to Rahul Mehta for 2026-27`.
- Filters: `session_year_id`, `class_id`, `class_section_id`, `subject_id`, `teacher_id`, and `q` (teacher, subject, class or section name).

## Tests worth adding on the backend

- A School Admin from school B gets `404` for school A's ids and `422` when referencing them in a body.
- Activate leaves exactly one `default=1` session.
- Duplicate section in a class, duplicate subject code, and duplicate assignment slot each return `409`.
- Unmapping a subject with assignments returns `409`.
