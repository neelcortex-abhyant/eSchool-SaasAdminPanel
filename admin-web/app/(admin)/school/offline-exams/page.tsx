"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { useSessions } from "@/components/people/academicOptions";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { OFFLINE_LIVE_NOTE, OFFLINE_TABS, OfflineExamForm, PublishChip, dayLabel } from "@/components/teaching/offline";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { allOfflineExams, offlineService } from "@/lib/teaching/offline";
import type { OfflineExam } from "@/lib/teaching/offlineTypes";
import { IconExam } from "@/lib/icons";

const PAGE_SIZE = 10;

export default function OfflineExamsPage() {
  const [editing, setEditing] = useState<OfflineExam | "new" | null>(null);
  return (
    <TeachingPage
      module="offline"
      title="Offline exams"
      description="Written exams: set the subject papers, enter marks, process results and publish them."
      icon={<IconExam width={18} height={18} />}
      tabs={OFFLINE_TABS}
      liveNote={OFFLINE_LIVE_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Create exam
        </button>
      }
    >
      <ExamsBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

type ExamRow = OfflineExam & { subjects: string[]; session_name: string };
type SortKey = "date-desc" | "date-asc" | "name" | "class";
type StatusFilter = "" | "draft" | "ready" | "published";

function statusOf(row: OfflineExam): StatusFilter {
  return row.publish ? "published" : row.results_processed_at ? "ready" : "draft";
}

function ExamsBody({ editing, setEditing }: { editing: OfflineExam | "new" | null; setEditing: (value: OfflineExam | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [filter, setFilter] = usePlacementFilter();
  const [status, setStatus] = useState<StatusFilter>("");
  const [sort, setSort] = useState<SortKey>("date-desc");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<OfflineExam | null>(null);
  const [pending, setPending] = useState(false);
  const sessions = useSessions();

  // Every matching exam is loaded so sorting and the status filter cover all of them, not one page.
  const loader = useCallback(async () => {
    const [exams, papers] = await Promise.all([
      allOfflineExams({ q: search, sessionYearId: filter.sessionId, classSectionId: filter.sectionId }),
      offlineService().schedules({ sessionYearId: filter.sessionId, classSectionId: filter.sectionId }),
    ]);
    const subjects = new Map<number, string[]>();
    for (const paper of papers) subjects.set(paper.exam_id, [...(subjects.get(paper.exam_id) ?? []), paper.subject_name || `Subject #${paper.subject_id}`]);
    return exams.map((exam) => ({ ...exam, subjects: subjects.get(exam.id) ?? [], session_name: "" }));
  }, [search, filter.sessionId, filter.sectionId]);
  const state = useOptions(loader);
  const sessionNames = useMemo(() => new Map(sessions.options.map((row) => [row.id, row.name])), [sessions.options]);
  const sorted = useMemo(() => {
    const rows = state.options
      .filter((row) => !filter.classId || filter.sectionId || row.class_id === filter.classId || row.class_id === 0)
      .filter((row) => !status || statusOf(row) === status)
      .map((row) => ({ ...row, session_name: sessionNames.get(row.session_year_id) ?? "" }));
    const compare: Record<SortKey, (a: ExamRow, b: ExamRow) => number> = {
      "date-desc": (a, b) => (b.exam_date ?? "").localeCompare(a.exam_date ?? ""),
      "date-asc": (a, b) => (a.exam_date ?? "9999").localeCompare(b.exam_date ?? "9999"),
      name: (a, b) => a.name.localeCompare(b.name),
      class: (a, b) => `${a.class_name} ${a.section_name}`.localeCompare(`${b.class_name} ${b.section_name}`, undefined, { numeric: true }),
    };
    return rows.sort((a, b) => compare[sort](a, b) || b.id - a.id);
  }, [state.options, filter.classId, filter.sectionId, status, sort, sessionNames]);
  const rows = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const list = { error: state.error, loading: state.loading, reload: state.reload };

  const columns: Column<ExamRow>[] = [
    { key: "name", label: "Exam", render: (row) => <Link className="teach-strong-link" href={`/school/offline-exams/${row.id}`}>{row.name}</Link> },
    { key: "session", label: "Session", render: (row) => row.session_name || "—" },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "subjects", label: "Subjects", render: (row) => (row.subjects.length ? <span className="muted">{row.subjects.join(", ")}</span> : <span className="muted">No papers yet</span>) },
    { key: "date", label: "Starts", render: (row) => dayLabel(row.exam_date) },
    { key: "status", label: "Status", render: (row) => <PublishChip exam={row} /> },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search exams" placeholder="Search by exam name" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPage(1); }} />
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as StatusFilter); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="ready">Results ready</option>
          <option value="published">Results published</option>
        </select>
        <select aria-label="Sort by" value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
          <option value="date-desc">Newest first</option>
          <option value="date-asc">Oldest first</option>
          <option value="name">Name A–Z</option>
          <option value="class">Class</option>
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={list.loading}
          emptyText={list.error ? "Exams couldn't be loaded." : search || filter.sectionId || status ? "No exams match these filters." : "No offline exams yet. Use Create exam to add one."}
          actions={(row) => (
            <>
              <Link className="link-btn" href={`/school/offline-exams/${row.id}`}>
                View
              </Link>
              <Link className="link-btn" href={`/school/offline-exams/${row.id}?tab=marks`}>
                Manage marks
              </Link>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              <button className="link-btn danger" type="button" onClick={() => setDeleting(row)}>
                Delete
              </button>
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={sorted.length} onPage={setPage} />
      </div>
      {editing ? (
        <OfflineExamForm
          exam={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            setEditing(null);
            toast("success", created ? `“${saved.name}” created. Open it to add the subject papers.` : "Exam updated.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this exam?"
          body={`“${deleting.name}” and its papers will be removed. Exams that already have marks or published results can't be deleted.`}
          confirmLabel="Delete exam"
          tone="danger"
          pending={pending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await offlineService().remove(deleting.id);
              toast("success", "Exam deleted.");
              if (rows.length === 1 && page > 1) setPage(page - 1);
              else void list.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the exam."));
            } finally {
              setPending(false);
              setDeleting(null);
            }
          }}
        />
      ) : null}
    </>
  );
}
