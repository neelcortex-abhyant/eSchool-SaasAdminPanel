# Phase 8 status — Admin Next.js

## Status: SCAFFOLD

Minimal App Router project created under `admin-web/`. Module ports not started.

## Delivered this pass

| Item | Path |
| --- | --- |
| package.json (Next 15 + React 19) | `admin-web/package.json` |
| next.config.ts (rewrite → FastAPI `/api/admin`) | `admin-web/next.config.ts` |
| tsconfig + next-env | `admin-web/tsconfig.json`, `admin-web/next-env.d.ts` |
| Root layout (Bootstrap CDN) | `admin-web/app/layout.tsx` |
| Home + login shell | `admin-web/app/page.tsx`, `admin-web/app/login/page.tsx` |
| middleware stub | `admin-web/middleware.ts` |
| API client → `/api/admin` | `admin-web/lib/api.ts` |
| Module port order README | `admin-web/README.md` |

## Checklist

- [x] Scaffold App Router admin-web
- [x] `npm install` succeeded (deps present under `admin-web/node_modules`)
- [ ] Local `npm run dev` smoke against FastAPI :8001
- [ ] Module ports (dashboard → students → academics → attendance → exams → fees → schools → more)
- [ ] Session cookie contract aligned with FastAPI admin auth
- [ ] UI tests against golden `/api/admin` fixtures

## Gate: BLOCKED on earlier phases

| Dependency | Why |
| --- | --- |
| Phase 0 datasets + frozen origins | Realistic admin data + media URLs |
| Phase 3 FastAPI foundation | Backend process, tenant DB, no DDL |
| Phase 4 auth / `/api/admin` login | Login shell has nowhere production-ready to land |
| Phase 6 payments (for Fees module) | Fee admin writes need webhook-safe ownership |

Do not treat the login shell as production evidence. Prototype archive `frontend/` remains reference-only.
