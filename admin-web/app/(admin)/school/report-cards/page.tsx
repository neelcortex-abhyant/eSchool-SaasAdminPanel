"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, useOptions, usePagedList } from "@/components/academics/hooks";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { peopleService, type StudentRow } from "@/lib/people";
import { allOfflineExams } from "@/lib/teaching/offline";
import { IconExam } from "@/lib/icons";

const PAGE_SIZE = 20;

export default function ReportCardsPage() {
  return (
    <TeachingPage
      module="grading"
      title="Report cards"
      description="Each student's results for the session across all offline exams, graded with the school's scale."
      icon={<IconExam width={18} height={18} />}
      liveNote={OPS_LIVE_NOTE.grading}
      tabs={[
        { href: "/school/grading", label: "Grading scales" },
        { href: "/school/report-cards", label: "Report cards" },
      ]}
    >
      <ReportCardsBody />
    </TeachingPage>
  );
}

function ReportCardsBody() {
  const [filter, setFilter] = usePlacementFilter();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [page, setPage] = useState(1);
  const ready = Boolean(filter.sessionId && filter.sectionId);

  const loader = useCallback(
    () => peopleService("students").listStudents({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, status: "1", sort: "name" }),
    [page, search, filter.sessionId, filter.sectionId],
  );
  const none = useCallback(() => Promise.resolve({ items: [] as StudentRow[], total: 0, page: 1, page_size: PAGE_SIZE }), []);
  const list = usePagedList(ready ? loader : none);
  const exams = useOptions(
    useCallback(() => allOfflineExams({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId }), [filter.sessionId, filter.sectionId]),
  );
  const processed = exams.options.filter((exam) => exam.results_processed_at).length;
  const published = exams.options.filter((exam) => exam.publish).length;

  const columns: Column<StudentRow>[] = [
    { key: "roll", label: "Roll", render: (row) => row.roll_number ?? "—" },
    { key: "name", label: "Student", render: (row) => <strong>{row.name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}` },
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPage(1); }} />
        <input type="search" aria-label="Search students" placeholder="Search by name or admission no." value={searchInput} disabled={!ready} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
      </div>
      {ready ? (
        <div className="teach-summary">
          <Chip tone="blue">{exams.loading ? "…" : exams.options.length} exams this session</Chip>
          <Chip tone={processed === exams.options.length && processed > 0 ? "green" : "amber"}>{processed} with results</Chip>
          <Chip tone={published ? "green" : "grey"}>{published} published</Chip>
        </div>
      ) : null}
      <ErrorAlert error={list.error ?? exams.error} onRetry={() => void list.reload()} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">Choose a session, class and section to list its students.</div>
        </div>
      ) : (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={list.data?.items ?? []}
            loading={list.loading}
            emptyText={list.error ? "Students couldn't be loaded." : "No active students in this section."}
            actions={(row) => (
              <Link className="link-btn" href={`/school/report-cards/${row.id}?session=${filter.sessionId}`}>
                View report card
              </Link>
            )}
          />
          <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
        </div>
      )}
    </>
  );
}
