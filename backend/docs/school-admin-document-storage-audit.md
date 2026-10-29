# School Admin document storage audit

Date: 2026-10-29. Scope: every School Admin workflow that stores or serves a binary file,
plus the teacher/student portal routes that share the same storage. Source of truth: this
repository (`backend/`). `admin-web` was deleted on purpose. Its last version (commit
`984aadc`) was read from git history only, to check the client contract. It was not restored.

## 1. Storage architecture

| Item | Finding |
| --- | --- |
| Abstraction | `app/services/v1/document_storage.py`: `LocalDocumentStorage` (`put` / `get` / `delete`), `get_storage()`, `require_storage()`, magic-byte type detection, filename sanitising |
| Backends | **Only `local`** (private directory). No S3/R2/GCS/Azure code or dependency exists. |
| Configuration | `app/core/config.py`: `DOCUMENT_STORAGE_BACKEND` (default **`none`**), `DOCUMENT_STORAGE_PATH` (default empty), `DOCUMENT_MAX_IMAGE_BYTES` (5 MB), `DOCUMENT_MAX_FILE_BYTES` (10 MB) |
| Keys | Server-generated `{school_id}/{owner_user_id}/{uuid4}.{ext}`. Client filenames are stored only as sanitised metadata. |
| Metadata | `person_documents` table (migration 0029, `title` in 0037): `school_id`, `owner_user_id`, `category`, `storage_key`, `content_type`, `size_bytes`, `original_filename`, `deleted_at` (soft delete). Homework uses `attachments_json` and study materials use `study_materials.storage_key`. |
| Deployment config | No `render.yaml`, Procfile or Dockerfile. `docs/RENDER.md` and `.env.example` (before this fix) **did not mention any `DOCUMENT_STORAGE_*` variable**. No persistent disk is declared anywhere in the repo. |
| Static mounts | `app/main.py` mounts no `StaticFiles`, so stored files can only be reached through the authenticated routes below. |

## 2. Root cause of the production error

The message `Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local and
DOCUMENT_STORAGE_PATH …` comes from `document_storage.require_storage()`. That function
raises it whenever the backend is not `local` or the path is empty. The backend defaults to
`none`, and the Render runbook never told anyone to set either variable, so the deployed
service runs with the default. Teacher creation (`POST /teachers`) never touches storage, so
it succeeds. The client then uploads each file separately (`POST /teachers/{id}/photo` and
`/documents`), gets `503` for each one, and shows the "Changes saved, but some files didn't
upload" banner. The client behaves correctly. This is a configuration and documentation gap,
not a parsing bug.

I could not view the Render dashboard, so "the variables are unset" is inferred from the
code path and the docs. It is the only configuration that produces this exact message.
Before the fix, a value pasted with quotes (`"local"`) would also produce it. That case is
now accepted.

Setting the variables alone would make uploads succeed **but not persist**. Render's
filesystem is ephemeral, so files written outside a persistent disk disappear on restart or
redeploy while their `person_documents` rows remain.

## 3. Client/API contract check (admin-web @ 984aadc, read-only)

| Check | Result |
| --- | --- |
| Multipart field names | Client sends `file`, `title`, `category` and the API reads `file`, `title`, `category`. Match. |
| Teacher id after creation | Client uses `saved.id` from `POST /teachers`, which is `users.id`. The document routes use the same id. Match. |
| Upload response | Client reads `id`, `title`, `category`, `url`, `file_name`, `content_type`. `document_public_item` returns all of them. Match. |
| Document display | Client loads `GET /teachers/{id}/documents` and filters out `profile_photo`. Works. |
| Profile `documents` | The People contract (`PEOPLE_API_CONTRACT.md`, "Profile") requires `documents` on `GET /teachers/{id}`. **Missing for teachers and staff** before the fix (present for students). |
| Partial-failure messaging | Teacher save and file uploads are separate calls. The banner names each failed file and shows the server's `detail`. Accurate. |
| Photo display | `photo_url` / `image` is an authenticated API path (`/teachers/{id}/photo`). The client fetches it as a blob with the bearer token. Works. |

## 4. Workflow inventory (state before the fix)

Legend: Working = implemented and covered by tests; Partial = implemented with defects or
gaps; Broken = fails in normal use; Blocked = cannot work until external storage is set up.

