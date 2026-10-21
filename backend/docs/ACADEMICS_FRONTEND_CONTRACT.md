# Academic API Contract — School Admin Panel (for Vishal)

**Status:** Verified against backend OpenAPI + services as of Phase 10 (documentation coordination).  
**Source of truth:** Live routes under `/api/v1/school-admin/` (not speculative).  
**Related:** [ACADEMICS_API.md](ACADEMICS_API.md) · [SCHOOL_ADMIN_RBAC_API.md](SCHOOL_ADMIN_RBAC_API.md)

All sample JSON is fictional. No credentials, tokens, or production PII.

---

## 1. Conventions (implemented & verified)

| Topic | Rule |
|---|---|
| Base | `/api/v1/school-admin` |
| Swagger tag | `v1-school-admin` |
| Auth | `Authorization: Bearer <opaque session token>` from School Admin login |
| School context | Always `auth.user.school_id`. **Never** send `school_id` in body/query/path for ownership |
| Success list | `{ "items": [...], "total": N, "page": 1, "page_size": 20 }` |
| Success detail / create | Resource object (no envelope wrapper) |
| Soft delete result | `{ "deleted": true }` |
| Errors | `{"detail": "..."}` or FastAPI validation array |
| Pagination | `page` ≥ 1 (default 1), `page_size` 1–50 (default 20) |
| Extra body fields | Rejected (`extra=forbid`) → `422` |

### Permissions

| Area | Permission |
|---|---|
| Read structure (sessions, classes, sections, subjects, mediums, class-sections, class-subjects) | `dashboard.view` |
| Write structure (create/PATCH/DELETE/activate; PUT subject classes) | `school.manage` |
| Teachers people + teacher-assignments (read & write) | `teachers.manage` |

`academic_admin` can manage teacher-assignments but **cannot** write structure. `accounts_admin` can read structure only.

### Preferred vs compatibility paths

| Domain | Prefer (direct) | Compat (legacy academics) |
|---|---|---|
| Classes | `/classes` | `/academics/classes` |
| Sections | `/sections` | `/academics/sections` |
| Subjects + class links | `/subjects`, `/subjects/{id}/classes` | `/academics/subjects`, `/academics/class-subjects` |
| Teacher assignments | `/teacher-assignments` | `/academics/teacher-assignments` |
| Sessions (full CRUD + activate) | — | `/academics/sessions` |
| Sessions (compact dropdown) | `/sessions` | — |
| Mediums | — | `/academics/mediums` |
| Teachers people | — | `/academics/teachers` |

Direct routes do **not** expose soft-delete for classes/sections/subjects (use academics `DELETE`). Direct teacher-assignments **do** expose soft-delete.

---

## 2. Endpoint inventory

Legend: **V** = implemented & verified via OpenAPI + service code · **C** = compatibility path (same service) · **P** = proposed / needs Vishal agreement (no code yet)

### 2.1 Auth & context

| Status | Method | Path | Perm | Notes |
|---|---|---|---|---|
| V | GET | `/me` | `dashboard.view` | Current user; does **not** yet return roles/permissions |
| V | GET | `/school` | `dashboard.view` | Own school from auth |
| V | GET | `/schools/{school_id}` | `dashboard.view` | Only if `school_id == auth.school_id` else 403/404 per scope helper |

### 2.2 Academic sessions

| Status | Method | Path | Perm | Body / query | Soft delete |
|---|---|---|---|---|---|
| V | GET | `/sessions` | `dashboard.view` | — | n/a (compact: `id`, `name`, `default` only; **no pagination**) |
| V | GET | `/academics/sessions` | `dashboard.view` | `q`, `page`, `page_size` | excludes `deleted_at` |
| V | POST | `/academics/sessions` | `school.manage` | `name`, `start_date`, `end_date`, optional `default` | — |
| V | GET | `/academics/sessions/{id}` | `dashboard.view` | — | soft-deleted → 404 |
| V | PATCH | `/academics/sessions/{id}` | `school.manage` | partial fields | — |
| V | DELETE | `/academics/sessions/{id}` | `school.manage` | — | soft delete; clears `default` |
| V | POST | `/academics/sessions/{id}/activate` | `school.manage` | empty | sets default atomically |

