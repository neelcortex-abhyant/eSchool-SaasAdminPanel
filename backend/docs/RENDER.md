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

### Document storage (teacher/staff/student files, homework, study materials)

| Variable | Required for uploads | Notes |
| --- | --- | --- |
| `DOCUMENT_STORAGE_BACKEND` | **Yes** | `local`. The default `none` makes every upload return `503 Document storage is not configured`. |
| `DOCUMENT_STORAGE_PATH` | **Yes** | Absolute path on a Render **persistent disk**, for example `/var/data/documents` with the disk mounted at `/var/data`. Must not be inside a `public`/`static`/`www` directory. |
| `DOCUMENT_MAX_IMAGE_BYTES` | Optional | Default `5242880` (People uploads are further capped at 2 MB) |
| `DOCUMENT_MAX_FILE_BYTES` | Optional | Default `10485760` (People uploads are further capped at 5 MB) |

Render's normal filesystem is ephemeral: anything written outside a persistent disk is
lost on restart and redeploy, while the `person_documents` rows survive in Neon, so
downloads then return `404 Document file not found`. Setting the path alone is not
enough. Attach a persistent disk first (paid instance types only). A disk limits the
service to a single instance and disables zero-downtime deploys. There is no object
storage (S3/R2/GCS) backend in this codebase; using one would need new code.

At boot the service logs `document_storage_unavailable reason=…` when uploads cannot work.

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

## Health checks

- `GET /health` — liveness (no DB open)
- `GET /ready` — requires `NEON_DATABASE_URL`
