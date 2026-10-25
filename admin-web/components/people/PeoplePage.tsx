"use client";

import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { AccessGate, useSchoolAdminAccess } from "@/components/academics/AcademicPage";
import { ToastProvider, useToast } from "@/components/academics/Toasts";
import { LIVE_LIMITS_NOTE, peopleSource, type PeopleModule } from "@/lib/people";

const FLASH_KEY = "people-flash";

/** Shows a success toast on the next page, e.g. on a profile after the admission form redirects there. */
export function flashMessage(message: string, tone: "success" | "error" = "success") {
  try {
    window.sessionStorage.setItem(FLASH_KEY, JSON.stringify({ tone, message }));
  } catch {
    // No storage: the redirect still happens, just without the toast.
  }
}

function FlashToast() {
  const toast = useToast();
  useEffect(() => {
    let flash: { tone?: "success" | "error"; message?: string } | null = null;
    try {
      flash = JSON.parse(window.sessionStorage.getItem(FLASH_KEY) || "null");
      window.sessionStorage.removeItem(FLASH_KEY);
    } catch {
      flash = null;
    }
    if (flash?.message) toast(flash.tone === "error" ? "error" : "success", flash.message);
  }, [toast]);
  return null;
}

const MODULE_LABEL: Record<PeopleModule, string> = {
  students: "student",
  parents: "parent",
  teachers: "teacher",
  staff: "staff",
};

/**
 * Frame for the student, parent, teacher and staff pages: title, optional back link, the
 * school admin access check, the sample-data note and toasts.
 */
export function PeoplePage({
  module,
  title,
  description,
  icon,
  back,
  actions,
  children,
}: {
  module: PeopleModule;
  title: string;
  description?: string;
  icon: ReactNode;
  back?: { href: string; label: string };
  actions?: ReactNode;
  children: ReactNode;
}) {
  const access = useSchoolAdminAccess();
  const mock = peopleSource(module) === "mock";

  return (
    <ToastProvider>
      <FlashToast />
      <div className="acad-page people-page">
        {back ? (
          <Link className="people-back" href={back.href}>
            ← {back.label}
          </Link>
        ) : null}
        <header className="acad-header">
          <div className="school-dash-title">
            <span className="school-dash-title-icon" aria-hidden>
              {icon}
            </span>
            <div>
              <h1>{title}</h1>
              {description ? <p className="muted acad-subtitle">{description}</p> : null}
            </div>
          </div>
          {(access.state === "allowed" || access.state === "loading") && actions ? <div className="acad-header-actions">{actions}</div> : null}
        </header>

        {mock ? (
          <div className="alert alert-info acad-mock-note">
            Showing sample data. Changes are saved only in this browser until the {MODULE_LABEL[module]} API is connected.
          </div>
        ) : (
          <div className="alert alert-info acad-mock-note">{LIVE_LIMITS_NOTE[module]}</div>
        )}

        <AccessGate access={access}>{children}</AccessGate>
      </div>
    </ToastProvider>
  );
}

/** Parses the [id] route segment. Anything that isn't a positive whole number is treated as not found. */
export function routeId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  const id = Number(raw);
  return Number.isInteger(id) && id > 0 ? id : null;
}