**Validation:** `name` required, trimmed, max 512; `end_date >= start_date`; active names unique per school (case-insensitive); at most one `default: 1`.

### 2.3 Mediums (dropdown dependency)

| Status | Method | Path | Perm |
|---|---|---|---|
| V | GET/POST/PATCH/DELETE | `/academics/mediums` | read `dashboard.view` / write `school.manage` |

List item: `{ "id", "name" }`. No direct `/mediums` route.

### 2.4 Classes

| Status | Method | Path | Perm | Query |
|---|---|---|---|---|
| V | GET | `/classes` | `dashboard.view` | `q`, `medium_id`, `page`, `page_size` |
| V | POST | `/classes` | `school.manage` | body: `name`, `medium_id`, optional `include_semesters` (0\|1) |
| V | GET | `/classes/{class_id}` | `dashboard.view` | includes `sections[]`, `subjects[]` |
| V | PATCH | `/classes/{class_id}` | `school.manage` | partial |
| C | CRUD | `/academics/classes` | same | soft delete only on academics DELETE |

**Uniqueness:** active name unique per school + medium. Foreign `medium_id` filter → **404**.

### 2.5 Sections

| Status | Method | Path | Perm | Query |
|---|---|---|---|---|
| V | GET | `/sections` | `dashboard.view` | `q`, `class_id`, `page`, `page_size` |
| V | POST | `/sections` | `school.manage` | `{ "name", "class_id" }` — creates/reuses Section + ClassSection |
| V | GET | `/sections/{section_id}` | `dashboard.view` | includes `classes[]` |
| V | PATCH | `/sections/{section_id}` | `school.manage` | `name` and/or `class_id` |
| C | POST | `/academics/sections` | `school.manage` | name-only (no class link) — **different semantics** |

**Note:** `Section` has **no** `class_id` column. Class link is via `class_sections`. With `class_id` filter, list items include `class_id`, `class_name`, `medium_id`, `class_section_id`.

### 2.6 Subjects & class–subject associations

| Status | Method | Path | Perm | Query / body |
|---|---|---|---|---|
| V | GET | `/subjects` | `dashboard.view` | `q`, `medium_id`, `class_id`, `page`, `page_size` |
| V | POST | `/subjects` | `school.manage` | `name`, `medium_id`, optional `code`, `type` (`Theory`\|`Practical`) |
| V | GET | `/subjects/{id}` | `dashboard.view` | includes `classes[]` |
| V | PATCH | `/subjects/{id}` | `school.manage` | does **not** change class links |
| V | GET | `/subjects/{id}/classes` | `dashboard.view` | paginated |
| V | PUT | `/subjects/{id}/classes` | `school.manage` | `{ "class_ids": [3,4] }` replace set (soft-delete removed; revive historical) |
| C | POST | `/academics/class-subjects` | `school.manage` | `{ "class_id", "subject_id" }` single link |

**Type is Theory/Practical — not Compulsory/Elective.** Active non-blank `code` unique per school + medium.

### 2.7 Teachers (people)

| Status | Method | Path | Perm |
|---|---|---|---|
| V | GET | `/academics/teachers` | `teachers.manage` |
| V | POST | `/academics/teachers` | `teachers.manage` |

List item fields: `id` (**users.id** — use as `teacher_id`), `name`, `first_name`, `last_name`, `email`, `mobile`, `status`. Paginated. No direct `/teachers` route.

### 2.8 Teacher–subject assignments

