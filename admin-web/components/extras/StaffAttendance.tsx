"use client";

import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, getOne, listRows, staffDirectory, type Raw, type StaffRef } from "@/lib/extras/api";
import { downloadText, toCsv } from "@/lib/operations/export";
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

/** Search by name or employee ID, and pick a department. */
function useStaffFilter(rows: RegisterRow[]) {
  const [q, setQ] = useState("");
  const [department, setDepartment] = useState("");
  const departments = useMemo(() => [...new Set(rows.map((row) => row.staff.department || "").filter(Boolean))].sort(), [rows]);
  const needle = q.trim().toLowerCase();
  const shown = rows.filter((row) => (!department || row.staff.department === department) && (!needle || `${row.staff.name} ${row.staff.employee_code ?? ""}`.toLowerCase().includes(needle)));
  const controls = (
    <>
      <input type="search" aria-label="Search employees" placeholder="Name or employee ID" value={q} onChange={(event) => setQ(event.target.value)} />
      <select aria-label="Department" value={department} onChange={(event) => setDepartment(event.target.value)}>
        <option value="">All departments</option>
        {departments.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
    </>
  );
  return { shown, controls };
}

function employeeColumns(): Column<RegisterRow>[] {
  return [
    { key: "name", label: "Employee", render: (row) => <div><strong>{row.staff.name}</strong><div className="muted">{row.staff.designation}</div></div> },
    { key: "code", label: "Employee ID", render: (row) => row.staff.employee_code || "—" },
    { key: "department", label: "Department", render: (row) => row.staff.department || "—" },
    { key: "status", label: "Status", render: (row) => statusChip(row.attendance?.status) },
    { key: "in", label: "Check-in", render: (row) => displayValue(row.attendance?.check_in) },
    { key: "out", label: "Check-out", render: (row) => displayValue(row.attendance?.check_out) },
  ];
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Problems with a corrected record before it's sent. */
export function correctionProblems(input: { status: string; check_in: string; check_out: string }): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!ATTENDANCE_STATUSES.some((item) => item.value === input.status)) errors.status = "Choose a status.";
  if (input.check_in && !TIME.test(input.check_in)) errors.check_in = "Use 24-hour time, e.g. 08:45.";
  if (input.check_out && !TIME.test(input.check_out)) errors.check_out = "Use 24-hour time, e.g. 16:30.";
  if (!errors.check_in && !errors.check_out && input.check_in && input.check_out && input.check_out <= input.check_in) errors.check_out = "Check-out must be after check-in.";
  if ((input.status === "absent" || input.status === "leave") && (input.check_in || input.check_out)) errors.status = "An absent or on-leave record can't have check-in times.";
  return errors;
}

/** Change one person's record for a day: status, check-in, check-out and remark (saved with POST, which updates the day's record). */
function CorrectionForm({ row, day, onClose, onSaved }: { row: RegisterRow; day: string; onClose: () => void; onSaved: () => void }) {
  const [status, setStatus] = useState(str(row.attendance?.status, "present"));
  const [checkIn, setCheckIn] = useState(str(row.attendance?.check_in).slice(0, 5));
  const [checkOut, setCheckOut] = useState(str(row.attendance?.check_out).slice(0, 5));
  const [remark, setRemark] = useState(str(row.attendance?.remark));
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    const invalid = correctionProblems({ status, check_in: checkIn, check_out: checkOut });
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await create("/staff-attendance", { staff_id: row.id, attendance_date: day, status, check_in: checkIn || null, check_out: checkOut || null, remark: remark.trim() || null });
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to save the correction.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="Correct attendance" description={`${row.staff.name} · ${day}`} error={errors.formError} saving={saving} submitLabel="Save correction" onSubmit={() => void submit()} onClose={onClose}>
      <SelectField id="sa-status" label="Status" required value={status} onChange={setStatus} options={ATTENDANCE_STATUSES.map((item) => ({ value: item.value, label: item.label }))} error={errors.fieldErrors.status} />
      <TextField id="sa-in" label="Check-in" type="time" value={checkIn} onChange={setCheckIn} error={errors.fieldErrors.check_in} />
      <TextField id="sa-out" label="Check-out" type="time" value={checkOut} onChange={setCheckOut} error={errors.fieldErrors.check_out} />
      <TextField id="sa-remark" label="Remark" maxLength={255} value={remark} onChange={setRemark} hint="Why it was changed, e.g. “Forgot to check in”." span />
    </FormModal>
  );
}

