"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { sessionLabel, useSessions } from "@/components/people/academicOptions";
import { ATTENDANCE_LIVE_NOTE, ATTENDANCE_TABS, percentText, todayIso } from "@/components/teaching/attendance";
import { Chip, Stat, TeachingPage } from "@/components/teaching/Frame";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { attendanceRoster, attendanceService, attendanceSupport, tally } from "@/lib/teaching/attendance";
import { IconCheck } from "@/lib/icons";

type SectionRow = {
  id: number;
  label: string;
  students: number;
  present: number;
  absent: number;
  late: number;
  leave: number;
  marked: number;
  percent: number;
};

export default function AttendanceDashboardPage() {
  return (
    <TeachingPage
      module="attendance"
      title="Student attendance"
      description="Daily attendance by class and section. Pick a date to see who was present."
      icon={<IconCheck width={18} height={18} />}
      tabs={ATTENDANCE_TABS}
      liveNote={ATTENDANCE_LIVE_NOTE}
      actions={
        <Link className="btn-pill btn-pill-green" href="/school/attendance/mark">
          Mark attendance
        </Link>
      }
    >
      <DashboardBody />
    </TeachingPage>
  );
}

function DashboardBody() {
  const sessions = useSessions();
  const currentSessionId = useCurrentSessionId();
  const [chosenSession, setChosenSession] = useState<number | "" | null>(null);
  const sessionId = chosenSession ?? currentSessionId;
  const [date, setDate] = useState(todayIso());
  const support = attendanceSupport();

  const loader = useCallback(async () => {
    const [records, roster] = await Promise.all([
      attendanceService().records({ sessionYearId: sessionId, from: date, to: date }),
      attendanceRoster(sessionId),
    ]);
    const sections = new Map<number, SectionRow>();
    for (const student of roster) {
      if (student.status !== 1 && String(student.status) !== "1") continue;
      const row = sections.get(student.class_section_id) ?? {
        id: student.class_section_id,
        label: `${student.class_name} ${student.section_name}`.trim(),
        students: 0,
        present: 0,
        absent: 0,
        late: 0,
        leave: 0,
        marked: 0,
        percent: 0,
      };
      row.students += 1;
      sections.set(student.class_section_id, row);
    }
    for (const row of sections.values()) {
      const counts = tally(records.filter((record) => record.class_section_id === row.id));
      Object.assign(row, { present: counts.present, absent: counts.absent, late: counts.late, leave: counts.leave, marked: counts.marked, percent: counts.percent });
    }
    return [...sections.values()].sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  }, [sessionId, date]);
  const state = useOptions(sessionId ? loader : null);

  const totals = useMemo(() => {
    const rows = state.options;
    const sum = (key: keyof SectionRow) => rows.reduce((total, row) => total + Number(row[key]), 0);
    const marked = sum("marked");
    return {
      students: sum("students"),
      present: sum("present"),
      absent: sum("absent"),
      late: sum("late"),
      leave: sum("leave"),
      marked,
      percent: marked ? Math.round(((sum("present") + sum("late")) / marked) * 1000) / 10 : 0,
      pendingSections: rows.filter((row) => row.marked < row.students).length,
    };
  }, [state.options]);

  const columns: Column<SectionRow>[] = [
    { key: "class", label: "Class", render: (row) => <strong>{row.label}</strong> },
    { key: "students", label: "Students", render: (row) => row.students },
    { key: "present", label: "Present", render: (row) => row.present },
    { key: "absent", label: "Absent", render: (row) => row.absent },
    { key: "late", label: "Late", render: (row) => row.late },
    ...(support.leave ? [{ key: "leave", label: "Leave", render: (row: SectionRow) => row.leave }] : []),
    { key: "percent", label: "Attendance", render: (row) => percentText(row.percent, row.marked) },
    {
      key: "state",
      label: "Status",
      render: (row) =>
        row.marked === 0 ? <Chip tone="grey">Not marked</Chip> : row.marked < row.students ? <Chip tone="amber">{row.students - row.marked} left</Chip> : <Chip tone="green">Complete</Chip>,
    },
  ];

  return (
    <>
      <div className="school-filters">
        <select aria-label="Academic session" value={sessionId} onChange={(event) => setChosenSession(event.target.value ? Number(event.target.value) : "")}>
          <option value="">{sessions.loading ? "Loading sessions…" : "Choose a session"}</option>
          {sessions.options.map((row) => (
            <option key={row.id} value={row.id}>
              {sessionLabel(row)}
            </option>
          ))}
        </select>
        <input type="date" aria-label="Date" value={date} max={todayIso()} onChange={(event) => setDate(event.target.value || todayIso())} />
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="teach-stats">
        <Stat label="Students" value={state.loading ? "…" : totals.students} />
        <Stat label="Present" value={totals.present} tone="green" />
        <Stat label="Absent" value={totals.absent} tone="red" />
        <Stat label="Late" value={totals.late} tone="amber" />
        {support.leave ? <Stat label="Leave" value={totals.leave} tone="blue" /> : null}
        <Stat label="Attendance" value={percentText(totals.percent, totals.marked)} />
      </div>
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={state.options}
          loading={state.loading}
          emptyText={state.error ? "Attendance couldn't be loaded." : !sessionId ? "Choose a session." : "No active students in this session yet."}
          actions={(row) => (
            <Link className="link-btn" href={`/school/attendance/mark?section=${row.id}&date=${date}`}>
              {row.marked ? "Open" : "Mark"}
            </Link>
          )}
        />
      </div>
    </>
  );
}
