"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { staffDirectory } from "@/lib/extras/api";
import { balances, createLeave, LEAVE_STATUS, leaveDays, leaveTypeProblems, loadLeaves, loadLeaveSettings, saveLeaveSettings, setLeaveStatus, type LeaveSettings } from "@/lib/operations/leave";
import type { LeaveRequest, LeaveStatus, LeaveType } from "@/lib/operations/types";
import { IconCalendar, IconSettings } from "@/lib/icons";

const STATUS_TONE: Record<LeaveStatus, ChipTone> = { 0: "amber", 1: "green", 2: "red" };
const PAGE_SIZE = 20;

export const LEAVE_TABS = [
  { href: "/school/staff-leave", label: "Leave requests" },
  { href: "/school/leave-settings", label: "Leave types" },
  { href: "/school/leave-report", label: "Leave report" },
];

function statusChip(status: LeaveStatus) {
  return <Chip tone={STATUS_TONE[status]}>{LEAVE_STATUS[status]}</Chip>;
}

/** Leaves matching the page's filters. */
export function filterLeaves(rows: LeaveRequest[], filter: { status: string; userId: string; type: string; q: string; from: string; to: string }): LeaveRequest[] {
  const needle = filter.q.trim().toLowerCase();
  return rows.filter(
    (row) =>
      (filter.status === "" || String(row.status) === filter.status) &&
      (!filter.userId || String(row.user_id) === filter.userId) &&
      (!filter.type || (row.leave_type ?? "") === filter.type) &&
      (!filter.from || row.to_date >= filter.from) &&
      (!filter.to || row.from_date <= filter.to) &&
      (!needle || `${row.person_name} ${row.reason}`.toLowerCase().includes(needle)),
  );
}

export function StaffLeavePage() {
  const [adding, setAdding] = useState(false);
  return (
    <ExtrasPage
      title="Staff leave"
      description="Leave requests from teachers and staff: approve or reject them, and see what each person has left."
      icon={<IconCalendar width={18} height={18} />}
      tabs={LEAVE_TABS}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setAdding(true)}>
          Add leave
        </button>
      }
    >
      <LeaveBody adding={adding} setAdding={setAdding} />
    </ExtrasPage>
  );
}

