/**
 * Client for FastAPI `/api/v1/*` (Neon slice on Render).
 * Auth uses Bearer access tokens from localStorage — not legacy `/api/admin` cookies.
 */

export const RENDER_V1_API = "https://eschool-backend-8322.onrender.com/api/v1";

export const TOKEN_KEY = "v1_access_token";
export const SESSION_COOKIE = "v1_session";

/** Visible on /login so we can confirm which build Netlify is serving. */
export const CLIENT_BUILD = "2026-10-06-netlify-direct-v2";

export type ApiResult<T> = {
  ok: boolean;
  status: number;
  data: T;
};

function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    // Always hit Render from Netlify — never the broken same-origin function proxy.
    if (host.endsWith("netlify.app") || host.endsWith("netlify.com")) {
      return RENDER_V1_API;
    }
  }
  const fromEnv = (process.env.NEXT_PUBLIC_ADMIN_API_URL || "/api/v1").replace(/\/$/, "");
  // If a stale Netlify build baked "/" relative or empty, prefer Render in production builds.
  if (fromEnv === "/api/v1" && process.env.NODE_ENV === "production") {
    // Local `next start` still wants relative proxy; only force Render on known hosts above.
    return fromEnv;
  }
  return fromEnv;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setSession(accessToken: string): void {
  window.localStorage.setItem(TOKEN_KEY, accessToken);
  // Middleware cannot read localStorage; set a presence cookie for route guards.
  document.cookie = `${SESSION_COOKIE}=1; Path=/; SameSite=Lax`;
}

export function clearSession(): void {
  getCache.clear();
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

async function fetchApi<T>(url: string, options: RequestInit): Promise<ApiResult<T>> {
  const headers = new Headers(options.headers || {});

  // FormData sets its own multipart Content-Type with the boundary.
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    // Bearer auth only — avoid credentialed CORS failures against Render from Netlify.
    credentials: "same-origin",
    headers,
  });

  if (response.status === 204) {
    return { ok: response.ok, status: response.status, data: {} as T };
  }

  const data = (await response.json().catch(() => ({}))) as T;
  return { ok: response.ok, status: response.status, data };
}

export function apiUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${resolveApiBase()}${suffix}`;
}

/**
 * Short-lived cache for successful GETs, shared by every page and component. Lookups such as
 * sessions, classes, sections, subjects and teachers are read by many dropdowns and lists at
 * once; identical requests made at the same time share one network call, and repeats within
 * GET_CACHE_MS reuse the answer. Any POST, PATCH, PUT or DELETE (and sign-out) clears it, so a
 * page always reads fresh data after a change.
 */
const GET_CACHE_MS = 30_000;
const getCache = new Map<string, { at: number; promise: Promise<ApiResult<unknown>> }>();

export function invalidateApiCache(): void {
  getCache.clear();
}

function copy<T>(result: ApiResult<T>): ApiResult<T> {
  // Callers may change the objects they get back; each one gets its own copy.
  return { ...result, data: typeof structuredClone === "function" ? structuredClone(result.data) : JSON.parse(JSON.stringify(result.data)) };
}

export async function api<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" || options.body || typeof window === "undefined") {
    if (method !== "GET") invalidateApiCache();
    return send<T>(path, options);
  }
  const key = `${getAccessToken() ?? ""} ${path}`;
  const hit = getCache.get(key);
  if (hit && Date.now() - hit.at < GET_CACHE_MS) return copy((await hit.promise) as ApiResult<T>);
  const promise = send<T>(path, options);
  getCache.set(key, { at: Date.now(), promise: promise as Promise<ApiResult<unknown>> });
  const result = await promise;
  // Only successful answers are kept; errors are retried on the next call.
  if (!result.ok && getCache.get(key)?.promise === promise) getCache.delete(key);
  return copy(result);
}

async function send<T>(path: string, options: RequestInit): Promise<ApiResult<T>> {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const base = resolveApiBase();
  const primary = await fetchApi<T>(`${base}${suffix}`, options);

  // If same-origin Netlify proxy fails, retry once against Render.
  if (
    primary.status >= 500 &&
    base !== RENDER_V1_API &&
    typeof window !== "undefined"
  ) {
    return fetchApi<T>(`${RENDER_V1_API}${suffix}`, options);
  }

  return primary;
}

/**
 * Fetches a file the API serves only to signed-in users (photos, document downloads) and
 * returns a blob: URL the browser can show or open. Revoke it when it's no longer needed.
 */
export async function apiBlobUrl(path: string): Promise<string> {
  const headers = new Headers();
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(apiUrl(path), { headers, credentials: "same-origin" });
  if (!response.ok) throw new Error(`File request failed (${response.status})`);
  return URL.createObjectURL(await response.blob());
}

let meRequest: { token: string | null; promise: Promise<ApiResult<unknown>> } | null = null;

/**
 * `/auth/me` shared by the shell and the page that mount together, so a page load makes
 * one profile request instead of two. The cached promise is dropped after it settles.
 */
export function getMe<T>(): Promise<ApiResult<T>> {
  const token = getAccessToken();
  if (!meRequest || meRequest.token !== token) {
    const promise = api<T>("/auth/me") as Promise<ApiResult<unknown>>;
    meRequest = { token, promise };
    const clear = () => {
      setTimeout(() => {
        if (meRequest?.promise === promise) meRequest = null;
      }, 2000);
    };
    promise.then(clear, clear);
  }
  return meRequest.promise as Promise<ApiResult<T>>;
}

export function apiErrorMessage(data: unknown, fallback = "Request failed."): string {
  if (!data || typeof data !== "object") return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (Array.isArray(record.detail)) {
    const first = record.detail.find((item) => item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string") as
      | { msg: string }
      | undefined;
    if (first) return first.msg.replace(/^Value error,\s*/i, "");
  }
  if (typeof record.message === "string") return record.message;
  return fallback;
}
