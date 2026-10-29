import { getAccessToken } from "@/lib/api";

export type AdminResult<T> = {
  ok: boolean;
  status: number;
  data: T;
};

/** Same-origin /api/admin calls. Sends the v1 Bearer token and any admin cookie. */
export async function adminApi<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<AdminResult<T>> {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`/api/admin${suffix}`, {
    ...options,
    credentials: "include",
    headers,
  });

  const data = (response.status === 204 ? {} : await response.json().catch(() => ({}))) as T;
  const record = data as { error?: boolean };
  return {
    ok: response.ok && record.error !== true,
    status: response.status,
    data,
  };
}

export function adminErrorMessage(data: unknown, fallback = "Request failed."): string {
  if (!data || typeof data !== "object") return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  if (Array.isArray(record.detail) && record.detail[0] && typeof record.detail[0] === "object") {
    const first = record.detail[0] as { msg?: string; loc?: unknown[] };
    if (first.msg) return first.msg;
  }
  if (typeof record.message === "string") return record.message;
  return fallback;
}
