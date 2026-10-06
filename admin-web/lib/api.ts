/**
 * Client for FastAPI `/api/v1/*` (Neon slice on Render).
 * Auth uses Bearer access tokens from localStorage — not legacy `/api/admin` cookies.
 */
const API_BASE = (process.env.NEXT_PUBLIC_ADMIN_API_URL || "/api/v1").replace(/\/$/, "");

export const TOKEN_KEY = "v1_access_token";
export const SESSION_COOKIE = "v1_session";

export type ApiResult<T> = {
  ok: boolean;
  status: number;
  data: T;
};

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

export async function api<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const url = `${API_BASE}${suffix}`;
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
    credentials: "include",
    headers,
  });

  if (response.status === 204) {
    return { ok: response.ok, status: response.status, data: {} as T };
  }

  const data = (await response.json().catch(() => ({}))) as T;
  return { ok: response.ok, status: response.status, data };
}

export function apiErrorMessage(data: unknown, fallback = "Request failed."): string {
  if (!data || typeof data !== "object") return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (typeof record.message === "string") return record.message;
  return fallback;
}
