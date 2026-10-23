# School Admin people API contract

> **For Nitish.** These are the routes and JSON shapes the admin-web Students, Parents, Teachers and Staff pages need. The pages are built and run on sample data (`admin-web/lib/people/mock.ts`, which follows every rule below) until these routes are on Render. No backend code comes with this document.
>
> **Your tables.** JSON field names don't have to match column names. They can map onto your migrations 0023–0031, for example:
> - `employee_code` ← `staffs.employee_id`
> - `status` on students ← `students.enrollment_status`
> - `department`, `designation`, `joining_date`, `employment_type` ← your staff employment, department and designation columns
> - guardians ← your `student_guardians` table
> - documents and photos ← `person_documents` (`owner_user_id`, `category`)
>
> **What exists today** (deployed, used by the pages' current live adapter in `admin-web/lib/people/http.ts`):
> - `GET/POST /api/v1/school-admin/academics/students` and `PATCH .../students/{id}`: list with `page` and `q`, create with an existing `guardian_id`, edit some fields and `status`.
> - `GET/POST /api/v1/school-admin/academics/parents`: list and create (name, email, mobile).
> - `/api/v1/school-admin/teachers` and `/api/v1/school-admin/staff` (added in 446a69d): list with filters, create (with a password), profile, PATCH, `/status`, `/photo` and `/documents` (categories: resume, id_proof, certificate, other). The Teachers and Staff pages use these. Employment uses `employment_status` (active, on_leave, resigned, terminated) in place of the employment type below, and there's no departments route, so the pages build that list from the records.
>
> **What's missing:**
> - Student profile (`GET /students/{id}`) and the student fields dob, gender, mobile, addresses.
> - Server-side filters and sorting on the student list.
> - Guardian link and unlink with several guardians per student.
> - Parent profile, edit and status.
> - Student photo and document uploads.
>
> **Switching a module to live.** Set `NEXT_PUBLIC_PEOPLE_API_MODE` per module, for example `students:live,parents:live,teachers:mock,staff:mock`, in `netlify.toml` (deployed) and `admin-web/.env.local` (local). The client that calls the routes below exactly as written is in commit `b25aff1` (`admin-web/lib/people/http.ts`). Restore it, or adapt the current file, when the routes ship.

This is the contract the School Admin Students, Parents, Teachers and Staff pages expect. The UI code is in `admin-web/lib/people/http.ts`. Until a module's endpoints are deployed, its pages use mock data that follows these same rules (`admin-web/lib/people/mock.ts`).

The routes live under the existing School Admin prefix. They don't use a separate `/api/v1/school/...` tree.

Base path: `/api/v1/school-admin`

## Auth and data isolation

- Every route uses `Authorization: Bearer <session token>` and `require_school_admin`.
- The school is always `auth.user.school_id`. The UI never sends `school_id`. Request bodies should use `extra="forbid"` so a stray `school_id` is rejected.
- A record id from another school returns `404 {"detail":"Record not found"}`, the same as a missing record. This applies to students, parents, teachers, staff, documents and guardian links.
- A referenced id from another school returns `422` on that field. Examples are `class_section_id`, `session_year_id`, `guardian.parent_id`, `parent_id` and `students[].student_id`.
- A teacher id under `/staff/{id}`, or a staff id under `/teachers/{id}`, returns `404`.

## Status of each route

| Route | Today | Needed |
|---|---|---|
| `GET/POST /academics/students`, `PATCH /academics/students/{id}` | Exists. Single `guardian_id`, few fields | **Move** to `/students` with the shapes below |
| `GET/POST /academics/teachers`, `GET/POST /academics/parents` | List and create only | **Move** to `/teachers` and `/parents`, then add profile, edit and status |
| `/staff` | Missing | **New**. Staff and teachers share the `staffs` table and need an `employee_type` column |
| `/students/{id}/guardians` | Missing | **New**. Needs a `student_guardians` table, so a student can have several guardians and a parent several children |
| Photo and document uploads | Missing | **New**. Needs a `documents` table and file storage |

Keep the old `/academics/...` routes until the admin build has switched every module to live.

The admin-web build chooses live or mock per module with `NEXT_PUBLIC_PEOPLE_API_MODE`, for example `students:live,parents:live`. Switch a module to live once its rows in this table are done.

## Database changes

- `students`: add `status` (int, default 1). Add a unique index on `(school_id, admission_no)` and a partial unique index on `(school_id, session_year_id, class_section_id, roll_number)` where `roll_number` is not null. Keep `guardian_id` in sync with the primary guardian during the transition.
- `users`: already has `dob`, `gender`, `image`, `current_address`, `permanent_address`, `occupation` and `status`. The `(school_id, email)` unique index already covers duplicate emails.
- `student_guardians` (new): `student_id`, `parent_id` (users.id), `relationship` (`Father|Mother|Guardian|Grandparent|Sibling|Other`), `is_primary` (bool) and `school_id`. Unique `(student_id, parent_id)`. At most 4 rows per student, and exactly one primary.
- `staffs`: add these columns:
  - `employee_type` (`teacher|staff`)
  - `employee_code`, unique per school
  - `department`
  - `designation`
  - `joining_date`
  - `employment_type` (`Permanent|Probation|Contract|Part-time`)
- `documents` (new): `id`, `school_id`, `owner_type` (`student|teacher|staff`), `owner_id`, `title`, `file_name`, `content_type`, `size` and `storage_key`.

## Lists

Every list returns:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20 }
```

All lists take `page` (default 1), `page_size` (1–50, default 20), `q` (case-insensitive partial match) and `status` (`1` or `0`, omit for both). Filters combine.

## Errors

These are the same shapes as the rest of v1.

| Status | Body |
|---|---|
| 401 | `{"detail":"Not authenticated"}`. The UI shows a sign-in link |
| 403 | `{"detail":"Forbidden"}` or `{"detail":"School access is suspended"}` |
| 404 | `{"detail":"Record not found"}` |
| 409 | A sentence the UI shows as is, for example `{"detail":"Admission number ADM20260001 is already used by Aarav Sharma"}` |
| 413 / 415 / 422 on uploads | `{"detail":"Only PDF, JPG and PNG files are allowed"}` |
| 422 | Pydantic list. The UI places each message next to the field named by `loc`. Nested fields keep their path: `["body","guardian","email"]` shows under the new-guardian email field, not the student email field |

## Students

### List row (`GET /students`)

```json
{
  "id": 41, "admission_no": "ADM20260015", "first_name": "Riya", "last_name": "Sharma", "name": "Riya Sharma",
  "session_year_id": 2, "session_name": "2026-27", "class_id": 3, "class_name": "Class 5",
  "class_section_id": 5, "section_name": "B", "roll_number": null,
  "guardian_name": "Rajesh Sharma", "guardian_mobile": "9830111137",
  "admission_date": "2026-04-02", "photo_url": null, "status": 1
}
```

`guardian_name` and `guardian_mobile` come from the primary guardian.

Filters:
- `session_year_id`, `class_id`, `class_section_id` and `parent_id`. With `parent_id`, the list returns that parent's linked students.
- `q` matches the name or admission number.
- `status`.
- `sort` is `name`, `admission_no`, `admission_date` or `class`. `order` is `asc` or `desc`, and the default is `name asc`.

### Profile (`GET /students/{id}`)

The profile is the list row plus these fields:

```json
{
  "dob": "2016-12-05", "gender": "female", "email": null, "mobile": null,
  "current_address": "12, Lake View Road, Pune", "permanent_address": null,
  "guardians": [
    { "parent_id": 301, "name": "Rajesh Sharma", "email": "rajesh@example.com", "mobile": "9830111137", "relationship": "Father", "is_primary": true }
  ],
  "documents": [
    { "id": 9, "title": "Birth certificate", "file_name": "birth-certificate.pdf", "content_type": "application/pdf", "size": 48211, "url": "https://…signed…", "uploaded_at": "2026-10-21T08:40:00Z" }
  ]
}
```

`gender` is `male`, `female` or `other`. `photo_url` and document `url` are short-lived signed links. They are never public bucket paths.

### Admission (`POST /students`)

Returns `201` and the profile.

```json
{
  "first_name": "Riya", "last_name": "Sharma", "dob": "2016-12-05", "gender": "female",
  "admission_no": "ADM20260015",
  "admission_date": "2026-10-21", "session_year_id": 2, "class_section_id": 5, "roll_number": null,
  "email": null, "mobile": null, "current_address": "…", "permanent_address": "…", "status": 1,
  "guardian": { "parent_id": 301, "relationship": "Father" }
}
```

`admission_no` is optional. When it's left out, the server generates `ADM{year}{seq:04}` from the admission date. Generate it inside the transaction so two admins can't get the same number.

`guardian` is either `{ "parent_id", "relationship" }` for an existing parent, or the details of a new parent: `{ "first_name", "last_name", "email", "mobile", "relationship" }`. The student, any new parent user and the primary `student_guardians` row are created in one transaction.

Validation returns `422` on the named field:
- `first_name` and `last_name` are required, with at most 128 characters each.
- `dob` is required, not in the future, and the student is 2 to 30 years old.
- `gender` is required.
- `admission_date` is after `dob`.
- `session_year_id` belongs to the school.
- `class_section_id` belongs to the school, the section and its class are active, and the class runs in that session (its `session_year_id` is null or equal).
- `admission_no` uses only letters, digits, `-` and `/`, with at most 32 characters.
- `roll_number` is between 1 and 9999.
- `email` and `mobile` are optional but must be valid when given. A valid `mobile` has 7 to 15 digits.
- `current_address` is required, with at most 512 characters.
- For a new guardian, names, email and mobile are required. The relationship must be one of the listed values.

Conflicts return `409`:
- An admission number that's already used.
- A roll number already used in the same section and session.
- A student email already used in the school.
- A new guardian whose email or mobile matches an existing parent. The message is "<name> is already registered with this email or phone number. Choose them as an existing parent instead."

### Update (`PATCH /students/{id}`)

The body is the same as admission without `guardian`, and `admission_no` is required. The same rules apply. A student whose class or section was later made inactive can be saved without changing their placement. Moving to a different section runs the full check. The response is the profile.

### Status (`PATCH /students/{id}/status`)

The body is `{ "status": 0 | 1 }` and the response is the profile. Deactivating also blocks the student's sign-in.

### Guardians

- `POST /students/{id}/guardians` takes `{ "parent_id", "relationship", "is_primary"?: bool }` and returns the profile.
  - It returns `409` if the parent is already linked, and `409` if the student already has 4 guardians.
  - The first link is primary. `is_primary: true` moves the primary flag to this link.
- `DELETE /students/{id}/guardians/{parent_id}` returns the profile.
  - It returns `409` if this is the student's only guardian, with the message "<student> must keep at least one parent or guardian. Link another one first."
  - Removing the primary guardian makes the next one primary.
- The parent pages also use these two routes to link and unlink children.

## Parents and guardians

A parent is a `users` row in the school that is linked through `student_guardians`, or created as a parent.

### Row and profile (`GET /parents`, `GET /parents/{id}`)

```json
{
  "id": 301, "first_name": "Rajesh", "last_name": "Sharma", "name": "Rajesh Sharma",
  "email": "rajesh@example.com", "mobile": "9830111137", "current_address": null, "occupation": "Engineer", "status": 1,
  "children": [
    { "student_id": 1, "name": "Aarav Sharma", "admission_no": "ADM20260001", "class_name": "Class 5", "section_name": "A", "relationship": "Father", "is_primary": true, "status": 1 }
  ]
}
```

Filters:
- `q` matches the name, email or mobile.
- `status`.
- `email` is an exact, case-insensitive match.
- `mobile` is an exact match on digits only.

The forms use `email` and `mobile` to warn about a duplicate before saving.

### Create (`POST /parents`)

The body is `{ "first_name", "last_name", "email", "mobile", "current_address"?, "occupation"?, "status", "students": [{ "student_id", "relationship" }] }`. It returns `201` and the profile.

- Email and mobile are required.
- An email or mobile that's already used by another parent returns `409`. The message names that parent and says to link students on their record instead.
- An email used by a student, teacher or staff member in the school returns `409`.
- Each `students[]` entry must belong to the school, can appear only once, and the student can't already have 4 guardians.

### Update and status

- `PATCH /parents/{id}` takes the same body without `students` and follows the same rules.
- `PATCH /parents/{id}/status` takes `{ "status" }`. Deactivating blocks the parent's sign-in and keeps their links.

## Teachers and staff

The routes are the same for both: `/teachers` and `/staff`. A record id is the user id, the same id `GET /academics/teachers` and teacher assignments use.

### Row (`GET /teachers`, `GET /staff`)

```json
{
  "id": 102, "employee_code": "TCH0002", "first_name": "Rahul", "last_name": "Mehta", "name": "Rahul Mehta",
  "email": "rahul.mehta@school.example", "mobile": "9710205406", "department": "Mathematics", "designation": "Teacher",
  "joining_date": "2016-06-01", "employment_type": "Permanent", "photo_url": null, "status": 1
}
```

Filters:
- `q` matches the name, employee code, email, mobile or designation.
- `department` is an exact, case-insensitive match.
- `employment_type`.
- `status`.

`GET /teachers/departments` and `GET /staff/departments` return `{ "items": ["Mathematics", "Science"] }`. These are the distinct department names in the school, used for the filter and as form suggestions.

### Profile (`GET /teachers/{id}`)

The profile is the row plus `gender`, `dob`, `qualification`, `current_address` and `documents` (same shape as for students). The teacher profile reads class and subject assignments from `GET /academics/teacher-assignments?teacher_id=`.

### Create and update

- `POST /teachers` or `POST /staff` returns `201`. `PATCH /{kind}/{id}` takes the same body.
- The body is `{ "employee_code"?, "first_name", "last_name", "email", "mobile", "gender"?, "dob"?, "qualification"?, "department", "designation", "joining_date", "employment_type", "current_address"?, "status" }`.
- `employee_code` is optional on create. When it's left out, the server generates `TCH0001` or `STF0001`. It's required on update.

Validation returns `422`:
- Names, email, mobile, department, designation, joining date and employment type are required.
- `qualification` is required for teachers only.
- When `dob` is given, the person must be at least 18, and `joining_date` must be after `dob`.

Conflicts return `409`:
- An employee code already used in the school.
- An email already used by anyone in the school.

### Status

`PATCH /{kind}/{id}/status` takes `{ "status" }`. Deactivating blocks sign-in and keeps the person's teacher assignments.

## Photos and documents

Owners are `students`, `teachers` and `staff`.

| Route | Body | Response |
|---|---|---|
| `POST /{owner}/{id}/photo` | multipart `file` | `{ "photo_url": "…" }` |
| `POST /{owner}/{id}/documents` | multipart `file`, `title` (at most 120 characters) | `201`, the document object |
| `DELETE /{owner}/{id}/documents/{document_id}` | none | `{ "deleted": true }` |

The UI uploads files only after the record is saved. A failed upload doesn't undo the save. The UI lists which files didn't upload and asks the admin to try again from Edit.

The server must enforce these rules even though the browser checks them first:
- A photo must be JPEG, PNG or WebP, at most 2 MB. A document must be PDF, JPEG or PNG, at most 5 MB. There can be at most 10 documents per record.
- Detect the type from the file's bytes, not its name or the `Content-Type` header. Reject anything else with `415`.
- Re-encode photos server side to strip metadata and any embedded content.
- Store files under random keys outside the web root, and return them only through short-lived signed URLs. Serve them with `Content-Disposition: attachment` for anything that isn't an image or PDF, and with `X-Content-Type-Options: nosniff`.
- Check that the owner and the document belong to the caller's school before reading or deleting (`404` otherwise).
- Scan uploads for malware if the storage provider supports it.

## Tests worth adding on the backend

- A School Admin from school B gets `404` for school A's students, parents, teachers, staff and documents, and gets `422` when referencing them in a body.
- A `school_id` in any body is rejected.
- Duplicate admission number, roll number, employee code, parent email and parent mobile each return `409`.
- Removing a student's only guardian returns `409`. Removing the primary guardian promotes the next one.
- An upload with a `.pdf` name but other bytes is rejected. Oversized files are rejected.
- Deactivated students, parents and employees can't sign in.