function LeaveBody({ adding, setAdding }: { adding: boolean; setAdding: (value: boolean) => void }) {
  const toast = useToast();
  const settings = useOptions(useCallback(() => loadLeaveSettings().then((row) => [row]), []));
  const types = settings.options[0]?.types;
  const leaves = useOptions(useCallback(() => (types ? loadLeaves(types) : Promise.resolve([] as LeaveRequest[])), [types]));
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [filter, setFilter] = useState({ status: "0", userId: "", type: "", q: "", from: "", to: "" });
  const [page, setPage] = useState(1);
  const [deciding, setDeciding] = useState<{ row: LeaveRequest; status: 1 | 2 } | null>(null);
  const [pending, setPending] = useState(false);
  const [history, setHistory] = useState<number | null>(null);

  // Only teachers' and staff members' leave belongs here; students have their own page.
  const staffLeaves = useMemo(() => leaves.options.filter((row) => row.kind !== "student"), [leaves.options]);
  const rows = filterLeaves(staffLeaves, filter);
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const set = (patch: Partial<typeof filter>) => {
    setFilter((current) => ({ ...current, ...patch }));
    setPage(1);
  };

  const columns: Column<LeaveRequest>[] = [
    { key: "person", label: "Employee", render: (row) => <button className="link-btn" type="button" onClick={() => setHistory(row.user_id)}><strong>{row.person_name}</strong></button> },
    { key: "type", label: "Leave type", render: (row) => row.leave_type ?? <span className="muted">Not set</span> },
    { key: "dates", label: "Dates", render: (row) => <div>{row.from_date}{row.to_date !== row.from_date ? ` → ${row.to_date}` : ""}<div className="muted">{row.days} day{row.days === 1 ? "" : "s"}</div></div> },
    { key: "reason", label: "Reason", render: (row) => row.reason },
    { key: "status", label: "Status", render: (row) => statusChip(row.status) },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Status" value={filter.status} onChange={(event) => set({ status: event.target.value })}>
          <option value="">All requests</option>
          <option value="0">Pending</option>
          <option value="1">Approved</option>
          <option value="2">Rejected</option>
        </select>
        <select aria-label="Employee" value={filter.userId} onChange={(event) => set({ userId: event.target.value })}>
          <option value="">All employees</option>
          {people.options.filter((row) => row.user_id).map((row) => <option key={row.user_id} value={row.user_id}>{row.name}</option>)}
        </select>
        <select aria-label="Leave type" value={filter.type} onChange={(event) => set({ type: event.target.value })}>
          <option value="">All types</option>
          {(types ?? []).map((type) => <option key={type.key} value={type.name}>{type.name}</option>)}
        </select>
        <label className="ops-filter-label">From <input type="date" value={filter.from} onChange={(event) => set({ from: event.target.value })} /></label>
        <label className="ops-filter-label">To <input type="date" value={filter.to} onChange={(event) => set({ to: event.target.value })} /></label>
        <input type="search" aria-label="Search leave" placeholder="Name or reason" value={filter.q} onChange={(event) => set({ q: event.target.value })} />
      </div>
      <div className="teach-stats">
        <Stat label="Waiting for a decision" value={staffLeaves.filter((row) => row.status === 0).length} tone="amber" />
        <Stat label="Approved" value={staffLeaves.filter((row) => row.status === 1).length} tone="green" />
        <Stat label="Rejected" value={staffLeaves.filter((row) => row.status === 2).length} tone="red" />
      </div>
      <ErrorAlert error={settings.error ?? leaves.error} onRetry={() => void leaves.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={shown}
          loading={leaves.loading || settings.loading}
          emptyText={filter.status === "0" ? "No leave is waiting for a decision." : "No leave matches these filters."}
          actions={(row) =>
            row.status === 0 ? (
              <>
                <button className="link-btn" type="button" onClick={() => setDeciding({ row, status: 1 })}>Approve</button>
                <button className="link-btn danger" type="button" onClick={() => setDeciding({ row, status: 2 })}>Reject</button>
              </>
            ) : (
              <button className="link-btn" type="button" onClick={() => setDeciding({ row, status: row.status === 1 ? 2 : 1 })}>
                {row.status === 1 ? "Reject instead" : "Approve instead"}
              </button>
            )
          }
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </div>
      {deciding ? (
        <ConfirmDialog
          title={deciding.status === 1 ? "Approve this leave?" : "Reject this leave?"}
          body={`${deciding.row.person_name}: ${deciding.row.leave_type ?? "Leave"}, ${deciding.row.from_date}${deciding.row.to_date !== deciding.row.from_date ? ` to ${deciding.row.to_date}` : ""} (${deciding.row.days} day${deciding.row.days === 1 ? "" : "s"}).`}
          confirmLabel={deciding.status === 1 ? "Approve" : "Reject"}
          tone={deciding.status === 2 ? "danger" : "default"}
          pending={pending}
          onCancel={() => setDeciding(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await setLeaveStatus(deciding.row.id, deciding.status);
              toast("success", deciding.status === 1 ? "Leave approved." : "Leave rejected.");
              void leaves.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to change the leave."));
            } finally {
              setPending(false);
              setDeciding(null);
            }
          }}
        />
      ) : null}
      {adding && types ? (
        <LeaveForm
          types={types}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            toast("success", "Leave added as pending.");
            void leaves.reload();
          }}
        />
      ) : null}
      {history !== null && types ? <HistoryDialog userId={history} leaves={staffLeaves} types={types} onClose={() => setHistory(null)} /> : null}
    </>
  );
}

