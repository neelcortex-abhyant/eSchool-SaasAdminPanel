"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { adminApi, adminErrorMessage } from "@/lib/adminApi";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconBook } from "@/lib/icons";

export type Column<T> = {
  key: keyof T & string;
  label: string;
};

export type FieldDef = {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "textarea";
  required?: boolean;
  createOnly?: boolean;
};

type ListResponse<T> = {
  error?: boolean;
  message?: string;
  detail?: string;
  data?: T[];
};

export default function ResourceList<T extends object>({
  title,
  endpoint,
  columns,
  fields,
  allowUpdate = true,
}: {
  title: string;
  endpoint: string;
  columns: Column<T>[];
  fields: FieldDef[];
  allowUpdate?: boolean;
}) {
  const [rows, setRows] = useState<T[]>([]);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await adminApi<ListResponse<T>>(endpoint);
    if (!result.ok) {
      setError(adminErrorMessage(result.data, `Failed to load ${title.toLowerCase()}.`));
      setRows([]);
    } else {
      setRows(result.data.data || []);
    }
    setLoading(false);
  }, [endpoint, title]);

  useEffect(() => {
    void load();
  }, [load]);

  function resetForm() {
    setForm({});
    setEditingId(null);
    setFormError("");
  }

  function startEdit(row: T) {
    const record = row as Record<string, unknown>;
    const next: Record<string, string> = {};
    fields
      .filter((field) => !field.createOnly)
      .forEach((field) => {
        const value = record[field.key];
        if (value === null || value === undefined) {
          next[field.key] = "";
        } else if (field.type === "date") {
          next[field.key] = String(value).slice(0, 10);
        } else {
          next[field.key] = String(value);
        }
      });
    setEditingId((record.id as string | number) ?? null);
    setForm(next);
    setFormError("");
  }

  function payloadFromForm(mode: "create" | "edit") {
    const active = fields.filter((field) => (mode === "create" ? true : !field.createOnly));
    const missing = active.filter((field) => field.required && !String(form[field.key] || "").trim());
    if (missing.length) {
      return { error: `Enter ${missing.map((field) => field.label.toLowerCase()).join(", ")}.` };
    }
    const body: Record<string, unknown> = {};
    active.forEach((field) => {
      const raw = String(form[field.key] || "").trim();
      if (!raw) return;
      if (field.type === "number") {
        const parsed = Number(raw);
        if (Number.isNaN(parsed)) {
          body.__invalid = field.label;
          return;
        }
        body[field.key] = parsed;
      } else {
        body[field.key] = raw;
      }
    });
    if (typeof body.__invalid === "string") {
      return { error: `${body.__invalid} must be a number.` };
    }
    return { body };
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const mode = editingId === null ? "create" : "edit";
    const parsed = payloadFromForm(mode);
    if (parsed.error || !parsed.body) {
      setFormError(parsed.error || "Check the form and try again.");
      return;
    }
    setSaving(true);
    setFormError("");
    const result =
      editingId === null
        ? await adminApi(endpoint, { method: "POST", body: JSON.stringify(parsed.body) })
        : await adminApi(`${endpoint}/${editingId}`, {
            method: "PATCH",
            body: JSON.stringify(parsed.body),
          });
    setSaving(false);
    if (!result.ok) {
      setFormError(adminErrorMessage(result.data, "Unable to save this record."));
      return;
    }
    setNotice(editingId === null ? "Record created." : "Record updated.");
    resetForm();
    await load();
  }

  async function onDelete(id: string | number) {
    if (!window.confirm("Delete this record?")) return;
    setError("");
    const result = await adminApi(`${endpoint}/${id}`, { method: "DELETE" });
    if (!result.ok) {
      setError(adminErrorMessage(result.data, "Unable to delete this record."));
      return;
    }
    if (editingId === id) resetForm();
    setNotice("Record deleted.");
    await load();
  }

  const visibleFields = fields.filter((field) => (editingId === null ? true : !field.createOnly));

  return (
    <div>
      <PageHeading
        title={title}
        description={`Live data from /api/admin${endpoint}`}
        icon={<IconBook width={20} height={20} />}
      />

      <form className="panel-card resource-form" onSubmit={onSubmit}>
        <div className="panel-card-header">
          <h2>{editingId === null ? `Add ${title.replace(/s$/, "")}` : `Edit ${title.replace(/s$/, "")}`}</h2>
        </div>
        {formError ? <div className="alert alert-danger">{formError}</div> : null}
        <div className="resource-fields">
          {visibleFields.map((field) => (
            <div className="form-field" key={field.key}>
              <label htmlFor={`${endpoint}-${field.key}`}>
                {field.label}
                {field.required ? " *" : ""}
              </label>
              {field.type === "textarea" ? (
                <textarea
                  id={`${endpoint}-${field.key}`}
                  rows={3}
                  value={form[field.key] || ""}
                  onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                />
              ) : (
                <input
                  id={`${endpoint}-${field.key}`}
                  type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                  value={form[field.key] || ""}
                  onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                  required={field.required}
                />
              )}
            </div>
          ))}
        </div>
        <div className="resource-actions">
          <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
            {saving ? "Saving…" : editingId === null ? "Create" : "Update"}
          </button>
          {editingId !== null ? (
            <button className="btn-pill btn-pill-green-soft" type="button" onClick={resetForm}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>

      {loading ? (
        <div className="resource-card" style={{ padding: 20, marginTop: 16 }}>
          <div className="skeleton" style={{ height: 18, width: "30%", marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      ) : null}

      {notice ? <div className="alert alert-info">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}

      {!loading && !error ? (
        <div className="resource-card" style={{ marginTop: 16 }}>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.key}>{col.label}</th>
                  ))}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length + 1}>
                      <div className="empty-state">No records.</div>
                    </td>
                  </tr>
                ) : (
                  rows.map((row, index) => {
                    const record = row as Record<string, unknown>;
                    const id = record.id as string | number;
                    return (
                      <tr key={String(id ?? index)}>
                        {columns.map((col) => (
                          <td key={col.key}>{formatCell(record[col.key])}</td>
                        ))}
                        <td>
                          {allowUpdate ? (
                            <button type="button" className="link-btn" onClick={() => startEdit(row)}>
                              Edit
                            </button>
                          ) : null}
                          {allowUpdate ? " · " : null}
                          <button type="button" className="link-btn" onClick={() => onDelete(id)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}
