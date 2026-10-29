"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AccessGate, useSchoolAdminAccess } from "@/components/academics/AcademicPage";
import { SelectField, StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { ToastProvider } from "@/components/academics/Toasts";
import { peopleService, type StudentRow } from "@/lib/people";
import { refOptions } from "@/lib/extras/refs";
import type { FieldDef } from "@/lib/extras/types";

export type Tab = { href: string; label: string };

/** Header, tabs, access check and toasts for the pages on the 0039 school-admin routes. */
export function ExtrasPage({ title, description, icon, actions, tabs, note, children }: { title: string; description?: string; icon: ReactNode; actions?: ReactNode; tabs?: Tab[]; note?: string; children: ReactNode }) {
  const pathname = usePathname();
  const access = useSchoolAdminAccess();
  return (
    <ToastProvider>
      <div className="acad-page teach-page">
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
        {tabs ? (
          <nav className="acad-tabs" aria-label={title}>
            {tabs.map((tab) => (
              <Link key={tab.href} href={tab.href} className={`acad-tab${pathname === tab.href ? " is-active" : ""}`} aria-current={pathname === tab.href ? "page" : undefined}>
                {tab.label}
              </Link>
            ))}
          </nav>
        ) : null}
        {note ? <div className="alert alert-info acad-mock-note">{note}</div> : null}
        <AccessGate access={access}>{children}</AccessGate>
      </div>
    </ToastProvider>
  );
}

/** Search box for one student; stores the student's id. */
export function StudentSearch({ id, label, required, value, onChange, error }: { id: string; label: string; required?: boolean; value: StudentRow | null; onChange: (student: StudentRow | null) => void; error?: string }) {
  const [text, setText] = useState("");
  const q = useDebounced(text.trim());
  const loader = useCallback(() => peopleService("students").listStudents({ q, pageSize: 8, status: "1" }).then((page) => page.items), [q]);
  const results = useOptions(q.length >= 2 ? loader : null);
  if (value) {
    return (
      <div className="form-field">
        <span className="field-label">{label}</span>
        <div className="ops-picked">
          <strong>{value.name}</strong>
          <span className="muted">
            {value.admission_no} · {value.class_name} {value.section_name}
          </span>
          <button className="link-btn" type="button" onClick={() => onChange(null)}>
            Change
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="form-field">
      <label htmlFor={id}>
        {label}
        {required ? " *" : ""}
      </label>
      <input id={id} type="search" autoComplete="off" placeholder="Name or admission number" value={text} className={error ? "invalid" : undefined} aria-invalid={Boolean(error)} onChange={(event) => setText(event.target.value)} />
      {error ? <p className="field-error">{error}</p> : <p className="field-hint">Type at least 2 letters.</p>}
      {q.length >= 2 ? (
        <ul className="ops-results" role="listbox" aria-label="Matching students">
          {results.loading ? <li className="muted">Searching…</li> : null}
          {!results.loading && results.options.length === 0 ? <li className="muted">No active student matches “{q}”.</li> : null}
          {results.options.map((student) => (
            <li key={student.id}>
              <button type="button" className="link-btn" onClick={() => onChange(student)}>
                {student.name} · {student.admission_no} · {student.class_name} {student.section_name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** One input for a field definition. */
export function FieldInput({
  field,
  value,
  onChange,
  error,
  disabled,
  student,
  onStudent,
}: {
  field: FieldDef;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  student?: StudentRow | null;
  onStudent?: (student: StudentRow | null) => void;
}) {
  const id = `x-${field.key.replace(/\./g, "-")}`;
  const ref = field.type === "ref" ? field.ref : undefined;
  const loader = useCallback(() => (ref ? refOptions(ref) : Promise.resolve([])), [ref]);
  const options = useOptions(ref && ref !== "student" ? loader : null);
  const hint = disabled && field.createOnly ? "Can't be changed after it's added." : field.hint;
  const current = field.defaultCurrent && !value && !disabled ? options.options.find((option) => option.label.endsWith("(current)")) : undefined;
  useEffect(() => {
    if (current) onChange(current.value);
  }, [current, onChange]);
  if (field.type === "ref" && field.ref === "student") {
    if (disabled) return <TextField id={id} label={field.label} value={student?.name ?? `Student #${value}`} onChange={() => undefined} disabled hint={hint} />;
    return (
      <StudentSearch
        id={id}
        label={field.label}
        required={field.required}
        value={student ?? null}
        error={error}
        onChange={(next) => {
          onStudent?.(next);
          onChange(next ? String(next.id) : "");
        }}
      />
    );
  }
  if (field.type === "ref" || field.type === "select") {
    return (
      <SelectField
        id={id}
        label={field.label}
        required={field.required}
        placeholder={field.required ? `Choose ${field.label.toLowerCase()}` : "None"}
        loading={options.loading}
        disabled={disabled}
        value={value}
        onChange={onChange}
        options={field.type === "select" ? field.options ?? [] : options.options}
        error={error ?? (options.error ? "The choices couldn't be loaded." : undefined)}
        hint={hint}
        span={field.span}
      />
    );
  }
  if (field.type === "textarea") {
    return <TextAreaField id={id} label={field.label} required={field.required} value={value} onChange={onChange} maxLength={field.maxLength} rows={field.rows} error={error} hint={hint} span />;
  }
  if (field.type === "password") {
    return <TextField id={id} label={field.label} type="password" autoComplete="new-password" value={value} onChange={onChange} maxLength={field.maxLength} error={error} hint={hint} span={field.span} />;
  }
  if (field.type === "list") {
    return <TextField id={id} label={field.label} required={field.required} value={value} onChange={onChange} error={error} hint={hint ?? "Separate choices with commas."} span={field.span} />;
  }
  if (field.type === "checkbox") {
    return <StatusToggle id={id} checked={value === "1"} onChange={(checked) => onChange(checked ? "1" : "0")} label={field.label} />;
  }
  const type = field.type === "datetime" ? "datetime-local" : field.type;
  return <TextField id={id} label={field.label} type={type} required={field.required} value={value} onChange={onChange} maxLength={field.maxLength} disabled={disabled} error={error} hint={hint} span={field.span} />;
}
