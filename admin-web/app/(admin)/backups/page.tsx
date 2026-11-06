"use client";

import { useCallback, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { PageHeading } from "@/components/ui/PageHeading";
import { api, apiErrorMessage } from "@/lib/api";
import { backupStatus, type Backup } from "@/lib/backups";
import { IconSettings } from "@/lib/icons";

function when(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function BackupsPage() {
  const [rows, setRows] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState<Backup | null>(null);
  const [typed, setTyped] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const result = await api<{ items?: Backup[] }>("/super-admin/backups?page=1&page_size=50");
    if (result.ok) setRows(result.data.items ?? []);
    else setError(result.status === 403 ? "Only super admins can see platform backups." : apiErrorMessage(result.data, "Unable to load backups."));
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    const result = await api<Backup>("/super-admin/backups", { method: "POST" });
    setBusy(false);
    if (!result.ok) {
      setNotice({ ok: false, text: apiErrorMessage(result.data, "Unable to start a backup.") });
      return;
    }
    setNotice({ ok: result.data.status !== "failed", text: `${backupStatus(result.data.status).label}.${result.data.error_message ? ` ${result.data.error_message}` : ""}` });
    void load();
  }

  return (
    <div>
      <PageHeading title="Platform backups" description="Backups of the whole platform, as the server records them." icon={<IconSettings width={20} height={20} />} />
      <div className="alert alert-warning">
        The server doesn&apos;t make full database copies yet. A backup here is a record, and a restore only records the request; nothing in the database
        is replaced. Each row shows the server&apos;s own note.
      </div>
      <div className="page-actions">
        <button className="btn-pill btn-pill-green" type="button" disabled={busy} onClick={() => void create()}>
          {busy ? "Starting…" : "Start backup"}
        </button>
      </div>
      {notice ? <div className={`alert ${notice.ok ? "alert-success" : "alert-danger"}`} role="status">{notice.text}</div> : null}
      {error ? <div className="alert alert-danger" role="alert">{error}</div> : null}
      <section className="panel-card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Started</th>
                <th>Status</th>
                <th>Size</th>
                <th>Kept until</th>
                <th>Server note</th>
                <th>
                  <span className="acad-sr">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && !rows.length ? (
                <tr>
                  <td colSpan={6}>
                    <div className="skeleton" style={{ height: 18 }} />
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-state">No backups yet.</div>
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.id}>
                    <td data-label="Started">{when(row.created_at)}</td>
                    <td data-label="Status">
                      <span className={`status-badge ${backupStatus(row.status).tone}`}>{backupStatus(row.status).label}</span>
                    </td>
                    <td data-label="Size">{row.size_bytes ? `${Math.max(1, Math.round(row.size_bytes / 1024))} KB` : "—"}</td>
                    <td data-label="Kept until">{when(row.expires_at)}</td>
                    <td data-label="Server note">{row.error_message || "—"}</td>
                    <td>
                      {row.status !== "failed" && row.status !== "pending" ? (
                        <button className="link-btn danger" type="button" onClick={() => { setRestoring(row); setTyped(""); }}>
                          Request restore
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      {restoring ? (
        <ConfirmDialog
          title="Request a restore from this backup?"
          body={
            <>
              <p>The server records the request; it doesn&apos;t replace the database. Type RESTORE to confirm.</p>
              <input aria-label="Type RESTORE to confirm" value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" />
            </>
          }
          confirmLabel="Request restore"
          tone="danger"
          pending={busy}
          onCancel={() => setRestoring(null)}
          onConfirm={async () => {
            if (busy) return;
            if (typed.trim() !== "RESTORE") {
              setNotice({ ok: false, text: "Type RESTORE exactly to request a restore." });
              setRestoring(null);
              return;
            }
            setBusy(true);
            const result = await api<{ message?: string }>(`/super-admin/backups/${restoring.id}/restore`, { method: "POST", body: JSON.stringify({ confirmation: "RESTORE" }) });
            setBusy(false);
            setRestoring(null);
            setNotice(result.ok ? { ok: true, text: result.data.message || "Restore request recorded." } : { ok: false, text: apiErrorMessage(result.data, "Unable to request a restore.") });
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