function MarkBody() {
  const toast = useToast();
  const [day, setDay] = useState(today());
  const register = useRegister(day);
  const filter = useStaffFilter(register.options);
  const [saving, setSaving] = useState<number | "all" | null>(null);
  const [fixing, setFixing] = useState<RegisterRow | null>(null);

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

  const unmarked = filter.shown.filter((row) => !row.attendance);
  const columns: Column<RegisterRow>[] = [
    ...employeeColumns(),
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
        {filter.controls}
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={!unmarked.length || saving !== null} onClick={() => void mark(unmarked, "present")}>
          {saving === "all" ? "Saving…" : `Mark the other ${unmarked.length} present`}
        </button>
      </div>
      <ErrorAlert error={register.error} onRetry={() => void register.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={filter.shown}
          loading={register.loading}
          emptyText={register.error ? "The register couldn't be loaded." : register.options.length ? "No one matches these filters." : "No staff on record yet."}
          actions={(row) => <button className="link-btn" type="button" onClick={() => setFixing(row)}>Times</button>}
        />
      </div>
      {fixing ? (
        <CorrectionForm
          row={fixing}
          day={day}
          onClose={() => setFixing(null)}
          onSaved={() => {
            setFixing(null);
            toast("success", "Attendance saved.");
            void register.reload();
          }}
        />
      ) : null}
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
    <ExtrasPage title="Attendance register" description="Staff attendance for any day, with check-in and check-out times. Correct a record if it's wrong." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <RegisterBody />
    </ExtrasPage>
  );
}

function RegisterBody({ fixedDay }: { fixedDay?: boolean }) {
  const toast = useToast();
  const [day, setDay] = useState(today());
  const register = useRegister(day);
  const filter = useStaffFilter(register.options);
  const [fixing, setFixing] = useState<RegisterRow | null>(null);
  const counts = useMemo(() => {
    const by = (value: string) => filter.shown.filter((row) => row.attendance?.status === value).length;
    return { present: by("present") + by("late") + by("half_day"), late: by("late"), absent: by("absent"), leave: by("leave"), unmarked: filter.shown.filter((row) => !row.attendance).length };
  }, [filter.shown]);
  const columns: Column<RegisterRow>[] = [...employeeColumns(), { key: "remark", label: "Remark", render: (row) => displayValue(row.attendance?.remark) }];
  return (
    <>
      <div className="school-filters">
        {fixedDay ? null : (
          <label className="ops-filter-label">
            Date
            <input type="date" value={day} max={today()} onChange={(event) => setDay(event.target.value || today())} />
          </label>
        )}
        {filter.controls}
      </div>
      <div className="teach-stats">
        <Stat label="In" value={counts.present} tone="green" />
        <Stat label="Late" value={counts.late} tone="amber" />
        <Stat label="Absent" value={counts.absent} tone="red" />
        <Stat label="On leave" value={counts.leave} tone="blue" />
        <Stat label="Not marked" value={counts.unmarked} tone="grey" />
      </div>
      <ErrorAlert error={register.error} onRetry={() => void register.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={filter.shown}
          loading={register.loading}
          emptyText={register.error ? "The register couldn't be loaded." : register.options.length ? "No one matches these filters." : "No staff on record yet."}
          actions={(row) => <button className="link-btn" type="button" onClick={() => setFixing(row)}>Correct</button>}
        />
      </div>
      {fixing ? (
        <CorrectionForm
          row={fixing}
          day={day}
          onClose={() => setFixing(null)}
          onSaved={() => {
            setFixing(null);
            toast("success", "Attendance corrected.");
            void register.reload();
          }}
        />
      ) : null}
    </>
  );
}

export function StaffAttendanceReports() {
  return (
    <ExtrasPage title="Attendance reports" description="Each employee's attendance for a month or any period." icon={<IconStaff width={18} height={18} />} tabs={STAFF_ATTENDANCE_TABS}>
      <ReportsBody />
    </ExtrasPage>
  );
}

export type Summary = { id: number; name: string; designation: string; employee_code: string; department: string; present: number; absent: number; late: number; leave: number; total: number };

/** Days per status for each staff member, from the server's records for the period. */
export function summarise(records: Raw[], people: StaffRef[]): Summary[] {
  const byStaff = new Map<number, Summary>();
  for (const record of records) {
    const id = num(record.staff_id);
    const person = people.find((item) => item.staff_id === id);
    const row = byStaff.get(id) ?? { id, name: person?.name ?? `Staff #${id}`, designation: person?.designation ?? "", employee_code: person?.employee_code ?? "", department: person?.department ?? "", present: 0, absent: 0, late: 0, leave: 0, total: 0 };
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

/** Monday–Saturday days in the period that aren't school holidays. */
export function workingDays(from: string, to: string, holidays: { holiday_date: string; end_date: string | null }[]): number {
  const off = new Set<string>();
  for (const holiday of holidays) {
    const start = new Date(`${holiday.holiday_date.slice(0, 10)}T00:00:00`);
    const end = new Date(`${(holiday.end_date || holiday.holiday_date).slice(0, 10)}T00:00:00`);
    for (let day = start; day <= end; day = new Date(day.getTime() + 86_400_000)) off.add(day.toDateString());
  }
  let count = 0;
  const last = new Date(`${to}T00:00:00`);
  for (let day = new Date(`${from}T00:00:00`); day <= last; day = new Date(day.getTime() + 86_400_000)) {
    if (day.getDay() !== 0 && !off.has(day.toDateString())) count += 1;
  }
  return count;
}

function ReportsBody() {
  const toast = useToast();
  const end = today();
  const [from, setFrom] = useState(`${end.slice(0, 8)}01`);
  const [to, setTo] = useState(end);
  const [department, setDepartment] = useState("");
  const report = useOptions(
    useCallback(async () => {
      const [data, people, holidays] = await Promise.all([getOne("/staff-attendance/reports", { from_date: from, to_date: to }), staffDirectory(), listRows("/holidays").catch(() => [] as Raw[])]);
      const days = workingDays(from, to, holidays.map((row) => ({ holiday_date: str(row.holiday_date), end_date: str(row.end_date) || null })));
      const recorded = summarise(Array.isArray(data.items) ? (data.items as Raw[]) : [], people);
      // Everyone on the staff appears, including people with no records in the period.
      const all = people.map((person) => recorded.find((row) => row.id === person.staff_id) ?? { id: person.staff_id, name: person.name, designation: person.designation, employee_code: person.employee_code ?? "", department: person.department ?? "", present: 0, absent: 0, late: 0, leave: 0, total: 0 });
      return all.map((row) => ({ ...row, working: days }));
    }, [from, to]),
  );
  const departments = [...new Set(report.options.map((row) => row.department).filter(Boolean))].sort();
  const rows = report.options.filter((row) => !department || row.department === department);
  const rate = (row: (typeof rows)[number]) => (row.working ? Math.round(((row.present + row.late) / row.working) * 100) : 0);
  const columns: Column<(typeof rows)[number]>[] = [
    { key: "name", label: "Employee", render: (row) => <div><strong>{row.name}</strong><div className="muted">{row.employee_code ? `${row.employee_code} · ` : ""}{row.designation}</div></div> },
    { key: "department", label: "Department", render: (row) => row.department || "—" },
    { key: "working", label: "Working days", render: (row) => row.working },
    { key: "present", label: "Present", render: (row) => row.present },
    { key: "late", label: "Late", render: (row) => row.late },
    { key: "absent", label: "Absent", render: (row) => row.absent },
    { key: "leave", label: "Leave", render: (row) => row.leave },
    { key: "unmarked", label: "Not marked", render: (row) => Math.max(row.working - row.total, 0) },
    { key: "rate", label: "Attendance", render: (row) => (row.working ? `${rate(row)}%` : "—") },
  ];
  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">
          Month
          <input type="month" value={from.slice(0, 7)} max={end.slice(0, 7)} onChange={(event) => {
            const month = event.target.value;
            if (!month) return;
            const last = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate();
            setFrom(`${month}-01`);
            setTo(`${month}-${String(last).padStart(2, "0")}` > end ? end : `${month}-${String(last).padStart(2, "0")}`);
          }} />
        </label>
        <label className="ops-filter-label">
          From
          <input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        </label>
        <label className="ops-filter-label">
          To
          <input type="date" value={to} min={from} max={end} onChange={(event) => setTo(event.target.value)} />
        </label>
        <select aria-label="Department" value={department} onChange={(event) => setDepartment(event.target.value)}>
          <option value="">All departments</option>
          {departments.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          disabled={!rows.length}
          onClick={() => {
            downloadText(
              `staff-attendance-${from}-to-${to}.csv`,
              toCsv(rows, [
                { label: "Employee", value: (row) => row.name },
                { label: "Employee ID", value: (row) => row.employee_code },
                { label: "Department", value: (row) => row.department },
                { label: "Working days", value: (row) => row.working },
                { label: "Present", value: (row) => row.present },
                { label: "Late", value: (row) => row.late },
                { label: "Absent", value: (row) => row.absent },
                { label: "Leave", value: (row) => row.leave },
                { label: "Not marked", value: (row) => Math.max(row.working - row.total, 0) },
                { label: "Attendance %", value: (row) => rate(row) },
              ]),
            );
            toast("success", "Report downloaded.");
          }}
        >
          Export CSV
        </button>
      </div>
      <ErrorAlert error={report.error} onRetry={() => void report.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={rows} loading={report.loading} emptyText={report.error ? "The report couldn't be loaded." : "No staff in this department."} />
      </div>
    </>
  );
}
