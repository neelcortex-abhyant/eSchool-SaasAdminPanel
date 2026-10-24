"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { OFFLINE_LIVE_NOTE, OFFLINE_TABS, OfflineExamForm, PublishChip, dayLabel } from "@/components/teaching/offline";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { offlineService } from "@/lib/teaching/offline";
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

function ExamsBody({ editing, setEditing }: { editing: OfflineExam | "new" | null; setEditing: (value: OfflineExam | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [filter, setFilter] = usePlacementFilter();
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<OfflineExam | null>(null);
  const [pending, setPending] = useState(false);

  const loader = useCallback(
    () => offlineService().list({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: filter.sessionId, classSectionId: filter.sectionId }),
    [page, search, filter.sessionId, filter.sectionId],
  );
  const list = usePagedList(loader);
  const rows = (list.data?.items ?? []).filter((row) => !filter.classId || filter.sectionId || row.class_id === filter.classId || row.class_id === 0);

  const columns: Column<OfflineExam>[] = [
    { key: "name", label: "Exam", render: (row) => <Link className="teach-strong-link" href={`/school/offline-exams/${row.id}`}>{row.name}</Link> },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "type", label: "Type", render: (row) => row.exam_type || "—" },
    { key: "date", label: "Starts", render: (row) => dayLabel(row.exam_date) },
    { key: "status", label: "Status", render: (row) => <PublishChip exam={row} /> },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search exams" placeholder="Search by exam name" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPage(1); }} />
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={list.loading}
          emptyText={list.error ? "Exams couldn't be loaded." : search || filter.sectionId ? "No exams match these filters." : "No offline exams yet. Use Create exam to add one."}
          actions={(row) => (
            <>
              <Link className="link-btn" href={`/school/offline-exams/${row.id}`}>
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
