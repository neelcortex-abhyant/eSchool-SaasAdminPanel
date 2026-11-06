"use client";

import { useEffect, useRef, type FormEvent, type ReactNode } from "react";

/** Create/edit dialog shared by the academic pages. Escape and Cancel close it unless it is saving. */
export function FormModal({
  title,
  description,
  error,
  saving,
  submitLabel,
  wide,
  onSubmit,
  onClose,
  children,
}: {
  title: string;
  description?: string;
  error?: string;
  saving: boolean;
  submitLabel: string;
  wide?: boolean;
  onSubmit: () => void;
  onClose: () => void;
  children: ReactNode;
}) {
  const cardRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const first = cardRef.current?.querySelector<HTMLElement>("input, select, textarea");
    first?.focus();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !saving) onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [saving, onClose]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!saving) onSubmit();
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        ref={cardRef}
        className={`modal-card acad-modal${wide ? " is-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="acad-modal-title"
        onSubmit={handleSubmit}
        noValidate
      >
        <h2 id="acad-modal-title">{title}</h2>
        {description ? <p>{description}</p> : null}
        {error ? (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        ) : null}
        <div className="resource-fields">{children}</div>
        <div className="resource-actions acad-modal-actions">
          <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
            {saving ? "Saving…" : submitLabel}
          </button>
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={saving} onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
