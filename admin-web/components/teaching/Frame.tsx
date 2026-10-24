"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AccessGate, useSchoolAdminAccess } from "@/components/academics/AcademicPage";
import { ToastProvider, useToast } from "@/components/academics/Toasts";
import { openFile, safeFileUrl } from "@/components/people/Files";
import type { FileMeta } from "@/lib/teaching/types";
import { teachingSource, type TeachingModule } from "@/lib/teaching/mode";

export type Tab = { href: string; label: string };

/**
 * Frame for the teaching pages: title, actions, optional tabs, the school admin access check,
 * the live or sample-data note, and toasts.
 */
export function TeachingPage({
  module,
  title,
  description,
  icon,
  actions,
  tabs,
  liveNote,
  back,
  children,
}: {
  module: TeachingModule;
  title: string;
  description?: string;
  icon: ReactNode;
  actions?: ReactNode;
  tabs?: Tab[];
  /** What the live server can't do yet for this page, shown when the module is live. */
  liveNote?: string;
  back?: { href: string; label: string };
  children: ReactNode;
}) {
  const pathname = usePathname();
  const access = useSchoolAdminAccess();
  const mock = teachingSource(module) === "mock";
  return (
    <ToastProvider>
      <div className="acad-page teach-page">
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
          {access.state === "allowed" && actions ? <div className="acad-header-actions">{actions}</div> : null}
        </header>
        {tabs ? (
          <nav className="acad-tabs" aria-label={title}>
            {tabs.map((tab) => (
              <Link key={tab.href} href={tab.href} className={`acad-tab${pathname === tab.href ? " is-active" : ""}`} aria-current={pathname === tab.href ? "page" : undefined}>
                {tab.label}
              </Link>
            ))}
          </nav>
        ) : null}
        {mock ? (
          <div className="alert alert-info acad-mock-note">Showing sample data. Changes are saved only in this browser until this page is connected to the server.</div>
        ) : liveNote ? (
          <div className="alert alert-info acad-mock-note">{liveNote}</div>
        ) : null}
        <AccessGate access={access}>{children}</AccessGate>
      </div>
    </ToastProvider>
  );
}

export type ChipTone = "green" | "amber" | "red" | "grey" | "blue";

const TONE_CLASS: Record<ChipTone, string> = { green: "paid", amber: "pending", red: "failed", grey: "refunded", blue: "info" };

export function Chip({ tone, children }: { tone: ChipTone; children: ReactNode }) {
  return <span className={`status-badge ${TONE_CLASS[tone]}`}>{children}</span>;
}

/** A count card for summary rows (attendance, homework). */
export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: ChipTone }) {
  return (
    <div className={`teach-stat${tone ? ` is-${tone}` : ""}`}>
      <span className="teach-stat-value">{value}</span>
      <span className="teach-stat-label">{label}</span>
    </div>
  );
}

/** "2026-10-23T18:00:00Z" → "23 Oct 2026, 11:30 pm" in the viewer's time zone. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

/** ISO date-time → value for <input type="datetime-local"> in local time. */
export function toLocalInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value → ISO date-time (UTC). */
export function fromLocalInput(value: string): string {
  return value ? new Date(value).toISOString() : "";
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Why a stored file couldn't open, in words an admin can act on. */
function fileProblem(caught: unknown): string {
  const message = caught instanceof Error ? caught.message : "";
  if (message.includes("(401)")) return "Your session has expired. Sign in again to open this file.";
  if (message.includes("(403)")) return "You don't have permission to open this file.";
  if (message.includes("(404)")) return "This file is no longer on the server.";
  return "The file couldn't be opened. Try again.";
}

/** A stored file's name; opens it when the server has a link for it. */
export function FileButton({ file, label }: { file: FileMeta; label?: string }) {
  const toast = useToast();
  const size = formatBytes(file.size_bytes);
  const text = `${label ?? file.original_filename}${size ? ` (${size})` : ""}`;
  if (!file.url || !safeFileUrl(file.url)) {
    return (
      <span className="teach-file" title="The server doesn't offer a download for this file yet.">
        📎 {text}
      </span>
    );
  }
  const url = file.url;
  return (
    <button
      className="link-btn teach-file"
      type="button"
      onClick={() => {
        openFile(url).catch((caught) => toast("error", fileProblem(caught)));
      }}
    >
      📎 {text}
    </button>
  );
}
