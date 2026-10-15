"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { adminApi, adminErrorMessage } from "@/lib/adminApi";
import { SCHOOL_MODULE_ALIAS, SCHOOL_MODULES, type SchoolField } from "@/lib/schoolModules";
import { schoolMenuTitle } from "@/lib/nav";
import type { SchoolRecord } from "@/lib/school";

type Row = Record<string, string | number | null>;
type ListResponse = { error?: boolean; data?: Row[]; detail?: string; message?: string };

export default function SchoolModulePage({ moduleKey }: { moduleKey: string }) {
  const config = SCHOOL_MODULES[SCHOOL_MODULE_ALIAS[moduleKey] || moduleKey];
  const menuTitle = schoolMenuTitle(moduleKey);
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const pageSize = 20;

  const load = useCallback(async () => {
    if (!config) return;
    setLoading(true);
    setError("");
    const schoolResult = await api<SchoolRecord>("/school-admin/school");
    const schoolId = schoolResult.ok ? schoolResult.data?.id : undefined;
    if (!schoolResult.ok || !schoolId) {
      setRows([]);
      setTotal(0);
      setError(adminErrorMessage(schoolResult.data, "Unable to load your school."));
      setLoading(false);
      return;
    }
    const result = await adminApi<ListResponse>(config.endpoint);
    if (!result.ok || !Array.isArray(result.data.data)) {
      setRows([]);
      setTotal(0);
      setError(adminErrorMessage(result.data, "Unable to load these records."));
    } else {
      const needle = query.trim().toLowerCase();
      const owned = result.data.data.filter((row) => Number(row.school_id) === schoolId);
      const matched = needle
        ? owned.filter((row) => JSON.stringify(row).toLowerCase().includes(needle))
        : owned;
      setRows(matched.slice((page - 1) * pageSize, page * pageSize));
      setTotal(matched.length);
    }
    setLoading(false);
  }, [config, page, query]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!config) {
    return (
      <div>
        <header className="school-dash-title">
          <h1>{menuTitle || "School"}</h1>
        </header>
        <section className="panel-card">
          <div className="empty-state">
            {menuTitle
              ? `No ${menuTitle.toLowerCase()} records are available for this school.`
              : "This school page does not exist."}
          </div>
          <Link className="btn-pill btn-pill-green" href="/school">
            Back to dashboard
          </Link>
        </section>
      </div>
    );
  }

  function valueFor(field: SchoolField, raw: string) {
    if (field.type === "number") return raw === "" ? null : Number(raw);
    return raw;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const missing = config.fields.filter((field) => field.required && !form[field.key]?.trim());
    if (missing.length) {
      setFormError(`Enter ${missing.map((field) => field.label.toLowerCase()).join(", ")}.`);
      return;
    }
    setSaving(true);
    setFormError("");
    setNotice("");
    const schoolResult = await api<SchoolRecord>("/school-admin/school");
    if (!schoolResult.ok || !schoolResult.data?.id) {
      setSaving(false);
      setFormError(adminErrorMessage(schoolResult.data, "Unable to load your school."));
      return;
    }
    const body: Record<string, string | number | null> = { school_id: schoolResult.data.id };
    config.fields.forEach((field) => {
      if (form[field.key] !== undefined && form[field.key] !== "") body[field.key] = valueFor(field, form[field.key]);
    });
    const result = await adminApi(editingId ? `${config.endpoint}/${editingId}` : config.endpoint, {
      method: editingId ? "PATCH" : "POST",
      body: JSON.stringify(body),
    });
    setSaving(false);
    if (!result.ok) {
      setFormError(adminErrorMessage(result.data, "Unable to save this record."));
      return;
    }
    setForm({});
    setEditingId(null);
    setNotice(editingId ? "Record updated." : "Record saved.");
    await load();
  }

  async function onDelete(row: Row) {
    const label = String(row.name || row.title || row.reason || row.id);
    if (!window.confirm(`Delete ${label}? This removes it from the school list.`)) return;
    setNotice("");
    setError("");
    const result = await adminApi(`${config.endpoint}/${row.id}`, { method: "DELETE" });
    if (!result.ok) {
      setError(adminErrorMessage(result.data, "Unable to delete this record."));
      return;
    }
    setNotice("Record deleted.");
    await load();
  }

  function startEdit(row: Row) {
    const next: Record<string, string> = {};
    config.fields.forEach((field) => {
      const value = row[field.key];
      next[field.key] = value === null || value === undefined ? "" : String(value);
    });
    if (row.first_name) next.first_name = String(row.first_name);
    if (row.last_name) next.last_name = String(row.last_name);
    setForm(next);
    setEditingId(Number(row.id));
    setFormError("");
  }

  return (
    <div>
      <header className="school-dash-title">
        <h1>{menuTitle || config.title}</h1>
      </header>
      {notice ? <div className="alert alert-success">{notice}</div> : null}
      {error ? (
        <section className="panel-card">
          <div className="alert alert-danger">{error}</div>
          <button className="btn-pill btn-pill-green" type="button" onClick={() => void load()}>
            Retry
          </button>
        </section>
      ) : null}

      <form className="panel-card resource-form" onSubmit={onSubmit}>
        {formError ? <div className="alert alert-danger">{formError}</div> : null}
        <div className="resource-fields">
          {config.fields.map((field) => (
            <div className="form-field" key={field.key}>
              <label htmlFor={`field-${field.key}`}>
                {field.label}
                {field.required ? " *" : ""}
              </label>
              {field.type === "textarea" ? (
                <textarea id={`field-${field.key}`} value={form[field.key] || ""} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
              ) : (
                <input
                  id={`field-${field.key}`}
                  type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                  value={form[field.key] || ""}
                  onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))}
                />
              )}
            </div>
          ))}
        </div>
        <div className="resource-actions">
          <button className="btn-pill btn-pill-green" type="submit" disabled={saving}>
            {saving ? "Saving…" : editingId ? "Save changes" : `Add ${config.title.toLowerCase()}`}
          </button>
          {editingId ? (
            <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => { setEditingId(null); setForm({}); }}>
              Cancel
            </button>
          ) : null}
        </div>
      </form>

      <div className="page-actions">
        <input
          type="search"
          placeholder={`Search ${config.title.toLowerCase()}`}
          value={query}
          onChange={(event) => { setQuery(event.target.value); setPage(1); }}
          aria-label={`Search ${config.title}`}
        />
      </div>

      {loading ? (
        <div className="panel-card"><div className="skeleton" style={{ height: 160 }} /></div>
      ) : (
        <div className="resource-card">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  {config.columns.map((column) => <th key={column.key}>{column.label}</th>)}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={config.columns.length + 1}>
                      <div className="empty-state">No {config.title.toLowerCase()} yet.</div>
                    </td>
                  </tr>
                ) : rows.map((row) => (
                  <tr key={String(row.id)}>
                    {config.columns.map((column) => (
                      <td key={column.key}>{displayCell(row, column.key)}</td>
                    ))}
                    <td>
                      <button className="link-btn" type="button" onClick={() => startEdit(row)}>Edit</button>
                      {" · "}
                      <button className="link-btn" type="button" onClick={() => void onDelete(row)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="page-actions" style={{ margin: 16 }}>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button>
            <span className="muted">Page {page} of {Math.max(1, Math.ceil(total / pageSize))} · {total}</span>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={page * pageSize >= total} onClick={() => setPage((current) => current + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}

function displayCell(row: Row, key: string): string {
  if (key === "name") {
    const named = row.name || `${row.first_name || ""} ${row.last_name || ""}`.trim();
    return named ? String(named) : "—";
  }
  const value = row[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}
