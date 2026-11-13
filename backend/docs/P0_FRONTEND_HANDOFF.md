# P0 hand-off for Vishal: admin-web changes that complete the login fix

The backend fixes are on branch `fix/p0-school-admin-auth-domain`. Four of the QA symptoms need a small admin-web change as well. No API breaks: every response change is additive.

## 1. Login spins forever on "Signing in…" (most important)

**Cause.** On 2026-11-12 a cold Render start took **83 s**, and a warm login about 2.7 s (Render is in Oregon, Neon in Singapore). `lib/backendProxy.ts` calls `fetch(target)` with no timeout, so the Netlify function waits until the platform kills it. The browser request stays pending, and the form never leaves "Signing in…". Because login never finishes, the `v1_session` cookie is never set, so a new tab is sent to `/login`.

**Change in `lib/backendProxy.ts`:**
```ts
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 25_000);
try {
  upstream = await fetch(target, { ...init, signal: controller.signal });
} catch (error) {
  const aborted = error instanceof Error && error.name === "AbortError";
  return NextResponse.json(
    { detail: aborted ? "The server is starting up. Please try again in a few seconds." : `Cannot reach backend … (${message})` },
    { status: aborted ? 504 : 502 },
  );
} finally {
  clearTimeout(timer);
}
```
Also forward the client address, so the backend's login rate limit is per user and not per Netlify IP. The backend reads it with `TRUSTED_PROXY_HOPS=2`:
```ts
const fwd = request.headers.get("x-forwarded-for");
const ip = request.headers.get("x-nf-client-connection-ip");
const chain = [fwd, ip].filter(Boolean).join(", ");
if (chain) headers.set("x-forwarded-for", chain);
```

The backend side is already done: `/health/ready` exists for a keep-warm ping, and DB connects time out after 10 s.

## 2. Session should survive refresh, a new tab and a browser restart

`lib/api.ts::setSession` sets `v1_session=1` with no `Max-Age`. That's a browser-session cookie, while the token in `localStorage` lasts 7 days. After a browser restart, middleware sends the user to `/login` even though the token is still valid. Pass `expires_at` from the login response:
```ts
export function setSession(accessToken: string, expiresAt?: string) {
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  const maxAge = expiresAt ? Math.max(0, Math.floor((Date.parse(expiresAt) - Date.now()) / 1000)) : 60 * 60 * 24 * 7;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${SESSION_COOKIE}=1; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
}
```
`LoginForm.tsx`: `setSession(result.data.access_token, result.data.expires_at)`.

## 3. Show the real reason when login is refused (403)

Login now returns **403** with a clear `detail` when the school can't use the panel. It used to return 200 and then fail on every page. Show `detail` as it is. `LoginForm` already does this through `apiErrorMessage` for non-500 errors, so check that the fallback "Invalid email or password." appears only on 401.

| Status | `detail` |
|---|---|
| 401 | `Invalid email or password` |
| 403 | `This school is waiting for approval. You can sign in after it is activated.` |
| 403 | `School access is suspended` |
| 403 | `This school has not finished setup. Ask the Super Admin to activate it, then sign in again.` |
| 403 | `Subscription access is not available` |
| 403 | `Account inactive` / `No school assigned` |
| 429 | `Too many attempts. Try again later.` (with a `Retry-After` header) |

## 4. Domain preview must not invent `.localhost`

`GET /api/v1/schools/subdomain-availability?slug=…` now returns `hostname` (e.g. `qa-sunrise-1105.schoolsarthi.com`) and `base_domain`. Registration, `by-host` and `by-code` also return `hostname`. Display `hostname` from the API. Set `NEXT_PUBLIC_SCHOOL_ROOT_DOMAIN=schoolsarthi.com` on Netlify so `lib/domains/core.ts` (host routing) agrees with the backend.

## Retest checklist (browser)

1. Sign in with the QA School Admin. You should land on `/school` within a few seconds when the backend is warm.
2. Refresh `/school`, open it in a new tab, then restart the browser and open it again. You should stay signed in each time.
3. Log out, then press Back or open `/school`. You should land on `/login`, and the old token should return 401.
4. Enter a wrong password. You should see "Invalid email or password" and the spinner should stop.
5. Registration preview should show `qa-sunrise-1105.schoolsarthi.com`.
6. Admission, Fees and Branch Management pages should load.
