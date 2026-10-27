"use client";

import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, getOne, staffDirectory, type Raw, type StaffRef } from "@/lib/extras/api";
import { num, str } from "@/lib/teaching/client";
import { IconStaff } from "@/lib/icons";

export const STAFF_ATTENDANCE_TABS = [
  { href: "/school/staff-attendance", label: "Mark attendance" },
  { href: "/school/todays-attendance", label: "Today" },
  { href: "/school/attendance-register", label: "Register" },
  { href: "/school/attendance-reports", label: "Reports" },
];

export const ATTENDANCE_STATUSES: { value: string; label: string; tone: ChipTone }[] = [
  { value: "present", label: "Present", tone: "green" },
  { value: "absent", label: "Absent", tone: "red" },
  { value: "late", label: "Late", tone: "amber" },
  { value: "half_day", label: "Half day", tone: "amber" },
  { value: "leave", label: "On leave", tone: "blue" },
];

function statusChip(value: unknown) {
  const status = ATTENDANCE_STATUSES.find((item) => item.value === value);
  return status ? <Chip tone={status.tone}>{status.label}</Chip> : <span className="muted">Not marked</span>;
}

function today() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

type RegisterRow = { id: number; staff: StaffRef; attendance: Raw | null };

/** Everyone on the staff with their attendance for one day. */
function useRegister(day: string) {
  return useOptions(
    useCallback(async () => {
      const [register, people] = await Promise.all([getOne("/staff-attendance/register", { attendance_date: day }), staffDirectory()]);
      const marks = new Map((Array.isArray(register.items) ? (register.items as Raw[]) : []).map((row) => [num(row.staff_id), (row.attendance as Raw | null) ?? null]));
      const rows: RegisterRow[] = people.map((staff) => ({ id: staff.staff_id, staff, attendance: marks.get(staff.staff_id) ?? null }));
      // Staff on the register that the people lists don't show (for example inactive accounts).
      for (const [staffId, attendance] of marks) {
        if (!rows.some((row) => row.id === staffId)) rows.push({ id: staffId, staff: { staff_id: staffId, user_id: 0, name: `Staff #${staffId}`, designation: "", kind: "staff" }, attendance });
      }
      return rows;
    }, [day]),
  );
}

export function MarkStaffAttendance() {
  return (
    <ExtrasPage title="Staff attendance" description="Mark each staff member present, absent, late or on leave for the day." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <MarkBody />
    </ExtrasPage>
  );
}