| Status | Method | Path | Perm | Query |
|---|---|---|---|---|
| V | GET | `/teacher-assignments` | `teachers.manage` | `teacher_id`, `class_id`, `section_id`, `subject_id`, `session_id`, `page`, `page_size` |
| V | POST | `/teacher-assignments` | `teachers.manage` | see samples |
| V | GET | `/teacher-assignments/{id}` | `teachers.manage` | — |
| V | PATCH | `/teacher-assignments/{id}` | `teachers.manage` | partial; revalidates full combo |
| V | DELETE | `/teacher-assignments/{id}` | `teachers.manage` | soft delete → `{deleted: true}` |
| C | same | `/academics/teacher-assignments` | same | also accepts `class_section_id`, `session_year_id` filters |

**Uniqueness (active):** `(school_id, staff_id, subject_id, class_section_id, session_year_id)`. Team-teaching allowed (different teachers, same class/section/subject/session).

When `class_id`+`section_id` (or `class_section_id`) is set, subject must already be mapped via `class_subjects`.

### 2.9 Summary (optional dashboard)

| Status | Method | Path | Perm | Query |
|---|---|---|---|---|
| V | GET | `/academics/summary` | `dashboard.view` | optional `session_year_id` (foreign → 404) |

---

## 3. Sample JSON (fictional)

### 3.1 Compact sessions (dropdown)

`GET /api/v1/school-admin/sessions`

```json
{
  "items": [
    { "id": 5, "name": "2026-27", "default": 1 },
    { "id": 4, "name": "2025-26", "default": 0 }
  ]
}
```

### 3.2 Full session list / detail

`GET /api/v1/school-admin/academics/sessions`

