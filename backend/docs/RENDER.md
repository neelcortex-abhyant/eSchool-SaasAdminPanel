# Render deployment (single Neon PostgreSQL)

## Required environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `NEON_DATABASE_URL` | **Yes** | `postgresql+psycopg://…/eschool_saas_v1?sslmode=require` |
| `APP_ENV` | Yes | `production` |
| `SESSION_SECRET` | Yes | Strong random value |
| `ALLOW_DDL` | Yes | Must be `false` |
| `FRONTEND_ORIGIN` | Recommended | Comma-separated browser origins (localhost). Netlify `*.netlify.app` is allowed via CORS regex in `main.py`. |
| `V1_SESSION_TTL_MINUTES` | Optional | Default `10080` |

**Remove** obsolete MySQL variables if present: `DB_CONNECTION`, `DB_HOST`, `DB_PORT`,
`DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`. They are no longer read.

Never commit real credentials. Set secrets only in the Render dashboard.

## Tenancy model

One Neon database. Schools are isolated with `school_id` (+ school-code header / admin cookie).
`schools.database_name` is legacy metadata only.

## Auth stacks (not merged)

- `/api/v1/*` → `v1_users` + `auth_sessions` (UUID)
- `/api/student|parent|teacher|staff|admin/*` → legacy `users` + `personal_access_tokens` / cookie

## Deploy commands (after approval)

```bash
# IMPORTANT: unset TEST_DATABASE_URL in the shell so Alembic cannot target the test DB.
# Alembic only uses TEST_DATABASE_URL when ALLOW_TEST_MIGRATIONS=1.

# From backend/ against the TARGET database (staging first):
export NEON_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require'
unset TEST_DATABASE_URL
unset ALLOW_TEST_MIGRATIONS

# Confirm target before mutating:
python -c "from app.core.db_urls import safe_url_target, normalize_neon_database_url as n; import os; print(safe_url_target(n(os.environ['NEON_DATABASE_URL'])))"
alembic current

alembic upgrade head

# Start (Render start command example):
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Subscription expiry

Automatic expiry is not running in this deployment. The API process does not start a scheduler.

When an operator wants past subscriptions to become status `2`, schedule an external job against the already deployed API. The job sends:

`POST /api/v1/super-admin/subscriptions/expire-due`

with a Super Admin bearer token. Do not add a worker-local scheduler: more than one Render instance would run the same pass. The endpoint itself is safe to call again. It does not delete schools and it does not change `schools.status` or `schools.installed`.

Confirm the database target with the procedure above before `alembic upgrade head`. The unapplied head in the working tree includes `20261015_0011` and `20261016_0012`. This document does not mean those revisions have been applied.

## Health checks

- `GET /health` — liveness (no DB open)
- `GET /ready` — requires `NEON_DATABASE_URL`
