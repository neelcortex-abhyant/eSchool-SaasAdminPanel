# Teacher Portal — Authentication & Errors (Frontend Handoff)

## Overview

Teacher teaching APIs live under `/api/teacher/*` (see OpenAPI tag `teacher-portal`).
They are **separate** from school-admin panel routes under `/api/v1/school-admin/*`.

| Audience | Auth | Base path |
|----------|------|-----------|
| Teacher app | Personal access token (PAT) from teacher/staff login | `/api/teacher/...` |
| School admin panel | V1 JWT + RBAC (`teachers.manage`, `exams.manage`, …) | `/api/v1/school-admin/...` |
| Student / parent | Student or Guardian PAT | `/api/student/...`, `/api/parent/...` |

Teachers do **not** receive school-admin panel permissions by using the teacher portal.

## How to authenticate as a teacher

1. Login: `POST /api/teacher/login` (form: `email`, `password`, `school_code`).
2. Store the returned bearer token (format `tokenId|plain`).
3. Call teacher portal routes with:
   - `Authorization: Bearer <token>`
   - `school-code: <school code>` (required header)

Identity is always taken from the verified token. Clients must **not** send
`teacher_user_id`, `staff_id`, `school_id`, or evaluator/actor fields; request
bodies use `extra=forbid` and the server forces the authenticated teacher.

## Who may use `/api/teacher/*`

All of the following are required:

- Valid, non-expired PAT for a user in the school identified by `school-code`
- Spatie role **Teacher**
- A `Staff` row for that user in the same school
- `User.status == 1` and school not deactivated
- `Staff.employment_status` not `resigned` or `terminated`

**`on_leave`:** still allowed. Product convention (`school_teachers`) treats
employment status as business metadata; login/access is gated by `User.status`
except that the teacher portal additionally blocks resigned/terminated. Changing
`on_leave` behavior is a product decision.

Staff or Driver accounts **without** the Teacher role receive unauthorized
responses on teacher portal routes even if they can log in via `/api/teacher/login`
(that login accepts broader staff roles).

## Offline exam schedules (marks)

Teacher mark entry/correction requires the schedule’s `teacher_user_id` to equal
the authenticated teacher. Schedules with `teacher_user_id` unset are **not**
writable on the teacher portal (school-admin can assign a teacher or enter marks
on school-admin APIs). Matching subject assignment alone is not ownership.

## Error response shapes

### A. Mobile / PAT dependency failures → HTTP **200** + Laravel-style envelope

Used when `require_tenant_user` / `require_teacher_user` raise `ApiError`
(missing `school-code`, bad/expired token, wrong school, missing Teacher role,
resigned/terminated, inactive account):

```json
{
  "error": true,
  "message": "Unauthenticated. | Unauthorized Access | …",
  "data": null,
  "code": <int>,
  "details": ""
}
```

Frontend should treat `error: true` (or known messages) as auth failure even when
HTTP status is 200. This matches existing mobile API conventions and was **not**
changed in the teacher-portal hardening work.

### B. Business / validation failures → HTTP **4xx** with FastAPI `detail`

Used when the handler raises `AcademicError` (or Pydantic validation fails):

- `404` — resource not found / not owned / not assigned to this teacher
- `422` — validation (marks range, unassigned subject, published exam, bulk row errors, …)
- `409` — conflicts (where applicable on shared services)
- `503` — document storage not configured (uploads)

Example: `{"detail": "Record not found"}`.

### C. School-admin JWT on `/api/teacher/*`

A V1 school-admin access token is **not** a personal access token. Calls to
`/api/teacher/*` with only an admin JWT fail tenant PAT authentication (envelope
in section A). Use `/api/v1/school-admin/...` for admin operations.

## Suggested FE checks

1. Always send `school-code` with teacher PAT calls.
2. On any teacher portal response: if `error === true`, force re-login / school selection.
3. On HTTP 404 for homework/materials/schedules/assessments, treat as “not yours / not found”.
4. After creating offline exam schedules from admin UI, set `teacher_user_id` before
   expecting the teacher app to enter marks.