```json
{
  "items": [
    {
      "id": 5,
      "name": "2026-27",
      "default": 1,
      "start_date": "2026-04-01",
      "end_date": "2027-03-31"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`POST /api/v1/school-admin/academics/sessions` → `201`

```json
{
  "name": "2027-28",
  "start_date": "2027-04-01",
  "end_date": "2028-03-31",
  "default": 0
}
```

```json
{
  "id": 6,
  "name": "2027-28",
  "default": 0,
  "start_date": "2027-04-01",
  "end_date": "2028-03-31"
}
```

### 3.3 Mediums

`GET /api/v1/school-admin/academics/mediums`

```json
{
  "items": [{ "id": 1, "name": "English" }, { "id": 2, "name": "Hindi" }],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

### 3.4 Classes — list / create / detail / PATCH

`GET /classes?medium_id=1`

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

`POST /classes` → `201`

```json
{ "name": "Grade 1", "medium_id": 1, "include_semesters": 0 }
```

`GET /classes/3`

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

`PATCH /classes/3`

```json
{ "name": "Grade 1A" }
```

### 3.5 Sections — filtered list / create

`GET /sections?class_id=3`

```json
{
  "items": [
    {
      "id": 2,
      "name": "A",
      "class_id": 3,
      "class_name": "Grade 1",
      "medium_id": 1,
      "class_section_id": 10
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

`POST /sections` → `201`

```json
{ "name": "A", "class_id": 3 }
```

### 3.6 Subjects — list by class / association replace

`GET /subjects?class_id=3&medium_id=1`

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

`PUT /subjects/9/classes`

```json
{ "class_ids": [3, 4] }
```

Response shape: same as subject detail with updated `classes[]` (and/or list envelope from replace — clients should use returned body as source of truth).

### 3.7 Teachers list

`GET /academics/teachers`

```json
{
  "items": [
    {
      "id": 41,
      "name": "Priya Sharma",
      "first_name": "Priya",
      "last_name": "Sharma",
      "email": "priya.sharma@example.school",
      "mobile": "9000000001",
      "status": 1
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 3.8 Teacher assignment — create / list item

`POST /teacher-assignments` → `201`

```json
{
  "teacher_id": 41,
  "subject_id": 9,
  "class_id": 3,
  "section_id": 2,
  "session_id": 5
}
```

Compat aliases accepted: `class_section_id`, `session_year_id`.

```json
{
  "id": 17,
  "teacher_id": 41,
  "staff_id": 8,
  "teacher_name": "Priya Sharma",
  "subject_id": 9,
  "subject_name": "Math",
  "class_section_id": 10,
  "class_id": 3,
  "class_name": "Grade 1",
  "section_id": 2,
  "section_name": "A",
  "session_year_id": 5,
  "session_id": 5,
  "session_name": "2026-27",
  "name": "Priya Sharma / Math"
}
```

### 3.9 Error samples

**401 Unauthorized**

```json
{ "detail": "Not authenticated" }
```

**403 Forbidden (missing permission)**

```json
{ "detail": "Permission denied" }
```

**404 Not found (or other-school concealment)**

```json
{ "detail": "Record not found" }
```

**409 Conflict**

```json
{ "detail": "A class with this name already exists for the medium" }
```

```json
{ "detail": "This teacher assignment already exists" }
```

**422 Validation (Pydantic)**

```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "school_id"],
      "msg": "Extra inputs are not permitted",
      "input": 99
    }
  ]
}
```

**422 Business rule (string detail)**

```json
{ "detail": "Class medium does not match the subject medium" }
```

---

## 4. Dependent dropdown mapping

No new “options” endpoints are required for the flows below if existing list endpoints are used with the filters shown. Prefer **direct** paths where available.

| # | UI dependency | Endpoint | Required params | Option `id` | Display label | Empty / errors |
|---|---|---|---|---|---|---|
| 1 | Academic session | `GET /sessions` (compact) **or** `GET /academics/sessions` | none / `q,page` | `id` | `name` (mark `default===1`) | Empty `items` → disable dependent fields; 401/403 as usual |
| 2 | Medium | `GET /academics/mediums` | `q,page,page_size` | `id` | `name` | Create medium via same resource if school has none |
| 3 | Class (after medium) | `GET /classes?medium_id={id}` | `medium_id` | `id` | `name` | Wrong-school medium → **404**; empty → prompt create class |
| 4 | Section (after class) | `GET /sections?class_id={id}` | `class_id` | `id` (section) + use `class_section_id` when posting assignments | `name` | Foreign class → **404** |
| 5 | Subject (after class and/or medium) | `GET /subjects?class_id={id}&medium_id={id}` | prefer both when known | `id` | `name` (optional `code`) | Unmapped class returns empty list (not error) if class is owned |
| 6 | Teacher | `GET /academics/teachers` | `q,page,page_size` | `id` (= `teacher_id`) | `name` | Needs `teachers.manage` |
| 7 | Assignment combo | compose from 1–6; submit `POST /teacher-assignments` | `teacher_id`,`subject_id`, and either `class_id`+`section_id` or `class_section_id`; optional `session_id` | — | — | 422 if class/section not linked or subject not mapped; 409 duplicate |

### Loading / pagination notes for dropdowns

- Default `page_size=20`. For long catalogs, either raise to 50 or implement typeahead with `q`.
- Compact `/sessions` returns **all** non-deleted sessions (no page). Prefer it for session pickers.
- Do **not** filter by school on the client for security — backend already scopes by token.
- Soft-deleted rows never appear in active lists.

### New endpoint needed?

| Proposal | Verdict |
|---|---|
| Dedicated `/options/classes` etc. | **Not needed** — existing filtered lists suffice |
| Direct `/mediums` or `/teachers` | **Optional convenience** — needs agreement; academics paths work today |
| Return roles/permissions on `GET /me` | **Useful for menus** — currently documented gap; needs agreement |
| Revive soft-deleted teacher assignment | **Not implemented** — needs agreement if UI needs undo |

---

## 5. Validation & error handling cheat sheet

| Status | Typical cause |
|---|---|
| 401 | Missing/invalid/revoked token |
| 403 | Wrong role, inactive account/school, missing permission, subscription gate |
| 404 | Missing/soft-deleted row **or** foreign-school resource/filter id |
| 409 | Duplicate name/code/mapping/assignment |
| 422 | Invalid body, extra fields, foreign refs in write body, medium mismatch, date order |

Frontend should treat **403 Permission denied** as “hide/disable module”, and **404** on detail as “gone or not yours” (do not leak cross-tenant existence).

---

## 6. Discrepancies & frontend assumptions to confirm

| # | Topic | Backend today | Confirm with Vishal |
|---|---|---|---|
| D1 | Prefer direct `/classes` etc. vs only `/academics/...` | Both work; docs prefer direct | Which base path will the panel call? |
| D2 | Section create semantics | Direct requires `class_id`; academics creates bare section | Panel must use direct create for class-linked sections |
| D3 | Subject `type` | `Theory` \| `Practical` only | UI must not send Compulsory/Elective |
| D4 | `teacher_id` | = `users.id` from `/academics/teachers`, not `staffs.id` | Confirm client stores `id` from teachers list |
| D5 | Assignment class/section | Prefer `class_id`+`section_id` together; or `class_section_id` | Which shape will forms send? |
| D6 | Soft delete UX | No hard delete; no revive for assignments | Is soft-delete enough for “Remove”? |
| D7 | Compact vs full sessions | `/sessions` omits dates | Does session picker need dates? |
| D8 | `GET /me` permissions | Roles/permissions not returned | Will UI hardcode menus or need `/me` enrichment? |
| D9 | Migrations 0017–0022 | Applied on local app DB (`eschool_saas_v1`, `APP_ENV=local`) to head `20261021_0022`; **not** assumed applied on staging/production | Confirm each environment’s Alembic revision before relying on DB unique indexes |
| D10 | Class detail nested ids | `sections[].id` is **class_section** id; `section_id` is section catalog id | Confirm which id UI binds in forms |

---

## 7. Breaking-change & compatibility notes

- **Do not remove** `/academics/{resource}` CRUD; existing clients may depend on it.
- Direct routes are additive. Prefer them for new School Admin UI code.
- Response field names (`session_id` / `session_year_id` dual expose) are intentional aliases — keep both.
- Changing uniqueness rules or requiring Compulsory/Elective would be breaking; do not implement without agreement.
- Applying migrations 0017–0022 changes DB constraints; run preflight duplicate checks first (see ACADEMICS_API.md).

---

## 8. Questions for Vishal (precise)

1. Will new School Admin academic screens call **direct** paths (`/classes`, `/sections`, `/subjects`, `/teacher-assignments`) exclusively, with academics reserved for mediums/teachers/sessions CRUD?
2. For session pickers, is compact `GET /sessions` (`id`/`name`/`default`) sufficient, or do you need dates on the same response?
3. Confirm subject type UI: **Theory / Practical** only — correct?
4. For teacher assignment forms: will you send `{class_id, section_id}` or `{class_section_id}`?
5. Do you need `roles`/`permissions` on `GET /school-admin/me` before wiring menus?
6. Should soft-deleted teacher assignments be revivable, or is permanent soft-remove OK?
7. Preferred empty-state: auto-redirect to “create medium/class” vs inline create dialogs?
8. Max catalog size expectation — is `page_size=50` enough for dropdowns, or do you need a dedicated unpaginated options endpoint?

---

## 9. Status summary for coordination

| Area | Contract status |
|---|---|
| Sessions, mediums, classes, sections, subjects, class-subjects, teachers, teacher-assignments | **Implemented & documented** |
| Auth / RBAC / tenant isolation | **Implemented & documented** (Phase 9) |
| Dedicated options endpoints | **Deferred** — not required until Vishal confirms gap |
| `GET /me` roles/permissions | **Proposed** — needs agreement |
| Direct `/mediums`, `/teachers` | **Proposed** — optional; academics paths exist |
| Frontend TypeScript / clients | **Out of scope for this phase** (backend docs only) |

**Approval:** This document is prepared for Vishal’s review. Approval has **not** been recorded in this repository.
