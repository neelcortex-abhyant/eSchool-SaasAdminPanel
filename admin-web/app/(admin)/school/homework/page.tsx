"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { formatDateTime, TeachingPage } from "@/components/teaching/Frame";
import { HOMEWORK_LIVE_NOTE, HomeworkForm } from "@/components/teaching/homework";
import { PlacementFilters, usePlacementFilter, useSubjects } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { homeworkService } from "@/lib/teaching/homework";
import type { Homework } from "@/lib/teaching/types";
import { IconBook } from "@/lib/icons";

const PAGE_SIZE = 10;

export default function HomeworkPage() {
  const [editing, setEditing] = useState<Homework | "new" | null>(null);
  return (
    <TeachingPage
      module="homework"
      title="Homework & assignments"
      description="Set homework for a section, then follow who handed it in and grade their work."
      icon={<IconBook width={18} height={18} />}
      liveNote={HOMEWORK_LIVE_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add homework
        </button>
      }
    >
      <HomeworkBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function HomeworkBody({ editing, setEditing }: { editing: Homework | "new" | null; setEditing: (value: Homework | "new" | null) => void }) {
  const toast = useToast();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [filter, setFilter] = usePlacementFilter();
  const [subjectId, setSubjectId] = useState<number | "">("");
  const subjects = useSubjects(filter.classId ? String(filter.classId) : "");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<Homework | null>(null);
  const [pending, setPending] = useState(false);

  const loader = useCallback(
    () =>
      homeworkService().list({
        page,
        pageSize: PAGE_SIZE,
        q: search,
        sessionYearId: filter.sessionId,
        classSectionId: filter.sectionId,
        subjectId,
      }),
    [page, search, filter.sessionId, filter.sectionId, subjectId],
  );
  const list = usePagedList(loader);
  // The server filters by section, not class; narrow a class-only filter on this page.
  const rows = (list.data?.items ?? []).filter((row) => !filter.classId || filter.sectionId || row.class_id === filter.classId || row.class_id === 0);

  const columns: Column<Homework>[] = [
    {
      key: "title",
      label: "Homework",
      render: (row) => (
        <Link href={`/school/homework/${row.id}`} className="teach-strong-link">
          {row.title}
        </Link>
      ),
    },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "subject", label: "Subject", render: (row) => row.subject_name || "—" },
    { key: "teacher", label: "Teacher", render: (row) => row.teacher_name || "—" },
    { key: "deadline", label: "Deadline", render: (row) => formatDateTime(row.deadline_at) },
    { key: "marks", label: "Max marks", render: (row) => (row.max_marks ?? "—") },
    { key: "files", label: "Files", render: (row) => row.attachments.length || "—" },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search homework" placeholder="Search by title" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters
          sessionId={filter.sessionId}
          classId={filter.classId}
          sectionId={filter.sectionId}
          onChange={(next) => {
            setFilter(next);
            setSubjectId("");
            setPage(1);
          }}
        />
        <select aria-label="Filter by subject" value={subjectId} onChange={(event) => { setSubjectId(event.target.value ? Number(event.target.value) : ""); setPage(1); }}>
          <option value="">{subjects.loading ? "Loading subjects…" : "All subjects"}</option>
          {subjects.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
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
          emptyText={list.error ? "Homework couldn't be loaded." : search || filter.sectionId || subjectId ? "No homework matches these filters." : "No homework yet. Use Add homework to set the first one."}
          actions={(row) => (
            <>
              <Link className="link-btn" href={`/school/homework/${row.id}`}>
                Submissions
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
        <HomeworkForm
          homework={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(_, created, failures) => {
            setEditing(null);
            if (failures.length) toast("error", `Homework saved, but some files didn't upload — ${failures.join("; ")}`);
            else toast("success", created ? "Homework added." : "Homework updated.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <ConfirmDialog
          title="Delete this homework?"
          body={`“${deleting.title}” and every submission for it will be removed. This can't be undone.`}
          confirmLabel="Delete homework"
          tone="danger"
          pending={pending}
          onCancel={() => setDeleting(null)}
          onConfirm={async () => {
            setPending(true);
            try {
              await homeworkService().remove(deleting.id);
              toast("success", "Homework deleted.");
              if (rows.length === 1 && page > 1) setPage(page - 1);
              else void list.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the homework."));
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