function MarkBody() {
  const toast = useToast();
  const [day, setDay] = useState(today());
  const register = useRegister(day);
  const [saving, setSaving] = useState<number | "all" | null>(null);

  async function mark(rows: RegisterRow[], status: string) {
    setSaving(rows.length === 1 ? rows[0].id : "all");
    try {
      for (const row of rows) await create("/staff-attendance", { staff_id: row.id, attendance_date: day, status });
      toast("success", rows.length === 1 ? `${rows[0].staff.name}: ${ATTENDANCE_STATUSES.find((item) => item.value === status)?.label}.` : `${rows.length} marked ${status}.`);
      void register.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to save attendance."));
      void register.reload();
    } finally {
      setSaving(null);
    }
  }

  const unmarked = register.options.filter((row) => !row.attendance);
  const columns: Column<RegisterRow>[] = [
    { key: "name", label: "Staff", render: (row) => <div><strong>{row.staff.name}</strong><div className="muted">{row.staff.designation}</div></div> },
    { key: "status", label: "Status", render: (row) => statusChip(row.attendance?.status) },
    {
      key: "mark",
      label: "Mark as",
      render: (row) => (
        <div className="att-choices" role="group" aria-label={`Mark ${row.staff.name}`}>
          {ATTENDANCE_STATUSES.map((status) => (
            <button key={status.value} type="button" className={`att-choice is-${status.tone}`} disabled={saving !== null} aria-pressed={row.attendance?.status === status.value} onClick={() => void mark([row], status.value)}>
              {status.label}
            </button>
          ))}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">
          Date
          <input type="date" value={day} max={today()} onChange={(event) => setDay(event.target.value || today())} />
        </label>
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={!unmarked.length || saving !== null} onClick={() => void mark(unmarked, "present")}>
          {saving === "all" ? "Saving…" : `Mark the other ${unmarked.length} present`}
        </button>
      </div>
      <ErrorAlert error={register.error} onRetry={() => void register.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={register.options} loading={register.loading} emptyText={register.error ? "The register couldn't be loaded." : "No staff on record yet."} />
      </div>
    </>
  );
}

export function TodaysStaffAttendance() {
  return (
    <ExtrasPage title="Today's attendance" description="Who is in today." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <RegisterBody fixedDay />
    </ExtrasPage>
  );
}

export function StaffAttendanceRegister() {
  return (
    <ExtrasPage title="Attendance register" description="Staff attendance for any day." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <RegisterBody />
    </ExtrasPage>
  );
}

function RegisterBody({ fixedDay }: { fixedDay?: boolean }) {
  const [day, setDay] = useState(today());
  const register = useRegister(day);
  const counts = useMemo(() => {
    const by = (value: string) => register.options.filter((row) => row.attendance?.status === value).length;
    return { present: by("present") + by("late") + by("half_day"), absent: by("absent"), leave: by("leave"), unmarked: register.options.filter((row) => !row.attendance).length };
  }, [register.options]);
  const columns: Column<RegisterRow>[] = [
    { key: "name", label: "Staff", render: (row) => <div><strong>{row.staff.name}</strong><div className="muted">{row.staff.designation}</div></div> },
    { key: "status", label: "Status", render: (row) => statusChip(row.attendance?.status) },
    { key: "in", label: "In", render: (row) => displayValue(row.attendance?.check_in) },
    { key: "out", label: "Out", render: (row) => displayValue(row.attendance?.check_out) },
    { key: "remark", label: "Remark", render: (row) => displayValue(row.attendance?.remark) },
  ];
  return (
    <>
      {fixedDay ? null : (
        <div className="school-filters">
          <label className="ops-filter-label">
            Date
            <input type="date" value={day} max={today()} onChange={(event) => setDay(event.target.value || today())} />
          </label>
        </div>
      )}
      <div className="teach-stats">
        <Stat label="In" value={counts.present} tone="green" />
        <Stat label="Absent" value={counts.absent} tone="red" />
        <Stat label="On leave" value={counts.leave} tone="blue" />
        <Stat label="Not marked" value={counts.unmarked} tone="grey" />
      </div>
      <ErrorAlert error={register.error} onRetry={() => void register.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={register.options} loading={register.loading} emptyText={register.error ? "The register couldn't be loaded." : "No staff on record yet."} />
      </div>
    </>
  );
}

export function StaffAttendanceReports() {
  return (
    <ExtrasPage title="Attendance reports" description="Each staff member's attendance over a period." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <ReportsBody />
    </ExtrasPage>
  );
}

type Summary = { id: number; name: string; designation: string; present: number; absent: number; late: number; leave: number; total: number };

/** Days per status for each staff member, from the server's records for the period. */
export function summarise(records: Raw[], people: StaffRef[]): Summary[] {
  const byStaff = new Map<number, Summary>();
  for (const record of records) {
    const id = num(record.staff_id);
    const person = people.find((item) => item.staff_id === id);
    const row = byStaff.get(id) ?? { id, name: person?.name ?? `Staff #${id}`, designation: person?.designation ?? "", present: 0, absent: 0, late: 0, leave: 0, total: 0 };
    const status = str(record.status);
    if (status === "present" || status === "half_day") row.present += 1;
    else if (status === "absent") row.absent += 1;
    else if (status === "late") row.late += 1;
    else if (status === "leave") row.leave += 1;
    row.total += 1;
    byStaff.set(id, row);
  }
  return [...byStaff.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function ReportsBody() {
  const end = today();
  const [from, setFrom] = useState(`${end.slice(0, 8)}01`);
  const [to, setTo] = useState(end);
  const report = useOptions(
    useCallback(async () => {
      const [data, people] = await Promise.all([getOne("/staff-attendance/reports", { from_date: from, to_date: to }), staffDirectory()]);
      return summarise(Array.isArray(data.items) ? (data.items as Raw[]) : [], people);
    }, [from, to]),
  );
  const columns: Column<Summary>[] = [
    { key: "name", label: "Staff", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.designation}</div></div> },
    { key: "present", label: "Present", render: (row) => row.present },
    { key: "late", label: "Late", render: (row) => row.late },
    { key: "absent", label: "Absent", render: (row) => row.absent },
    { key: "leave", label: "On leave", render: (row) => row.leave },
    { key: "rate", label: "Attendance", render: (row) => (row.total ? `${Math.round(((row.present + row.late) / row.total) * 100)}%` : "—") },
  ];
  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">
          From
          <input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        </label>
        <label className="ops-filter-label">
          To
          <input type="date" value={to} min={from} max={end} onChange={(event) => setTo(event.target.value)} />
        </label>
      </div>
      <ErrorAlert error={report.error} onRetry={() => void report.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={report.options} loading={report.loading} emptyText={report.error ? "The report couldn't be loaded." : "No attendance recorded in this period."} />
      </div>
    </>
  );
}
