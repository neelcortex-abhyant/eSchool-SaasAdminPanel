# Student Web API Contract Summary

Source: `Student Web Code/eSchool Sass student web v-1.11.0/src/lib/api/student/`

## Base URL

- `API_BASE_URL` = `${NEXT_PUBLIC_STUDENT_API_URL}/api` (from `endpoints.ts`)
- Axios instance `studentApi` in `axiosConfig.ts` uses that `baseURL`, timeout 10s, `withCredentials: false`
- Request interceptor attaches `Authorization: Bearer <token>` and `school-code` header when set
- Response interceptor maps custom API codes, handles 401 unauthenticated logout, and account-deactivation redirects

## Env vars

- **NEXT_PUBLIC_STUDENT_API_URL**: Public base origin for the student backend. All relative endpoint paths are resolved under `${NEXT_PUBLIC_STUDENT_API_URL}/api`. Required for static export (no Next.js API proxy). Declared in `.env`.
- **NEXT_PUBLIC_REVERB_URL**: WebSocket URL for Laravel Reverb / Pusher-protocol realtime chat. Used in `src/components/chat/ChatPage.tsx` via `new WebSocket(reverbUrl)`; subscribes to channel `user.{userId}` for live messages. Not an HTTP REST endpoint and not listed in `endpoints.ts`.

## Endpoint inventory

- Total defined in `endpoints.ts`: **60**
- All referenced from `functions.ts` (and LOGIN also from `axiosConfig.ts`): **60**
- By HTTP method: GET=42, POST=18
- By encoding: query=43, json=6, multipart=11

## Notable call patterns

- Most reads: `studentApi.get(path, { params })` → encoding `query`
- Auth + several transport/chat/assignment uploads: `FormData` + `studentApi.post` → encoding `multipart`
- Chat delete & assignment delete: comments say DELETE but runtime uses **POST**
- Public branding + tracking session: raw `fetch()` against absolute `API_BASE_URL` paths (no axios interceptors for branding; tracking uses `X-Tracking-Token` only)
- Manifest JSON: `contract-tests/manifest/student_web_endpoints.json`
