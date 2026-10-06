"use client";

import { useEffect, useState } from "react";

type Column<T> = {
  key: keyof T & string;
  label: string;
};

type ListResponse<T> = {
  error?: boolean;
  message?: string;
  data?: T[];
};

export default function ResourceList<T extends object>({
  title,
  endpoint,
  columns,
}: {
  title: string;
  endpoint: string;
  columns: Column<T>[];
}) {
  const [rows, setRows] = useState<T[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      // Legacy lists still hit /api/admin via absolute path through the Next rewrite.
      const response = await fetch(`/api/admin${endpoint}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      const payload = (await response.json().catch(() => ({}))) as ListResponse<T>;
      if (cancelled) return;

      if (!response.ok || payload.error) {
        setError(
          payload.message ||
            `Failed to load ${title.toLowerCase()}. This module needs the legacy /api/admin backend.`,
        );
        setRows([]);
      } else {
        setRows(payload.data || []);
      }
      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [endpoint, title]);

  return (
    <div>
      <h1 className="h3 mb-3">{title}</h1>
      <p className="text-muted small mb-3">
        Legacy MySQL module — GET <code>/api/admin{endpoint}</code> (not part of{" "}
        <code>/api/v1</code> on Render).
      </p>

      {loading ? <div className="text-muted">Loading…</div> : null}
      {error ? <div className="alert alert-danger">{error}</div> : null}

      {!loading && !error ? (
        <div className="table-responsive">
          <table className="table table-sm table-striped align-middle">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col.key} scope="col">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="text-muted">
                    No records.
                  </td>
                </tr>
              ) : (
                rows.map((row, index) => {
                  const record = row as Record<string, unknown>;
                  return (
                    <tr key={String(record.id ?? index)}>
                      {columns.map((col) => (
                        <td key={col.key}>{formatCell(record[col.key])}</td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}
