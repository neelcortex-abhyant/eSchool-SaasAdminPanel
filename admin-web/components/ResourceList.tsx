"use client";

import { useEffect, useState } from "react";
import { PageHeading } from "@/components/dashboard/StatCard";
import { IconBook } from "@/lib/icons";

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
      const response = await fetch(`/api/admin${endpoint}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      const payload = (await response.json().catch(() => ({}))) as ListResponse<T>;
      if (cancelled) return;

      if (!response.ok || payload.error) {
        setError(
          payload.message ||
            `Failed to load ${title.toLowerCase()}. This module needs the /api/admin backend session.`,
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
      <PageHeading
        title={title}
        description={`Listing from /api/admin${endpoint}`}
        icon={<IconBook width={20} height={20} />}
      />

      {loading ? (
        <div className="resource-card" style={{ padding: 20 }}>
          <div className="skeleton" style={{ height: 18, width: "30%", marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 160 }} />
        </div>
      ) : null}

      {error ? <div className="alert alert-danger">{error}</div> : null}

      {!loading && !error ? (
        <div className="resource-card">
          <div className="table-wrap">
            <table className="data-table">
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
                    <td colSpan={columns.length}>
                      <div className="empty-state">No records.</div>
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
