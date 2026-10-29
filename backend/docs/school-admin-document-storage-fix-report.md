# School Admin document storage fix report

Date: 2026-10-29. Companion to `school-admin-document-storage-audit.md`.
Nothing was deployed, committed or pushed. No production environment variable, Neon
database or migration was touched.

## 1. Confirmed root cause

`DOCUMENT_STORAGE_BACKEND` defaults to `none` (`app/core/config.py`), and
`document_storage.require_storage()` returns exactly the reported 503 in that state.
`docs/RENDER.md` and `.env.example` never listed the variable, so the Render service runs on
the default. Teacher creation does not use storage, which is why the teacher is saved and
only the files fail. (Render dashboard values could not be checked; see audit §2.)

A second, deeper issue: the only implemented backend writes to the local filesystem, and
Render's filesystem is ephemeral. Setting the two variables without a persistent disk would
make uploads "work" until the next restart or redeploy. After that the files are gone and
downloads return `404 Document file not found`.

## 2. Changes

| File | Change |
| --- | --- |
| `app/services/v1/document_storage.py` | `storage_config_error()` returns a specific reason: not configured, unsupported backend, path missing, path is a filesystem root, or path inside a public web root (`public`, `static`, `www`, `public_html`, `htdocs`, `wwwroot`). Quoted or mixed-case env values are tolerated. The root is created `0700` and files are written `0600` (POSIX), atomically via temp file + rename. `OSError` on root/write/read now gives `503 Document storage is unavailable` with no path and only an errno logged. Keys reject NUL, drive letters and empty values, and `build_key` allows only known extensions. New `discard()` provides best-effort compensating cleanup. |
| `app/services/v1/person_documents.py` | If saving metadata fails after the file write, the session is rolled back and the file is removed (no orphan). |
| `app/services/v1/school_homework.py` | Homework attachment: the 10-attachment check now runs **before** the write. Student submission: graded/limit checks run before the write. Both clean up the file if the commit fails. Inline 503 blocks replaced by `require_storage()` so the real reason is reported. |
| `app/services/v1/school_study_materials.py` | Create and replace remove the new file if the commit fails. Inline 503 blocks replaced by `require_storage()`. |
| `app/services/v1/school_people.py` | `owner_documents()` shared helper (student profile now uses it). |
| `app/services/v1/school_teachers.py`, `school_staff.py` | `GET /teachers/{id}` and `GET /staff/{id}` include `documents` (non-photo, same shape as the list items), as `PEOPLE_API_CONTRACT.md` requires. Additive only. |
| `app/schemas/v1/school_admin_core_responses.py` | `TeacherOut` / `StaffOut` OpenAPI schemas gain optional `documents`. |
| `app/api/v1/school_admin.py` | One `_download_response` for student/teacher/staff document and study-material downloads: ASCII `filename=` plus UTF-8 `filename*=` (fixes the 500 on non-Latin filenames), `nosniff`, `Cache-Control: private, no-store`. Photo responses get the same private headers. People upload routes return `413` (contract) for files over the 10 MB read cap; homework and study materials keep `422`. |
| `app/main.py` | At startup, logs `document_storage_unavailable reason=…` when uploads cannot work. |
| `.env.example`, `docs/RENDER.md` | Document the storage variables, the persistent-disk requirement and the single-instance trade-off. |
| `tests_offline/test_document_storage_offline.py` | New: 37 tests (see §5). |
| `tests/v1/test_school_admin_person_documents.py` | New DB-backed test: the profile lists persisted documents and the photo URL. |

No schema change and no migration. API changes are additive, apart from the oversize status
code on People uploads (422 → 413 above 10 MB, matching the contract; smaller oversize files
already returned 413).

## 3. Render configuration required (not applied)

1. Attach a **persistent disk** to the API web service (dashboard → service → Disks), for
   example mount path `/var/data`, size 1–5 GB. Disks need a paid instance type.
2. Set:

   | Variable | Value |
   | --- | --- |
   | `DOCUMENT_STORAGE_BACKEND` | `local` |
   | `DOCUMENT_STORAGE_PATH` | `/var/data/documents` (any directory under the disk mount) |
   | `DOCUMENT_MAX_IMAGE_BYTES` / `DOCUMENT_MAX_FILE_BYTES` | optional; defaults are fine |

3. Redeploy and check the boot log for the absence of `document_storage_unavailable`.

## 4. Persistence and remaining infrastructure

