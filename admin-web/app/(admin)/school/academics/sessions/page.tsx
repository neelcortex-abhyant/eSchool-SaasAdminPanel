"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { AcademicPage } from "@/components/academics/AcademicPage";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, usePagedList } from "@/components/academics/hooks";
import { academicsService, errorMessage, formatDate, type AcademicSession, type SessionInput } from "@/lib/academics";
import { IconCalendar } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("sessions");
const EMPTY: SessionInput = { name: "", start_date: "", end_date: "" };

export default function SessionsPage() {
  const [editing, setEditing] = useState<AcademicSession | "new" | null>(null);
  return (
    <AcademicPage
      feature="sessions"
      title="Academic sessions"
      description="Set up school years and choose the session the school is working in."
      icon={<IconCalendar width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add session
        </button>
      }
    >
      <SessionsBody editing={editing} setEditing={setEditing} />
    </AcademicPage>
  );
}

function SessionsBody({ editing, setEditing }: { editing: AcademicSession | "new" | null; setEditing: (value: AcademicSession | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);
  const [activating, setActivating] = useState<AcademicSession | null>(null);
  const [pending, setPending] = useState(false);

  const loader = useCallback(() => service.listSessions({ page, pageSize: PAGE_SIZE, q: search, status }), [page, search, status]);
  const { data, loading, error, reload } = usePagedList(loader);
  const rows = data?.items ?? [];
  const current = rows.find((row) => row.is_active);

  async function activate() {
    if (!activating) return;
    setPending(true);
    try {
      await service.activateSession(activating.id);
      toast("success", `${activating.name} is now the active session.`);
      setActivating(null);
      await reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to activate the session."));
    } finally {
      setPending(false);
    }
  }

  const columns = useMemo<Column<AcademicSession>[]>(
    () => [
      { key: "name", label: "Session", render: (row) => <strong>{row.name}</strong> },
      { key: "start", label: "Starts", render: (row) => formatDate(row.start_date) },
      { key: "end", label: "Ends", render: (row) => formatDate(row.end_date) },
      { key: "status", label: "Status", render: (row) => <StatusBadge active={row.is_active} /> },
    ],
    [],
  );

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search sessions" placeholder="Search sessions" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as "" | "0" | "1"); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
      </div>

      <ErrorAlert error={error} onRetry={() => void reload()} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={rows}
            loading={loading}
            emptyText={search || status ? "No sessions match these filters." : "No academic sessions yet. Add the current school year to get started."}
            actions={(row) => (
              <>
                <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                  Edit
                </button>
                {!row.is_active ? (
                  <button className="link-btn" type="button" onClick={() => setActivating(row)}>
                    Set active
                  </button>
                ) : null}
              </>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}

      {editing ? (
        <SessionForm
          session={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (saved, created) => {
            setEditing(null);
            toast("success", created ? `${saved.name} added.` : `${saved.name} updated.`);
            await reload();
          }}
        />
      ) : null}

      {activating ? (
        <ConfirmDialog
          title={`Set ${activating.name} as active?`}
          body={
            current && current.id !== activating.id
              ? `${current.name} will become inactive. Classes, assignments and other modules will use ${activating.name} by default.`
              : `Classes, assignments and other modules will use ${activating.name} by default. Any other active session becomes inactive.`
          }
          confirmLabel="Set active"
          pending={pending}
          onConfirm={() => void activate()}
          onCancel={() => setActivating(null)}
        />
      ) : null}
    </>
  );
}

function SessionForm({ session, onClose, onSaved }: { session: AcademicSession | null; onClose: () => void; onSaved: (saved: AcademicSession, created: boolean) => Promise<void> }) {
  const [form, setForm] = useState<SessionInput>(session ? { name: session.name, start_date: session.start_date, end_date: session.end_date } : EMPTY);
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};
    if (!form.name.trim()) next.name = "Enter a session name, such as 2026-27.";
    if (!form.start_date) next.start_date = "Choose a start date.";
    if (!form.end_date) next.end_date = "Choose an end date.";
    if (form.start_date && form.end_date && form.end_date <= form.start_date) next.end_date = "End date must be after the start date.";
    return next;
  }

  async function submit() {
    const invalid = validate();
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      const body = { ...form, name: form.name.trim() };
      const saved = session ? await service.updateSession(session.id, body) : await service.createSession(body);
      await onSaved(saved, !session);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the session.");
      setSaving(false);
    }
  }

  const set = (key: keyof SessionInput) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  return (
    <FormModal
      title={session ? `Edit ${session.name}` : "Add academic session"}
      error={errors.formError}
      saving={saving}
      submitLabel={session ? "Save changes" : "Add session"}
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <TextField id="session-name" label="Session name" required span maxLength={255} placeholder="2026-27" value={form.name} onChange={set("name")} error={errors.fieldErrors.name} />
      <TextField id="session-start" label="Start date" type="date" required value={form.start_date} onChange={set("start_date")} error={errors.fieldErrors.start_date} />
      <TextField id="session-end" label="End date" type="date" required value={form.end_date} onChange={set("end_date")} error={errors.fieldErrors.end_date} />
    </FormModal>
  );
}
