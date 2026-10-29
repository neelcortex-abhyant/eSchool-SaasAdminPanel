"use client";

import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ATTENDANCE_LIVE_NOTE, ATTENDANCE_TABS, AttendanceChip, percentText, todayIso } from "@/components/teaching/attendance";
import { formatDateTime, Stat, TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { attendanceRoster, attendanceService, attendanceSupport, STATUS_LABEL, tally } from "@/lib/teaching/attendance";
import type { AttendanceRecord, AttendanceStatus } from "@/lib/teaching/types";
import { IconCheck } from "@/lib/icons";

export default function AttendanceHistoryPage() {
  return (
    <TeachingPage
      module="attendance"
      title="Student attendance history"
      description="One student's attendance over a date range."
      icon={<IconCheck width={18} height={18} />}
      tabs={ATTENDANCE_TABS}
      liveNote={ATTENDANCE_LIVE_NOTE}
    >
      <HistoryBody />
    </TeachingPage>
  );
}

function monthStart(): string {
  return `${todayIso().slice(0, 8)}01`;
}

function HistoryBody() {
  const toast = useToast();
  const support = attendanceSupport();
  const [filter, setFilter] = usePlacementFilter();
  const [studentId, setStudentId] = useState<number | "">("");
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(todayIso());
  const [correcting, setCorrecting] = useState<AttendanceRecord | null>(null);

  const rosterLoader = useCallback(() => attendanceRoster(filter.sessionId, filter.sectionId), [filter.sessionId, filter.sectionId]);
  const roster = useOptions(filter.sectionId ? rosterLoader : null);

  const ready = Boolean(studentId && from && to && from <= to);
  const loader = useCallback(
    () => attendanceService().records({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId, studentId, from, to }),
    [filter.sessionId, filter.sectionId, studentId, from, to],
  );
  const records = useOptions(ready ? loader : null);
  const rows = useMemo(() => [...records.options].sort((a, b) => b.date.localeCompare(a.date)), [records.options]);
  const counts = tally(rows);

  const columns: Column<AttendanceRecord>[] = [
    { key: "date", label: "Date", render: (row) => new Date(`${row.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" }) },
    { key: "status", label: "Status", render: (row) => <AttendanceChip status={row.status} /> },
    { key: "remark", label: "Remark", render: (row) => row.remark ?? "—" },
    ...(support.correction
      ? [
          {
            key: "history",
            label: "Corrections",
            render: (row: AttendanceRecord) =>
              row.history.length ? (
                <span className="muted">
                  Was {STATUS_LABEL[row.history[0].status]} · changed {formatDateTime(row.history[0].changed_at)}
                  {row.history.length > 1 ? ` (+${row.history.length - 1} earlier)` : ""}
                </span>
              ) : (
                "—"
              ),
          },
        ]
      : []),
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters
          sessionId={filter.sessionId}
          classId={filter.classId}
          sectionId={filter.sectionId}
          onChange={(next) => {
            setFilter(next);
            setStudentId("");
          }}
        />
        <select aria-label="Student" value={studentId} disabled={!filter.sectionId} onChange={(event) => setStudentId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">{!filter.sectionId ? "Choose a section first" : roster.loading ? "Loading students…" : "Choose a student"}</option>
          {roster.options.map((student) => (
            <option key={student.id} value={student.id}>
              {student.name} · {student.admission_no}
            </option>
          ))}
        </select>
        <input type="date" aria-label="From" value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        <input type="date" aria-label="To" value={to} min={from} max={todayIso()} onChange={(event) => setTo(event.target.value)} />
      </div>
      <ErrorAlert error={roster.error ?? records.error} onRetry={() => void (roster.error ? roster.reload() : records.reload())} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">{from > to ? "The start date must be on or before the end date." : "Choose a section and a student to see their attendance."}</div>
        </div>
      ) : (
        <>
          <div className="teach-stats">
            <Stat label="Days marked" value={records.loading ? "…" : counts.marked} />
            <Stat label="Present" value={counts.present} tone="green" />
            <Stat label="Absent" value={counts.absent} tone="red" />
            <Stat label="Late" value={counts.late} tone="amber" />
            {support.leave ? <Stat label="Leave" value={counts.leave} tone="blue" /> : null}
            <Stat label="Attendance" value={percentText(counts.percent, counts.marked)} />
          </div>
          <div className="resource-card">
            <DataTable
              columns={columns}
              rows={rows}
              loading={records.loading}
              emptyText={records.error ? "Attendance couldn't be loaded." : "No attendance recorded for this student in these dates."}
              actions={
                support.correction
                  ? (row) => (
                      <button className="link-btn" type="button" onClick={() => setCorrecting(row)}>
                        Correct
                      </button>
                    )
                  : undefined
              }
            />
          </div>
        </>
      )}
      {correcting ? (
        <CorrectionForm
          record={correcting}
          onClose={() => setCorrecting(null)}
          onSaved={() => {
            setCorrecting(null);
            toast("success", "Attendance corrected. The previous value is kept in the history.");
            void records.reload();
          }}
        />
      ) : null}
    </>
  );
}

function CorrectionForm({ record, onClose, onSaved }: { record: AttendanceRecord; onClose: () => void; onSaved: () => void }) {
  const support = attendanceSupport();
  const [status, setStatus] = useState<AttendanceStatus>(record.status);
  const [remark, setRemark] = useState(record.remark ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const statuses: AttendanceStatus[] = support.leave ? ["present", "absent", "late", "leave"] : ["present", "absent", "late"];

  async function submit() {
    if (status === record.status && remark.trim() === (record.remark ?? "")) {
      errors.setFormError("Change the status or remark to save a correction.");
      return;
    }
    setSaving(true);
    try {
      await attendanceService().correct(record.id, status, remark.trim() || null);
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to correct the attendance.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={`Correct attendance · ${record.student_name}`}
      description={`${record.date}: currently ${STATUS_LABEL[record.status]}${record.remark ? ` (“${record.remark}”)` : ""}.`}
      error={errors.formError}
      saving={saving}
      submitLabel="Save correction"
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <SelectField id="cor-status" label="Status" required value={status} onChange={(value) => setStatus(value as AttendanceStatus)} options={statuses.map((value) => ({ value, label: STATUS_LABEL[value] }))} />
      <TextField id="cor-remark" label="Remark" maxLength={255} value={remark} onChange={setRemark} hint="Say why it changed, e.g. “Arrived with a late pass”." />
      {record.history.length ? (
        <div className="form-field field-span">
          <span className="field-label">Earlier values</span>
          <ul className="teach-list">
            {record.history.map((item, index) => (
              <li key={index}>
                {STATUS_LABEL[item.status]}
                {item.remark ? ` (“${item.remark}”)` : ""} · until {formatDateTime(item.changed_at)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </FormModal>
  );
}
