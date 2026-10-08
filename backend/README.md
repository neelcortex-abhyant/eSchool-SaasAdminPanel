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

Docs:
- [docs/RENDER.md](docs/RENDER.md) — Render env vars
- [docs/DATA_MIGRATION.md](docs/DATA_MIGRATION.md) — MySQL import status (pending without dumps)
- [docs/PHASE9_AUDIT.md](docs/PHASE9_AUDIT.md) — payments **BLOCKED / DEFERRED** (no gateway)
- [docs/PHASE10_SECURITY.md](docs/PHASE10_SECURITY.md) — auth model, roles, isolation, security
- [docs/PHASE10_REPORT.md](docs/PHASE10_REPORT.md) — Phase 10 final report

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
