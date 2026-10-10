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
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

async function fetchApi<T>(url: string, options: RequestInit): Promise<ApiResult<T>> {
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body) {
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

export async function api<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
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

export function apiErrorMessage(data: unknown, fallback = "Request failed."): string {
  if (!data || typeof data !== "object") return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (Array.isArray(record.detail)) {
    const first = record.detail.find((item) => item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string") as
      | { msg: string }
      | undefined;
    if (first) return first.msg;
  }
  if (typeof record.message === "string") return record.message;
  return fallback;
}
