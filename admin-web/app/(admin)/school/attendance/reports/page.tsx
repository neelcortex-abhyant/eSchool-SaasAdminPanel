"use client";

import { useCallback, useMemo, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { ATTENDANCE_LIVE_NOTE, ATTENDANCE_TABS, STATUS_SHORT, STATUS_TONE, percentText, todayIso } from "@/components/teaching/attendance";
import { Stat, TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { attendanceRoster, attendanceService, attendanceSupport, STATUS_LABEL, tally } from "@/lib/teaching/attendance";
import type { AttendanceStatus } from "@/lib/teaching/types";
import { IconCheck } from "@/lib/icons";

export default function AttendanceReportPage() {
  return (
    <TeachingPage
      module="attendance"
      title="Monthly attendance report"
      description="Day-by-day attendance for a section over one month, with totals per student."
      icon={<IconCheck width={18} height={18} />}
      tabs={ATTENDANCE_TABS}
      liveNote={ATTENDANCE_LIVE_NOTE}
    >
      <ReportBody />
    </TeachingPage>
  );
}

function daysOf(month: string): string[] {
  const [year, mon] = month.split("-").map(Number);
  const count = new Date(year, mon, 0).getDate();
  return Array.from({ length: count }, (_, index) => `${month}-${String(index + 1).padStart(2, "0")}`);
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function ReportBody() {
  const support = attendanceSupport();
  const [filter, setFilter] = usePlacementFilter();
  const [month, setMonth] = useState(todayIso().slice(0, 7));
  const days = useMemo(() => (/^\d{4}-\d{2}$/.test(month) ? daysOf(month) : []), [month]);
  const ready = Boolean(filter.sessionId && filter.sectionId && days.length);

  const loader = useCallback(async () => {
    const [roster, records] = await Promise.all([
      attendanceRoster(filter.sessionId, filter.sectionId),
      attendanceService().records({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId, from: days[0], to: days[days.length - 1] }),
    ]);
    return [{ roster: roster.filter((student) => student.status === 1).sort((a, b) => (a.roll_number ?? 9999) - (b.roll_number ?? 9999) || a.name.localeCompare(b.name)), records }];
  }, [filter.sessionId, filter.sectionId, days]);
  const state = useOptions(ready ? loader : null);
  const data = state.options[0] ?? null;

  const table = useMemo(() => {
    if (!data) return [];
    return data.roster.map((student) => {
      const mine = data.records.filter((record) => record.student_id === student.id);
      const byDay = new Map(mine.map((record) => [record.date, record.status]));
      return { student, byDay, counts: tally(mine) };
    });
  }, [data]);
  const markedDays = useMemo(() => new Set((data?.records ?? []).map((record) => record.date)), [data]);
  const overall = tally(data?.records.filter((record) => table.some((row) => row.student.id === record.student_id)) ?? []);

  function exportCsv() {
    const header = ["Roll", "Student", "Admission no.", ...days.map((day) => day.slice(8)), "Present", "Absent", "Late", ...(support.leave ? ["Leave"] : []), "Attendance %"];
    const lines = table.map(({ student, byDay, counts }) =>
      [
        student.roll_number ?? "",
        student.name,
        student.admission_no,
        ...days.map((day) => (byDay.get(day) ? STATUS_SHORT[byDay.get(day) as AttendanceStatus] : "")),
        counts.present,
        counts.absent,
        counts.late,
        ...(support.leave ? [counts.leave] : []),
        counts.marked ? counts.percent : "",
      ]
        .map(csvCell)
        .join(","),
    );
    const blob = new Blob([[header.map(csvCell).join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `attendance-${month}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
        <input type="month" aria-label="Month" value={month} max={todayIso().slice(0, 7)} onChange={(event) => setMonth(event.target.value)} />
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={!table.length} onClick={exportCsv}>
          Export CSV
        </button>
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">Choose a section and month to build the report.</div>
        </div>
      ) : state.loading && !data ? (
        <div className="resource-card">
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      ) : data && table.length === 0 ? (
        <div className="resource-card">
          <div className="empty-state">No active students in this section.</div>
        </div>
      ) : data ? (
        <>
          <div className="teach-stats">
            <Stat label="Students" value={table.length} />
            <Stat label="Days marked" value={markedDays.size} />
            <Stat label="Present" value={overall.present} tone="green" />
            <Stat label="Absent" value={overall.absent} tone="red" />
            <Stat label="Late" value={overall.late} tone="amber" />
            {support.leave ? <Stat label="Leave" value={overall.leave} tone="blue" /> : null}
            <Stat label="Attendance" value={percentText(overall.percent, overall.marked)} />
          </div>
          <p className="muted teach-legend">
            {(support.leave ? (["present", "absent", "late", "leave"] as AttendanceStatus[]) : (["present", "absent", "late"] as AttendanceStatus[])).map((status) => (
              <span key={status} className={`teach-cell is-${STATUS_TONE[status]}`}>
                {STATUS_SHORT[status]} = {STATUS_LABEL[status]}
              </span>
            ))}
          </p>
          <div className="resource-card teach-matrix-wrap">
            <table className="teach-matrix">
              <thead>
                <tr>
                  <th scope="col" className="teach-matrix-name">Student</th>
                  {days.map((day) => (
                    <th key={day} scope="col" className={markedDays.has(day) ? "" : "is-off"}>
                      {Number(day.slice(8))}
                    </th>
                  ))}
                  <th scope="col">P</th>
                  <th scope="col">A</th>
                  <th scope="col">L</th>
                  {support.leave ? <th scope="col">LV</th> : null}
                  <th scope="col">%</th>
                </tr>
              </thead>
              <tbody>
                {table.map(({ student, byDay, counts }) => (
                  <tr key={student.id}>
                    <th scope="row" className="teach-matrix-name">
                      {student.roll_number !== null ? `${student.roll_number}. ` : ""}
                      {student.name}
                    </th>
                    {days.map((day) => {
                      const status = byDay.get(day);
                      return (
                        <td key={day} className={status ? `teach-cell is-${STATUS_TONE[status]}` : ""} title={status ? `${day}: ${STATUS_LABEL[status]}` : day}>
                          {status ? STATUS_SHORT[status] : ""}
                        </td>
                      );
                    })}
                    <td>{counts.present}</td>
                    <td>{counts.absent}</td>
                    <td>{counts.late}</td>
                    {support.leave ? <td>{counts.leave}</td> : null}
                    <td>
                      <strong>{percentText(counts.percent, counts.marked)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </>
  );
}
