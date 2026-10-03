/**
 * Admin UI client for FastAPI `/api/admin/*`.
 * Default base is same-origin rewrite → FastAPI :8001 (see next.config.ts).
 * Never use this client to mint/replace Flutter mobile Sanctum bearer tokens.
 */
const ADMIN_API =
  process.env.NEXT_PUBLIC_ADMIN_API_URL || "/api/admin";

export type ApiResult<T> = {
  ok: boolean;
  status: number;
  data: T;
};

export async function api<T = Record<string, unknown>>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  const url = `${ADMIN_API}${suffix}`;

  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const data = (await response.json().catch(() => ({}))) as T;
  return { ok: response.ok, status: response.status, data };
}
