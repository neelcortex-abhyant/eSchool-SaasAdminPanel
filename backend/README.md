# eSchool SaaS FastAPI backend

Migration home for the Laravel API replacement.

## Run locally

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
cp .env.example .env           # then set NEON_DATABASE_URL
uvicorn app.main:app --reload --port 8001
```

## Single Neon database

All APIs use **one** `NEON_DATABASE_URL` (PostgreSQL via psycopg):

| Routes | Tables |
| --- | --- |
| `/api/v1/*` | `v1_users`, `auth_sessions` |
| `/api/student|parent|teacher|staff|admin/*` | legacy `users`, `schools`, … scoped by `school_id` |

School isolation is **logical** (`school_id` + school-code). Do not create per-school databases.

Super Admin school list: `GET /api/v1/super-admin/schools` keeps `page`, `page_size`, `status`, `code`, `name`, and `include_deleted`. `support_email` is an added case-insensitive partial match. Blank `support_email` is allowed and is not unique. A non-blank email must be valid and is unique ignoring case. Duplicate non-blank emails return `409` with `School email already in use`. Invalid non-blank emails return `422`. OpenAPI documents the query and field on the school schemas.

Docs:
- [docs/SCHOOL_API_CONTRACT.md](docs/SCHOOL_API_CONTRACT.md) — Super Admin school API for frontend integration
- [docs/DASHBOARD_API.md](docs/DASHBOARD_API.md) — Super Admin dashboard counts, charts, and activities
- [docs/SUBSCRIPTION_RENEWAL_API.md](docs/SUBSCRIPTION_RENEWAL_API.md) — Super Admin plans, school subscriptions, bills, renewal, expiry, and platform listing
- [docs/PEOPLE_API_CONTRACT.md](docs/PEOPLE_API_CONTRACT.md) — School Admin students, parents, teachers, staff, photos and documents
- [docs/RENDER.md](docs/RENDER.md) — Render env vars
- [docs/DATA_MIGRATION.md](docs/DATA_MIGRATION.md) — MySQL import status (pending without dumps)
- [docs/PHASE9_AUDIT.md](docs/PHASE9_AUDIT.md) — payments **BLOCKED / DEFERRED** (no gateway)
- [docs/PHASE10_SECURITY.md](docs/PHASE10_SECURITY.md) — auth model, roles, isolation, security
- [docs/PHASE10_REPORT.md](docs/PHASE10_REPORT.md) — Phase 10 final report

## People files

Photos and documents are stored privately (`FILE_STORAGE_BACKEND=local`, files under `FILE_STORAGE_DIR`, default `backend/var/uploads`, which git ignores). The API returns signed links to `GET /api/v1/files/{token}` that expire after `FILE_URL_TTL_SECONDS` (default 600). On Render the local disk is not persistent, so attach a disk at `FILE_STORAGE_DIR` or add an S3 backend in `app/services/v1/file_storage.py` before relying on uploads.

## Rules

- `ALLOW_DDL` must stay `false` outside tests. Production never calls `create_schema()`.
- Mobile writes are multipart (`Form`), not JSON.
- MySQL / PyMySQL / SQLite runtime fallbacks are removed.

## Tests (isolated Postgres only)

```bash
cd backend
# TEST_DATABASE_URL must point at a non-live DB (e.g. .../eschool_saas_test)
$env:ALLOW_DDL="true"
.\.venv\Scripts\python.exe -m pytest -q
```

Never point pytest at the live app database name.