| # | Workflow | Endpoints | Storage / persistence | AuthZ & tenancy | Retrieval | Defects found | Status (before) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Teacher create with optional attachments | `POST /school-admin/teachers`, then `POST /teachers/{id}/photo`, `/documents` | Record in `users`/`staff` and files in `person_documents` | `teachers.manage` permission; school id from session | n/a | Uploads return 503 in production | **Blocked** (storage config) |
| 2 | Teacher profile photo | `POST`/`GET /teachers/{id}/photo` | `person_documents` (`profile_photo`) and `users.image` set to the API path; previous photo soft-deleted and its file removed | `_owned_teacher` (same school + Teacher role), else 404 | Authenticated bytes | Missing `Cache-Control: private` | **Blocked** |
| 3 | Teacher documents (JPG/JPEG/PNG/PDF) | `POST/GET /teachers/{id}/documents`, `GET …/{doc}`, `GET …/{doc}/download`, `DELETE …/{doc}` | `person_documents`; 10-document cap; 2 MB image and 5 MB file limits; 415 on bad magic bytes | Owner and document both checked against the caller's school, else 404 | Authenticated download | File written before the DB commit with no cleanup on failure (orphans); non-ASCII filename in `Content-Disposition` gives 500 (latin-1); no `nosniff` on teacher/staff downloads; >10 MB returns 422 instead of the contract's 413; raw `OSError` gives opaque 500 | **Blocked / Partial** |
| 4 | Teacher profile shows documents | `GET /teachers/{id}` | n/a | as above | n/a | `documents` missing (contract gap) | **Partial** |
| 5 | Staff photo/documents/profile | `/school-admin/staff/{id}/photo`, `/documents…`, `GET /staff/{id}` | same as 2–4 | `_owned_non_teaching_staff` | same | same defects as 3–4 | **Blocked / Partial** |
| 6 | Student photo/documents (admission + edit) | `/school-admin/students/{id}/photo`, `/documents…` | same table; owner is the student's user | `resolve_student_owner_user_id` per school | same; profile already embeds `documents` | orphan and non-ASCII header defects | **Blocked / Partial** |
| 7 | Homework brief attachments (School Admin + teacher portal) | `POST /school-admin/homework/{id}/attachments`, `POST /teacher/homework/{id}/attachments` | `homework.attachments_json` holds `storage_key` (never returned) | homework owned by school | **No download route exists** (only `"stored": true` metadata). No contract requires one. | File written **before** the 10-attachment check, so the 422 left an orphan; no cleanup if the commit fails | **Partial** |
| 8 | Student homework submission attachments (student API) | `POST /student/homework/{id}/my-submission/attachments` | `homework_submissions.attachments_json` | student, class section and session must match | none (same as 7) | File written before the graded and limit checks, so orphans on 422 | **Partial** |
| 9 | Study materials (file resources) | `POST /school-admin/study-materials/upload`, `POST …/{id}/file`, `GET …/{id}/download`; teacher and student portal equivalents | `study_materials.storage_key`; refcounted delete | school, teacher assignment and section checks | Authenticated download with `nosniff` | No cleanup if the commit fails; non-ASCII filename gives 500 | **Blocked / Partial** |
| 10 | Generated PDFs (payslips, certificates, invoices) | `/payslips/{id}/pdf`, `/certificates/{id}/pdf` | Rendered on request; **not stored** | per school | inline | Not a storage workflow | Not applicable |
| 11 | Gallery / sliders | `/school-admin/gallery`, `/sliders` | Store an `image_url` string only; no binary upload exists | per school | n/a | Not a storage workflow | Not applicable |
| 12 | Super Admin backups | `BACKUP_STORAGE_PATH` | Separate local path | super admin | n/a | Same ephemeral-disk caveat; outside School Admin scope | Not audited further |

## 5. Security review (before the fix)

| Control | Finding |
| --- | --- |
| Type detection | Magic bytes (JPEG `FFD8FF`, PNG signature, `%PDF`, WebP RIFF, and DOC/DOCX for study materials). Extension and `Content-Type` are ignored. Good. |
| Size | Streaming read capped at 10 MB, then per-workflow caps. Good (status code inconsistent, see #3). |
| Path traversal | Keys are generated server-side and `_resolve` blocks `..` and escaping the root. Good. Hardened further to reject NUL, drive letters and empty keys. |
| Public web root | **No check.** A path such as `…/public/uploads` would be accepted. |
| Permissions | Directories and files were created with the process umask. No restriction. |
| Leakage | `storage_key` is never returned; clients only get download paths under `/api/v1/school-admin/…`. Filesystem errors were unhandled 500s (no path in the body, but not a clear error either). |
| Tenant isolation | Every read, download and delete resolves the owner within `auth.user.school_id` and matches `row.school_id` and `row.owner_user_id`. Cross-school access returns 404. Good. |
| Logging | No file contents or personal data logged. Good. |
| Not implemented (contract "should") | Photo re-encoding (EXIF strip), malware scanning, short-lived signed URLs. The current design uses bearer-authenticated API paths instead of signed URLs. |
