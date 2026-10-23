"use client";

import { useState } from "react";
import { errorMessage, type AcademicsService, type Medium } from "@/lib/academics";

/**
 * "Add a medium" link under a Medium dropdown. A school needs at least one medium before it
 * can add classes or subjects, so forms offer this instead of sending the admin elsewhere.
 */
export function AddMedium({ service, empty, onAdded }: { service: AcademicsService; empty: boolean; onAdded: (medium: Medium) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function add() {
    if (!name.trim()) {
      setError("Enter a medium name, such as English.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const medium = await service.createMedium(name);
      onAdded(medium);
      setName("");
      setOpen(false);
    } catch (caught) {
      setError(errorMessage(caught, "Unable to add the medium."));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <p className="field-hint">
        {empty ? "Your school has no mediums yet. " : null}
        <button className="link-btn" type="button" onClick={() => setOpen(true)}>
          Add a medium
        </button>
      </p>
    );
  }

  return (
    <div className="acad-inline-add">
      <input
        type="text"
        aria-label="New medium name"
        placeholder="English"
        maxLength={255}
        value={name}
        autoFocus
        onChange={(event) => setName(event.target.value)}
        onKeyDown={(event) => {
          // Enter adds the medium instead of submitting the class or subject form.
          if (event.key === "Enter") {
            event.preventDefault();
            void add();
          }
        }}
      />
      <button className="btn-pill btn-pill-green" type="button" disabled={saving} onClick={() => void add()}>
        {saving ? "Adding…" : "Add"}
      </button>
      <button className="btn-pill btn-pill-green-soft" type="button" disabled={saving} onClick={() => { setOpen(false); setError(""); }}>
        Cancel
      </button>
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}
