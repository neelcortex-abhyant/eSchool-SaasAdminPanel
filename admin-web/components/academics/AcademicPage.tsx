"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, apiErrorMessage, getAccessToken } from "@/lib/api";
import { academicsSource, type AcademicFeature } from "@/lib/academics";
import { ToastProvider } from "@/components/academics/Toasts";

export const ACADEMIC_TABS: { href: string; label: string; feature: AcademicFeature }[] = [
  { href: "/school/academics/sessions", label: "Sessions", feature: "sessions" },
  { href: "/school/academics/mediums", label: "Mediums", feature: "mediums" },
  { href: "/school/academics/classes", label: "Classes", feature: "classes" },
  { href: "/school/academics/sections", label: "Sections", feature: "sections" },
  { href: "/school/academics/subjects", label: "Subjects", feature: "subjects" },
  { href: "/school/academics/teacher-assignments", label: "Teacher assignments", feature: "assignments" },
];

export type Access = { state: "loading" } | { state: "allowed" } | { state: "signed-out" } | { state: "denied"; message: string };

/**
 * Only an active School Admin may open these pages. The API enforces the same rule and scopes
 * every record to the admin's own school; this check just avoids showing a broken page.
 */
// Remembers a successful check for the current token, so switching tabs skips the round trip.
let allowedToken: string | null = null;

export function useSchoolAdminAccess(): Access {
  const [access, setAccess] = useState<Access>(() =>
    allowedToken !== null && allowedToken === getAccessToken() ? { state: "allowed" } : { state: "loading" },
  );
  useEffect(() => {
    if (access.state === "allowed") return;
    let cancelled = false;
    void (async () => {
      const token = getAccessToken();
      let result;
      try {
        result = await api("/school-admin/me");
      } catch {
        if (!cancelled) setAccess({ state: "denied", message: "Unable to reach the server. Check your connection and reload." });
        return;
      }
      if (cancelled) return;
      allowedToken = result.ok ? token : null;
      if (result.ok) setAccess({ state: "allowed" });
      else if (result.status === 401) setAccess({ state: "signed-out" });
      else if (result.status === 403) {
        const detail = apiErrorMessage(result.data, "Forbidden");
        setAccess({ state: "denied", message: detail === "Forbidden" ? "Only school admins can open this page." : detail });
      } else setAccess({ state: "denied", message: apiErrorMessage(result.data, "Unable to confirm your school admin access.") });
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once per mount
  }, []);
  return access;
}

export function AcademicPage({
  feature,
  title,
  description,
  icon,
  actions,
  children,
}: {
  feature: AcademicFeature;
  title: string;
  description: string;
  icon: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const access = useSchoolAdminAccess();
  const mock = academicsSource(feature) === "mock";

  return (
    <ToastProvider>
      <div className="acad-page">
        <header className="acad-header">
          <div className="school-dash-title">
            <span className="school-dash-title-icon" aria-hidden>
              {icon}
            </span>
            <div>
              <h1>{title}</h1>
              <p className="muted acad-subtitle">{description}</p>
            </div>
          </div>
          {access.state === "allowed" && actions ? <div className="acad-header-actions">{actions}</div> : null}
        </header>

        <nav className="acad-tabs" aria-label="Academic structure">
          {ACADEMIC_TABS.map((tab) => (
            <Link key={tab.href} href={tab.href} className={`acad-tab${pathname === tab.href ? " is-active" : ""}`} aria-current={pathname === tab.href ? "page" : undefined}>
              {tab.label}
            </Link>
          ))}
        </nav>

        {mock ? (
          <div className="alert alert-info acad-mock-note">
            Showing sample data. Changes are saved only in this browser until the {title.toLowerCase()} API is connected.
          </div>
        ) : null}

        <AccessGate access={access}>{children}</AccessGate>
      </div>
    </ToastProvider>
  );
}

/** Shows a skeleton while access is checked, a sign-in link or the reason access was denied, or the page. */
export function AccessGate({ access, children }: { access: Access; children: ReactNode }) {
  const pathname = usePathname();
  if (access.state === "loading") {
    return (
      <div className="resource-card acad-card">
        <div className="skeleton" style={{ height: 18, width: "30%", marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 180 }} />
      </div>
    );
  }
  if (access.state === "signed-out") {
    return (
      <div className="alert alert-danger acad-error" role="alert">
        <span>Your session has expired. Sign in again to continue.</span>
        <Link className="link-btn" href={`/login?next=${encodeURIComponent(pathname)}`}>
          Sign in
        </Link>
      </div>
    );
  }
  if (access.state === "denied") {
    return (
      <div className="alert alert-danger" role="alert">
        {access.message}
      </div>
    );
  }
  return <>{children}</>;
}
