/** Error raised by both academics clients, so pages handle live and mock failures the same way. */
export class AcademicApiError extends Error {
  readonly status: number;
  /** Field name → message, from a FastAPI 422 validation list. */
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "AcademicApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }

  get unauthorized() {
    return this.status === 401;
  }

  get forbidden() {
    return this.status === 403;
  }
}

type ValidationItem = { loc?: unknown[]; msg?: unknown };

/** Turns a FastAPI error body into an AcademicApiError. */
export function errorFromResponse(status: number, data: unknown, fallback: string): AcademicApiError {
  const detail = data && typeof data === "object" ? (data as { detail?: unknown }).detail : undefined;
  if (status === 401) {
    return new AcademicApiError(401, "Your session has expired. Sign in again to continue.");
  }
  if (typeof detail === "string" && detail) {
    return new AcademicApiError(status, status === 403 && detail === "Forbidden" ? "Your account can't manage this school's records." : detail);
  }
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    for (const item of detail as ValidationItem[]) {
      if (!item || typeof item.msg !== "string") continue;
      const loc = Array.isArray(item.loc) ? item.loc : [];
      const message = item.msg.replace(/^Value error,\s*/i, "");
      // ["body", "end_date"] → "end_date". A nested field keeps its full path, e.g.
      // ["body", "guardian", "email"] → "guardian.email", so it doesn't land on a top-level
      // "email" field; its top-level name ("guardian") is set too.
      const parts = loc.slice(["body", "query", "path"].includes(String(loc[0])) ? 1 : 0).map(String);
      const field = parts.join(".");
      if (field && !fieldErrors[field]) fieldErrors[field] = message;
      if (parts.length > 1 && !fieldErrors[parts[0]]) fieldErrors[parts[0]] = message;
    }
    const first = Object.values(fieldErrors)[0];
    return new AcademicApiError(status, first ? "Check the highlighted fields." : fallback, fieldErrors);
  }
  if (status === 403) return new AcademicApiError(403, "Your account can't manage this school's records.");
  if (status === 0) return new AcademicApiError(0, "Unable to reach the server. Check your connection and try again.");
  return new AcademicApiError(status, fallback);
}

export function errorMessage(error: unknown, fallback = "Something went wrong. Try again."): string {
  if (error instanceof AcademicApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
