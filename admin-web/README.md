# Admin Next.js (`admin-web`)

Phase 8 scaffold: Next.js 15 App Router + React 19 admin UI calling FastAPI `/api/admin`.

## Local run

```bash
cd admin-web
npm install
npm run dev
```

- UI: `http://127.0.0.1:3000`
- FastAPI: `http://127.0.0.1:8001` (Laravel keeps `8000`)
- Rewrites: `/api/v1/*` and `/api/admin/*` → `${BACKEND_URL}/...`

Optional env:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BACKEND_URL` | `http://127.0.0.1:8001` | Server-side rewrite target |
| `NEXT_PUBLIC_ADMIN_API_URL` | `/api/v1` | Browser client base (same-origin preferred) |

## Netlify deploy

Repo root has `netlify.toml` (`base = admin-web`, `@netlify/plugin-nextjs`).

In Netlify → Site configuration → Environment variables, set:

| Variable | Example |
| --- | --- |
| `BACKEND_URL` | `https://eschool-backend-8322.onrender.com` |
| `NEXT_PUBLIC_ADMIN_API_URL` | `/api/v1` |

Do not set Publish directory to `.next` or `out`. Trigger a new deploy after pushing these changes.

## Non-negotiables

- Call `/api/admin` JSON APIs only from this app.
- Do not replace Flutter bearer tokens with admin cookies on mobile `/api/*` paths.
- Prototype reference (not production): Laravel-archive `frontend/` — copy modules only after Phase gates.
- Frozen public origins stay on the reverse proxy; temporary FastAPI hostnames must never leak into payloads.

## Module status

| Module | Route | FastAPI | Status |
| --- | --- | --- | --- |
| Auth / session | `/login` | `POST /api/admin/login`, `POST /logout`, `GET /me` | Done (scaffold) |
| Dashboard | `/` | `GET /api/admin/dashboard` | Done (scaffold) |
| Students | `/students` | `GET /api/admin/students` | Done (scaffold) |
| Classes | `/classes` | `GET /api/admin/classes` | Done (scaffold) |
| Subjects | `/subjects` | `GET /api/admin/subjects` | Done (scaffold) |
| Attendances | `/attendances` | `GET /api/admin/attendances` | Done (scaffold) |
| Exams | `/exams` | `GET /api/admin/exams` | Done (scaffold) |
| Fees | `/fees` | `GET /api/admin/fees` | Done (scaffold) |
| Announcements | `/announcements` | `GET /api/admin/announcements` | Done (scaffold) |
| Leaves | `/leaves` | `GET /api/admin/leaves` | Done (scaffold) |
| Expenses | `/expenses` | `GET /api/admin/expenses` | Done (scaffold) |
| Schools | `/schools` | `GET /api/admin/schools` | Done (scaffold) |
| Packages | `/packages` | `GET /api/admin/packages` | Done (scaffold) |
| Settings | `/settings` | — | Placeholder |
| Payroll | — | — | Pending |
| Transport | — | — | Pending |
| Provisioning | — | — | Pending |
| Backups | — | — | Pending |
| Installer | — | — | Pending |

Read-only list/dashboard shells only. Create/update/delete UIs wait on write contracts and ownership gates.

## Auth

Middleware checks the `eschool_session` cookie (set by FastAPI login) and redirects unauthenticated users to `/login`. Logged-in users hitting `/login` are sent to `/`.

## Gate

Blocked on Phases 3–4 (FastAPI foundation + admin auth) and Phase 0 datasets for realistic fixture-backed UI tests. See [PHASE8_STATUS.md](../PHASE8_STATUS.md).