function LeaveForm({ types, onClose, onSaved }: { types: LeaveType[]; onClose: () => void; onSaved: () => void }) {
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const session = useCurrentSessionId();
  const [userId, setUserId] = useState("");
  const [type, setType] = useState(types[0]?.name ?? "");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    errors.clear();
    setSaving(true);
    try {
      await createLeave({ user_id: Number(userId), leave_type: type, reason, from_date: from, to_date: to, session_year_id: Number(session) });
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to add the leave.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="Add leave" description="Recorded as pending; approve it from the list." error={errors.formError} saving={saving} submitLabel="Add leave" onSubmit={() => void submit()} onClose={onClose}>
      <SelectField id="lv-user" label="Employee" required placeholder="Choose someone" loading={people.loading} value={userId} onChange={setUserId} options={people.options.filter((row) => row.user_id).map((row) => ({ value: String(row.user_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }))} error={errors.fieldErrors.user_id} />
      <SelectField id="lv-type" label="Leave type" required value={type} onChange={setType} options={types.filter((row) => row.applies_to !== "student").map((row) => ({ value: row.name, label: row.name }))} error={errors.fieldErrors.leave_type} />
      <TextField id="lv-from" label="First day" type="date" required value={from} onChange={setFrom} error={errors.fieldErrors.from_date} />
      <TextField id="lv-to" label="Last day" type="date" required value={to} onChange={setTo} error={errors.fieldErrors.to_date} hint={from && to && to >= from ? `${leaveDays(from, to)} day(s)` : undefined} />
      <TextAreaField id="lv-reason" label="Reason" required value={reason} onChange={setReason} error={errors.fieldErrors.reason ?? errors.fieldErrors.session_year_id} span />
    </FormModal>
  );
}

function HistoryDialog({ userId, leaves, types, onClose }: { userId: number; leaves: LeaveRequest[]; types: LeaveType[]; onClose: () => void }) {
  const mine = leaves.filter((row) => row.user_id === userId);
  const name = mine[0]?.person_name ?? "Employee";
  const year = new Date().getFullYear();
  const left = balances(leaves, userId, types, year);
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card acad-modal" role="dialog" aria-modal="true" aria-labelledby="lh-title">
        <h2 id="lh-title">{name}</h2>
        <p className="muted">Leave balance for {year} and full history.</p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th scope="col">Type</th><th scope="col">Allowed</th><th scope="col">Used</th><th scope="col">Pending</th><th scope="col">Left</th></tr>
            </thead>
            <tbody>
              {left.map((row) => (
                <tr key={row.type.key}>
                  <td>{row.type.name}</td>
                  <td>{row.allowed}</td>
                  <td>{row.used}</td>
                  <td>{row.pending}</td>
                  <td><strong>{row.allowed ? row.remaining : "—"}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>History</h3>
        {mine.length ? (
          <ul className="teach-list">
            {mine.map((row) => (
              <li key={row.id}>
                {row.from_date}{row.to_date !== row.from_date ? ` → ${row.to_date}` : ""} · {row.leave_type ?? "Leave"} · {row.reason} · {statusChip(row.status)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No leave on record.</p>
        )}
        <div className="resource-actions acad-modal-actions">
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ---------- Leave types (leave settings) ----------

export function LeaveConfigPage() {
  return (
    <ExtrasPage title="Leave types" description="The kinds of leave staff can take and how many days a year each allows." icon={<IconSettings width={18} height={18} />} tabs={LEAVE_TABS}>
      <LeaveConfigBody />
    </ExtrasPage>
  );
}

function LeaveConfigBody() {
  const toast = useToast();
  const state = useOptions(useCallback(() => loadLeaveSettings().then((row) => [row]), []));
  const [draft, setDraft] = useState<LeaveSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [problems, setProblems] = useState<Record<string, string>>({});
  useEffect(() => {
    if (state.options[0]) setDraft(state.options[0]);
  }, [state.options]);

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!draft) return <div className="resource-card"><div className="skeleton" style={{ height: 200 }} /></div>;

  const setType = (index: number, patch: Partial<LeaveType>) => setDraft({ ...draft, types: draft.types.map((type, i) => (i === index ? { ...type, ...patch } : type)) });

  async function save() {
    if (!draft) return;
    const found = leaveTypeProblems(draft.types);
    setProblems(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    try {
      await saveLeaveSettings(draft);
      toast("success", "Leave types saved.");
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to save the leave types."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="resource-card"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <fieldset className="form-field ops-lines">
        <legend>Leave types</legend>
        {draft.types.map((type, index) => (
          <div key={index} className="ops-line ops-line-3">
            <input aria-label={`Leave type ${index + 1} name`} placeholder="Casual leave" maxLength={60} value={type.name} className={problems[`types.${index}`] ? "invalid" : undefined} onChange={(event) => setType(index, { name: event.target.value })} />
            <input aria-label={`${type.name || "Leave type"} days per year`} type="number" min={0} max={365} value={type.days_per_year} onChange={(event) => setType(index, { days_per_year: Number(event.target.value) })} />
            <select aria-label={`${type.name || "Leave type"} applies to`} value={type.applies_to} onChange={(event) => setType(index, { applies_to: event.target.value as LeaveType["applies_to"] })}>
              <option value="staff">Staff</option>
              <option value="student">Students</option>
              <option value="all">Everyone</option>
            </select>
            <button className="link-btn danger" type="button" disabled={draft.types.length <= 1} onClick={() => setDraft({ ...draft, types: draft.types.filter((_, i) => i !== index) })}>
              Remove<span className="acad-sr"> {type.name}</span>
            </button>
            {problems[`types.${index}`] ? <p className="field-error ops-line-error">{problems[`types.${index}`]}</p> : null}
          </div>
        ))}
        <div className="ops-line-foot">
          <button className="link-btn" type="button" onClick={() => setDraft({ ...draft, types: [...draft.types, { key: "", name: "", days_per_year: 0, applies_to: "staff" }] })}>
            + Add leave type
          </button>
          <span className="muted">0 days means no yearly limit.</span>
        </div>
        {problems.types ? <p className="field-error">{problems.types}</p> : null}
      </fieldset>
      <div className="resource-fields">
        <SelectField id="lc-approval" label="Who approves leave" value={draft.approval} onChange={(value) => setDraft({ ...draft, approval: value })} options={[{ value: "admin", label: "School admin" }, { value: "class_teacher", label: "Class teacher (students)" }]} />
        <TextAreaField id="lc-notes" label="Notes" value={draft.notes} onChange={(value) => setDraft({ ...draft, notes: value })} span />
      </div>
      <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={saving}>
        {saving ? "Saving…" : "Save leave types"}
      </button>
    </form>
  );
}
