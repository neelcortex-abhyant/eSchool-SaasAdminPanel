"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
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
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
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
    </>
  );
}