| Question | Answer |
| --- | --- |
| Do files survive restarts and redeploys today? | **No.** No disk is configured and uploads currently fail anyway. |
| With the variables set but no disk? | Uploads succeed, files are **lost** on restart or redeploy, and metadata survives in Neon (downloads then 404). Do not do this. |
| With a Render persistent disk? | Yes, files survive restarts and redeploys. Trade-offs: one instance only (no horizontal scaling), no zero-downtime deploys, and disk snapshots are Render's daily backups only. |
| Object storage? | Not implemented. Using S3/R2/GCS would need a new backend class behind `get_storage()` (same `put/get/delete` interface), a bucket, credentials and a dependency (e.g. `boto3`). None of these exist in the repo, so no credentials or settings were invented. |

## 5. Tests executed (local, Windows, Python 3.12, pytest 8.3.4)

| Command | Result |
| --- | --- |
| `python -m pytest tests_offline -q --tb=short` (baseline, before edits) | 55 passed, 1 failed |
| `python -m pytest tests_offline/test_document_storage_offline.py -q` | **37 passed** |
| `python -m pytest tests_offline -q --tb=short` (after) | **92 passed, 1 failed** |

The one failure is pre-existing and unrelated: `test_six_features_completion.py::test_announcement_lazy_publish_helper`
builds `publish_at` from local time (IST) while the service compares against UTC, so it
fails on any non-UTC machine. It was left unchanged.

The new offline route tests run the real FastAPI app against in-memory SQLite, overriding
only the DB session and the School Admin auth dependency. They cover:

- missing, partial, unsupported, quoted and public-root configuration
- an isolated tmp storage root, atomic writes, permissions and traversal rejection
- JPG, JPEG, PNG and PDF upload, metadata linkage and download
- JPEG/PNG profile photos and their replacement
- unsupported, spoofed and oversized files (413)
- multiple attachments shown on the profile after a "refresh" with a new client
- the 10-document cap with no orphan file
- cross-school upload, list, download, delete, photo and profile all returning 404
- unauthenticated requests returning 401
- a file missing on disk returning 404
- write errors (503, nothing persisted) and commit failures (file removed)
- non-ASCII filenames, the staff profile `documents` field, and orphan-free homework and graded-submission uploads

**Not run:** `tests/` and `tests/v1` (the Postgres integration suites, including the
new DB-backed test). `TEST_DATABASE_URL` is blank in `backend/.env`, so their conftest would
derive `eschool_saas_test` **on the production Neon host** and wipe its `public` schema. No
local Postgres or Docker is installed. To run them, point `TEST_DATABASE_URL` at a dedicated
Postgres (a separate Neon project or a local instance) and run `python -m pytest tests/v1 -q`.

## 6. Final status

Production behaviour cannot be verified without deploying. Everything below marked
Complete is backed by code and passing local tests only.

| Workflow | Local status | Production |
| --- | --- | --- |
| Storage configuration, validation and errors | Complete | Blocked: env vars + persistent disk not set |
| Teacher create with optional attachments | Complete | Blocked (storage) |
| Teacher photo (JPG/JPEG/PNG) | Complete | Blocked (storage) |
| Teacher documents (JPG/JPEG/PNG/PDF), list, download, delete | Complete | Blocked (storage) |
| Teacher profile `documents` | Complete (offline tests; DB test written, not run) | Needs deploy |
| Staff photo/documents/profile | Complete (offline tests cover upload + profile; download shares the teacher code path) | Blocked (storage) |
| Student photo/documents | Partial: shared code fixed, no new student-specific offline test; existing DB tests not run | Blocked (storage) |
| Homework brief attachments | Partial: orphan fix tested; no download route exists (none required by contract) | Blocked (storage) |
| Student submission attachments | Partial: orphan fix tested; no download route | Blocked (storage) |
| Study materials file upload/download | Partial: commit-failure cleanup and header fix added, but no new test for those paths; existing DB tests not run | Blocked (storage) |
| Cross-school isolation for person documents | Complete | Needs deploy |

## 7. Remaining blockers

1. **Render**: attach a persistent disk and set `DOCUMENT_STORAGE_BACKEND=local` and
   `DOCUMENT_STORAGE_PATH=/var/data/documents`. Without the disk, files will not survive redeploys.
2. **Isolated test database** for `tests/v1`. It is currently unsafe to run from this machine.
3. Contract items not implemented: photo re-encoding (EXIF strip), malware scanning,
   short-lived signed URLs (bearer-authenticated API paths are used instead), and homework
   attachment download.
4. Files uploaded before a persistent disk exists (if any were ever written to Render's
   ephemeral disk) are already gone. Their `person_documents` rows were left untouched, as
   instructed, and will return 404 on download.
