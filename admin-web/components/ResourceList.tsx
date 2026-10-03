"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

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
      const result = await api<ListResponse<T>>(endpoint);
      if (cancelled) return;

      if (!result.ok || result.data.error) {
        setError(result.data.message || `Failed to load ${title.toLowerCase()}.`);
        setRows([]);
      } else {
        setRows(result.data.data || []);
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
        GET <code>/api/admin{endpoint}</code>
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
