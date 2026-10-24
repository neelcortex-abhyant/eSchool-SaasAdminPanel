"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { EXAM_STATUS, EXAM_TABS, EXAMS_LIVE_NOTE, ExamForm, ExamStatusChip, examWindow } from "@/components/teaching/exams";
import { PlacementFilters, usePlacementFilter, useSubjects } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { examService } from "@/lib/teaching/exams";
import type { ExamStatus, OnlineExam } from "@/lib/teaching/types";
import { IconExam } from "@/lib/icons";

const PAGE_SIZE = 10;

export default function OnlineExamsPage() {
  const [editing, setEditing] = useState<OnlineExam | "new" | null>(null);
  return (
    <TeachingPage
      module="exams"
      title="Online exams"
      description="Create multiple-choice exams, add questions, publish them to a section and review students' attempts."
      icon={<IconExam width={18} height={18} />}
      tabs={EXAM_TABS}
      liveNote={EXAMS_LIVE_NOTE}
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

function ExamsBody({ editing, setEditing }: { editing: OnlineExam | "new" | null; setEditing: (value: OnlineExam | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [filter, setFilter] = usePlacementFilter();
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [status, setStatus] = useState<ExamStatus | "">("");
  const subjects = useSubjects(filter.classId ? String(filter.classId) : "");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<OnlineExam | null>(null);
  const [pending, setPending] = useState(false);

  const loader = useCallback(
    () => examService().list({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, subjectId, status }),
    [page, search, filter.sessionId, filter.sectionId, subjectId, status],
  );
  const list = usePagedList(loader);
  const rows = (list.data?.items ?? []).filter((row) => !filter.classId || filter.sectionId || row.class_id === filter.classId || row.class_id === 0);

  const columns: Column<OnlineExam>[] = [
    { key: "title", label: "Exam", render: (row) => <Link className="teach-strong-link" href={`/school/online-exams/${row.id}`}>{row.title}</Link> },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "subject", label: "Subject", render: (row) => row.subject_name || "—" },
    { key: "window", label: "Open", render: (row) => examWindow(row) },
    { key: "marks", label: "Marks", render: (row) => `${row.total_marks} (pass ${row.passing_marks})` },
    { key: "duration", label: "Duration", render: (row) => `${row.duration_minutes} min` },
    { key: "status", label: "Status", render: (row) => <ExamStatusChip status={row.status} /> },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search exams" placeholder="Search by exam name" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setSubjectId(""); setPage(1); }} />
        <select aria-label="Filter by subject" value={subjectId} onChange={(event) => { setSubjectId(event.target.value ? Number(event.target.value) : ""); setPage(1); }}>
          <option value="">{subjects.loading ? "Loading subjects…" : "All subjects"}</option>
          {subjects.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as ExamStatus | ""); setPage(1); }}>
          <option value="">All statuses</option>
          {(Object.keys(EXAM_STATUS) as ExamStatus[]).map((value) => (
            <option key={value} value={value}>
              {EXAM_STATUS[value].label}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={list.loading}
          emptyText={list.error ? "Exams couldn't be loaded." : search || status || subjectId || filter.sectionId ? "No exams match these filters." : "No online exams yet. Use Create exam to set one up."}
          actions={(row) => (
            <>
              <Link className="link-btn" href={`/school/online-exams/${row.id}`}>
                Manage
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
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {editing ? (
        <ExamForm
          exam={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            setEditing(null);
            toast("success", created ? `“${saved.title}” created as a draft. Open it to add questions.` : "Exam updated.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this exam?"
          body={`“${deleting.title}”, its questions and any student attempts will be removed. This can't be undone.`}
          confirmLabel="Delete exam"
          tone="danger"
          pending={pending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await examService().remove(deleting.id);
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
