"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AcademicApiError, errorMessage } from "@/lib/academics";

/** Load error with a retry button, or a sign-in link when the session has expired. */
export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const pathname = usePathname();
  if (!error) return null;
  const signedOut = error instanceof AcademicApiError && error.unauthorized;
  const forbidden = error instanceof AcademicApiError && error.forbidden;
  return (
    <div className="alert alert-danger acad-error" role="alert">
      <span>{errorMessage(error)}</span>
      {signedOut ? (
        <Link className="link-btn" href={`/login?next=${encodeURIComponent(pathname)}`}>
          Sign in
        </Link>
      ) : !forbidden && onRetry ? (
        <button className="link-btn" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
