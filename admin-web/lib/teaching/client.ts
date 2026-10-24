/**
 * Request helpers for the live teaching clients. Paths are relative to /api/v1, e.g.
 * "/school-admin/homework". Errors come back as AcademicApiError so pages show them the same
 * way as the academics and people pages (409 sentences, 422 field messages, 401/403).
 */
import { api, apiUrl, getAccessToken } from "@/lib/api";
import { AcademicApiError, errorFromResponse } from "@/lib/academics/errors";
import type { Page } from "@/lib/teaching/types";

export type Raw = Record<string, unknown>;
type QueryValue = string | number | boolean | null | undefined;

export const MAX_PAGE_SIZE = 50;
const MAX_PAGES = 20;

export function query(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export async function request<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  let result;
  try {
    result = await api<T>(path, init);
  } catch {
    throw errorFromResponse(0, null, fallback);
  }
  if (!result.ok) throw errorFromResponse(result.status, result.data, fallback);
  return result.data;
}

export function get<T = Raw>(path: string, params: Record<string, QueryValue>, fallback: string) {
  return request<T>(`${path}${query(params)}`, { method: "GET" }, fallback);
}

export function send<T = Raw>(method: "POST" | "PATCH" | "DELETE", path: string, body: unknown, fallback: string) {
  return request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }, fallback);
}

export function upload<T = Raw>(path: string, form: FormData, fallback: string) {
  return request<T>(path, { method: "POST", body: form }, fallback);
}

/** Multipart upload that reports progress (0–100). fetch() can't report upload progress, so this uses XHR. */
export function uploadWithProgress<T = Raw>(path: string, form: FormData, fallback: string, onProgress: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl(path));
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else reject(errorFromResponse(xhr.status, data, fallback));
    };
    xhr.onerror = () => reject(errorFromResponse(0, null, fallback));
    xhr.send(form);
  });
}

/** Every row of a paged list, for summaries and pickers (at most 1,000 rows). */
export async function allPages(path: string, params: Record<string, QueryValue>, fallback: string): Promise<Raw[]> {
  const rows: Raw[] = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const data = await get<Raw>(path, { ...params, page, page_size: MAX_PAGE_SIZE }, fallback);
    const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
    rows.push(...items);
    if (items.length === 0 || rows.length >= Number(data.total ?? rows.length)) break;
  }
  return rows;
}

export function pageOf<T>(data: Raw, map: (row: Raw) => T): Page<T> {
  const items = Array.isArray(data.items) ? (data.items as Raw[]) : [];
  return { items: items.map(map), total: num(data.total ?? items.length), page: num(data.page ?? 1), page_size: num(data.page_size ?? items.length) };
}

export function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : value === null || value === undefined ? fallback : String(value);
}

export function optStr(value: unknown): string | null {
  const text = str(value).trim();
  return text ? text : null;
}

export function num(value: unknown): number {
  return typeof value === "number" ? value : Number(value ?? 0);
}

export function optNum(value: unknown): number | null {
  return value === null || value === undefined || value === "" ? null : Number(value);
}

/** "08:30:00" or "08:30" → "08:30". */
export function hhmm(value: unknown): string {
  return str(value).slice(0, 5);
}

export function notAvailable(message: string): never {
  throw new AcademicApiError(501, message);
}

/** Runs tasks with limited concurrency and returns each result or error, in order. */
export async function settleLimited<T>(tasks: (() => Promise<T>)[], limit = 4): Promise<({ ok: true; value: T } | { ok: false; error: unknown })[]> {
  const results: ({ ok: true; value: T } | { ok: false; error: unknown })[] = new Array(tasks.length);
  let next = 0;
  async function worker() {
    while (next < tasks.length) {
      const index = next++;
      try {
        results[index] = { ok: true, value: await tasks[index]() };
      } catch (error) {
        results[index] = { ok: false, error };
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker));
  return results;
}
