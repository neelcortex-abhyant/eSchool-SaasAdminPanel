# eSchool SaaS FastAPI backend

Migration home for the Laravel API replacement.

## Run locally

```bash
cd /Users/apple/eSchool-SaasAdminPanel/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

## Rules

- Default DB is MySQL (see `.env.example` / `ops/docker-compose.phase0.yml` ports 3307/6380).
- `ALLOW_DDL` must stay `false` outside unit tests. Production startup never calls `create_schema()`.
- Mobile writes are multipart (`Form`), not JSON.
- Login resources are still reduced vs Laravel `UserDataResource` — expand against golden fixtures (Phase 4 gate).
- Unported client routes return envelope stubs from `app/api/stubs.py` (not canary-ready).

## Tests

```bash
cd backend
ALLOW_DDL=true DB_CONNECTION=sqlite .venv/bin/pytest -q
```
