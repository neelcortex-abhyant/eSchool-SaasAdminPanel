"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { StatusBadge } from "@/components/academics/StatusBadge";

/** Photo when there is one, otherwise the person's initials. */
export function Avatar({ name, photoUrl, size = 40 }: { name: string; photoUrl: string | null; size?: number }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return photoUrl ? (
    // eslint-disable-next-line @next/next/no-img-element -- signed upload URLs and local previews can't go through next/image
    <img className="people-avatar" src={photoUrl} alt="" width={size} height={size} style={{ width: size, height: size }} />
  ) : (
    <span className="people-avatar is-initials" aria-hidden style={{ width: size, height: size, fontSize: Math.round(size * 0.38) }}>
      {initials || "?"}
    </span>
  );
}

/** Name and photo with status and actions, at the top of a profile. */
export function ProfileHeader({
  name,
  photoUrl,
  meta,
  active,
  actions,
}: {
  name: string;
  photoUrl: string | null;
  meta: ReactNode;
  active: boolean;
  actions?: ReactNode;
}) {
  return (
    <section className="resource-card people-hero">
      <Avatar name={name} photoUrl={photoUrl} size={72} />
      <div className="people-hero-text">
        <h2>
          {name} <StatusBadge active={active} />
        </h2>
        <p className="muted">{meta}</p>
      </div>
      {actions ? <div className="people-hero-actions">{actions}</div> : null}
    </section>
  );
}

export type InfoRow = { label: string; value: ReactNode };

/** A titled card of label/value pairs. Empty values show a dash. */
export function InfoCard({ title, rows, action, children }: { title: string; rows?: InfoRow[]; action?: ReactNode; children?: ReactNode }) {
  return (
    <section className="resource-card people-card">
      <header className="people-card-head">
        <h3>{title}</h3>
        {action}
      </header>
      {rows ? (
        <dl className="people-info">
          {rows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value === null || row.value === undefined || row.value === "" ? "—" : row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children}
    </section>
  );
}

/** A titled group of fields in a long form. */
export function FormSection({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <fieldset className="resource-card people-form-section">
      <legend>{title}</legend>
      {description ? <p className="muted people-form-note">{description}</p> : null}
      <div className="resource-fields">{children}</div>
    </fieldset>
  );
}

/** Profile skeleton shown while a record loads. */
export function ProfileSkeleton() {
  return (
    <div className="people-grid" aria-busy="true">
      <div className="resource-card people-hero">
        <div className="skeleton" style={{ width: 72, height: 72, borderRadius: "50%" }} />
        <div style={{ flex: 1 }}>
          <div className="skeleton" style={{ height: 20, width: "40%", marginBottom: 10 }} />
          <div className="skeleton" style={{ height: 14, width: "60%" }} />
        </div>
      </div>
      <div className="resource-card people-card">
        <div className="skeleton" style={{ height: 140 }} />
      </div>
    </div>
  );
}

/**
 * Loads one record by id. A load that finishes after a newer one started is ignored, and
 * `setRecord` lets a page show the server's copy after a save without reloading.
 */
export function useRecord<T>(loader: (() => Promise<T>) | null) {
  const [record, setRecord] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const requestId = useRef(0);
  const latest = useRef(loader);
  latest.current = loader;

  const reload = useCallback(async () => {
    const id = ++requestId.current;
    const load = latest.current;
    if (!load) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await load();
      if (id === requestId.current) setRecord(result);
    } catch (caught) {
      if (id === requestId.current) setError(caught);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [loader, reload]);

  return { record, setRecord, loading, error, reload };
}
