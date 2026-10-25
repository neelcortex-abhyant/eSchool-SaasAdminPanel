"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { TeachingPage } from "@/components/teaching/Frame";
import { OFFLINE_LIVE_NOTE, OFFLINE_TABS, dayLabel, paperTime } from "@/components/teaching/offline";
import { PlacementFilters, usePlacementFilter, useTeachers } from "@/components/teaching/Pickers";
import { offlineService } from "@/lib/teaching/offline";
import { sectionMap } from "@/lib/teaching/lookups";
import type { OfflineSchedule } from "@/lib/teaching/offlineTypes";
import { IconCalendar } from "@/lib/icons";

export default function ExamTimetablePage() {
  return (
    <TeachingPage
      module="offline"
      title="Exam timetable"
      description="Every subject paper by date. Add papers from an exam's page."
      icon={<IconCalendar width={18} height={18} />}
      tabs={OFFLINE_TABS}
      liveNote={OFFLINE_LIVE_NOTE}
    >
      <TimetableBody />
    </TeachingPage>
  );
}

function TimetableBody() {
  const [filter, setFilter] = usePlacementFilter();
  const teachers = useTeachers();
  const teacherNames = useMemo(() => new Map(teachers.options.map((row) => [row.id, row.name])), [teachers.options]);
  const loader = useCallback(
    async () => {
      const [papers, sections] = await Promise.all([offlineService().schedules({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId }), sectionMap()]);
      return papers.map((paper) => ({ ...paper, place: sections.get(paper.class_section_id) }));
    },
    [filter.sessionId, filter.sectionId],
  );
  const state = useOptions(loader);
  const rows = state.options.filter((row) => !filter.classId || filter.sectionId || row.place?.class_id === filter.classId);
  const [view, setView] = useState<"list" | "calendar">("calendar");

  const columns: Column<OfflineSchedule & { place?: { class_name: string; section_name: string } }>[] = [
    { key: "date", label: "Date", render: (row) => <strong>{dayLabel(row.exam_date)}</strong> },
    { key: "time", label: "Time", render: (row) => paperTime(row) },
    { key: "class", label: "Class", render: (row) => (row.place ? `${row.place.class_name} ${row.place.section_name}` : `Section #${row.class_section_id}`) },
    { key: "subject", label: "Subject", render: (row) => row.subject_name || `Subject #${row.subject_id}` },
    { key: "marks", label: "Marks", render: (row) => `${row.max_marks} (pass ${row.passing_marks})` },
    { key: "teacher", label: "Teacher", render: (row) => (row.teacher_user_id ? teacherNames.get(row.teacher_user_id) ?? `#${row.teacher_user_id}` : "—") },
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
        <div className="teach-segmented" role="group" aria-label="View">
          <button type="button" className={view === "calendar" ? "is-active" : ""} aria-pressed={view === "calendar"} onClick={() => setView("calendar")}>
            Calendar
          </button>
          <button type="button" className={view === "list" ? "is-active" : ""} aria-pressed={view === "list"} onClick={() => setView("list")}>
            List
          </button>
        </div>
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      {view === "calendar" ? (
        <PaperCalendar papers={rows} loading={state.loading} teacherNames={teacherNames} />
      ) : (
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={state.loading}
          emptyText={state.error ? "The exam timetable couldn't be loaded." : "No papers scheduled for these filters."}
          actions={(row) => (
            <Link className="link-btn" href={`/school/offline-exams/${row.exam_id}`}>
              Open exam
            </Link>
          )}
        />
      </div>
      )}
    </>
  );
}

type CalendarPaper = OfflineSchedule & { place?: { class_name: string; section_name: string } };

function monthKey(date: string) {
  return date.slice(0, 7);
}

/** Papers on a month grid (a list of days on phones). Days with two papers for one class are flagged. */
function PaperCalendar({ papers, loading, teacherNames }: { papers: CalendarPaper[]; loading: boolean; teacherNames: Map<number, string> }) {
  const months = useMemo(() => [...new Set(papers.map((paper) => monthKey(paper.exam_date)))].sort(), [papers]);
  const thisMonth = new Date().toISOString().slice(0, 7);
  const [chosen, setChosen] = useState<string | null>(null);
  const month = chosen ?? (months.find((item) => item >= thisMonth) ?? months[months.length - 1] ?? thisMonth);
  const [year, mon] = month.split("-").map(Number);
  const first = new Date(year, mon - 1, 1);
  const days = new Date(year, mon, 0).getDate();
  const lead = (first.getDay() + 6) % 7; // weeks start on Monday
  const byDay = new Map<string, CalendarPaper[]>();
  for (const paper of papers) if (monthKey(paper.exam_date) === month) byDay.set(paper.exam_date, [...(byDay.get(paper.exam_date) ?? []), paper]);
  const shift = (step: number) => {
    const next = new Date(year, mon - 1 + step, 1);
    setChosen(`${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`);
  };
  if (loading && !papers.length) return <div className="resource-card"><div className="skeleton" style={{ height: 260 }} /></div>;
  return (
    <section className="resource-card" aria-label="Exam calendar">
      <div className="teach-cal-head">
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => shift(-1)} aria-label="Previous month">
          ‹
        </button>
        <h2>{first.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => shift(1)} aria-label="Next month">
          ›
        </button>
      </div>
      {byDay.size === 0 ? <div className="empty-state">No papers this month.{months.length ? " Use the arrows to see other months." : ""}</div> : null}
      <div className="teach-cal" role="grid">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((name) => (
          <div key={name} className="teach-cal-dow" role="columnheader">
            {name}
          </div>
        ))}
        {Array.from({ length: lead }, (_, index) => (
          <div key={`lead-${index}`} className="teach-cal-cell is-blank" aria-hidden />
        ))}
        {Array.from({ length: days }, (_, index) => {
          const date = `${month}-${String(index + 1).padStart(2, "0")}`;
          const list = (byDay.get(date) ?? []).sort((a, b) => (a.start_time ?? "").localeCompare(b.start_time ?? ""));
          const clash = new Set(list.map((paper) => paper.class_section_id)).size < list.length;
          return (
            <div key={date} className={`teach-cal-cell${list.length ? " has-papers" : ""}`} role="gridcell" aria-label={dayLabel(date)}>
              <span className="teach-cal-day">{index + 1}</span>
              <span className="teach-cal-date">{dayLabel(date)}</span>
              {clash ? <span className="teach-conflict-text">Two papers for one class</span> : null}
              {list.map((paper) => (
                <Link key={paper.id} className="teach-cal-paper" href={`/school/offline-exams/${paper.exam_id}`}>
                  <strong>{paper.subject_name || `Subject #${paper.subject_id}`}</strong>
                  <span>{paper.place ? `${paper.place.class_name} ${paper.place.section_name}` : ""}</span>
                  <span className="muted">
                    {paperTime(paper)}
                    {paper.teacher_user_id ? ` · ${teacherNames.get(paper.teacher_user_id) ?? ""}` : ""}
                  </span>
                </Link>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}
