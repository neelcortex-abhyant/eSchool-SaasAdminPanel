"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconPackage } from "@/lib/icons";

export type Column = { key: string; label: string };

export type Field = {
  key: string;
  label: string;
  type?: "text" | "number" | "date" | "textarea";
  required?: boolean;
};

type ListBody = { items?: Record<string, unknown>[]; detail?: string };

export default function PlatformResource({
  title,
  description,
  endpoint,
  columns,
  fields = [],
  canCreate = false,
  canEdit = false,
  canDelete = false,
  statusToggle = false,
}: {
  title: string;
  description: string;
  endpoint: string;
  columns: Column[];
  fields?: Field[];
  canCreate?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
  statusToggle?: boolean;
}) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await api<ListBody>(`${endpoint}?page=1&page_size=100`);
    if (!result.ok) {
      setRows([]);
      setError(result.status === 403 ? forbidden() : apiErrorMessage(result.data, `Unable to load ${title.toLowerCase()}.`));
    } else {
      setRows(result.data.items || []);
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

  function startEdit(row: Record<string, unknown>) {
    const next: Record<string, string> = {};
    fields.forEach((field) => {
      const value = row[field.key];
      if (value === null || value === undefined) next[field.key] = "";
      else if (field.type === "date") next[field.key] = String(value).slice(0, 10);
      else next[field.key] = String(value);
    });
    setEditingId((row.id as string | number) ?? null);
    setForm(next);
    setFormError("");
  }

  function buildBody() {
    const missing = fields.filter((field) => field.required && !String(form[field.key] || "").trim());
    if (missing.length) return { error: `Enter ${missing.map((field) => field.label.toLowerCase()).join(", ")}.` };
    const body: Record<string, unknown> = {};
    for (const field of fields) {
      const raw = String(form[field.key] || "").trim();
      if (!raw) continue;
      if (field.type === "number") {
        const parsed = Number(raw);
        if (Number.isNaN(parsed)) return { error: `${field.label} must be a number.` };
        body[field.key] = parsed;
      } else {
        body[field.key] = raw;
      }
    }
    return { body };
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const parsed = buildBody();
    if (parsed.error || !parsed.body) {
      setFormError(parsed.error || "Check the form and try again.");
      return;
    }
    setSaving(true);
    setFormError("");
    const result =
      editingId === null
        ? await api(endpoint, { method: "POST", body: JSON.stringify(parsed.body) })
        : await api(`${endpoint}/${editingId}`, { method: "PATCH", body: JSON.stringify(parsed.body) });
    setSaving(false);
    if (!result.ok) {
      setFormError(result.status === 403 ? forbidden() : apiErrorMessage(result.data, "Unable to save this record."));
      return;
    }
    setNotice(editingId === null ? "Record created." : "Record updated.");
    resetForm();
    await load();
  }

  async function onDelete(id: string | number) {
    if (!window.confirm("Delete this record?")) return;
    const result = await api(`${endpoint}/${id}`, { method: "DELETE" });
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to delete this record."));
      return;
    }
    if (editingId === id) resetForm();
    setNotice("Record deleted.");
    await load();
  }

  async function onToggleStatus(row: Record<string, unknown>) {
    const id = row.id as string | number;
    const next = Number(row.status) === 1 ? 0 : 1;
    const result = await api(`${endpoint}/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: next }),
    });
    if (!result.ok) {
      setError(apiErrorMessage(result.data, "Unable to update status."));
      return;
    }
    await load();
  }

  const showForm = canCreate || (canEdit && editingId !== null);

  return (
    <div>
      <PageHeading title={title} description={description} icon={<IconPackage width={20} height={20} />} />
      {showForm ? (
        <form className="panel-card resource-form" onSubmit={onSubmit}>
          <div className="panel-card-header">
            <h2>{editingId === null ? `Add ${title.replace(/s$/, "")}` : `Edit ${title.replace(/s$/, "")}`}</h2>
          </div>
          {formError ? <div className="alert alert-danger">{formError}</div> : null}
          <div className="resource-fields">
            {fields.map((field) => (
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
      ) : null}
      {notice ? <div className="alert alert-info">{notice}</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}
      {loading ? (
        <div className="resource-card" style={{ padding: 20 }}>
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      ) : null}
      {!loading && !error ? (
        <div className="resource-card" style={{ marginTop: 16 }}>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  {canEdit || canDelete || statusToggle ? <th>Actions</th> : null}
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
                    const id = row.id as string | number;
                    return (
                      <tr key={String(id ?? index)}>
                        {columns.map((column) => (
                          <td key={column.key}>{formatCell(row[column.key])}</td>
                        ))}
                        {canEdit || canDelete || statusToggle ? (
                          <td>
                            {canEdit ? (
                              <button type="button" className="link-btn" onClick={() => startEdit(row)}>
                                Edit
                              </button>
                            ) : null}
                            {statusToggle ? (
                              <>
                                {canEdit ? " · " : null}
                                <button type="button" className="link-btn" onClick={() => onToggleStatus(row)}>
                                  {Number(row.status) === 1 ? "Deactivate" : "Activate"}
                                </button>
                              </>
                            ) : null}
                            {canDelete ? (
                              <>
                                {canEdit || statusToggle ? " · " : null}
                                <button type="button" className="link-btn" onClick={() => onDelete(id)}>
                                  Delete
                                </button>
                              </>
                            ) : null}
                          </td>
                        ) : null}
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
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function forbidden() {
  return "This account cannot use platform APIs. Sign in with a super admin account.";
}
