"use client";

import { useParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { FileButton, formatDateTime, Stat, TeachingPage } from "@/components/teaching/Frame";
import { EvaluationForm, HOMEWORK_LIVE_NOTE, HomeworkForm, SUBMISSION_STATUS, SubmissionChip } from "@/components/teaching/homework";
import { homeworkService } from "@/lib/teaching/homework";
import type { AssignmentStatus, Homework, Submission } from "@/lib/teaching/types";
import { IconBook } from "@/lib/icons";

const FILTERS: ("" | AssignmentStatus)[] = ["", "pending", "submitted", "late", "graded"];

export default function HomeworkDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <TeachingPage
      module="homework"
      title="Homework submissions"
      icon={<IconBook width={18} height={18} />}
      liveNote={HOMEWORK_LIVE_NOTE}
      back={{ href: "/school/homework", label: "All homework" }}
    >
      {Number.isInteger(id) && id > 0 ? <DetailBody id={id} /> : <div className="alert alert-danger">This homework link isn't valid.</div>}
    </TeachingPage>
  );
}

function DetailBody({ id }: { id: number }) {
  const toast = useToast();
  const homeworkLoader = useCallback(() => homeworkService().get(id).then((row) => [row]), [id]);
  const homeworkState = useOptions(homeworkLoader);
  const homework = homeworkState.options[0] ?? null;

  const submissionLoader = useCallback(() => (homework ? homeworkService().submissions(homework) : Promise.resolve([])), [homework]);
  const submissions = useOptions(homework ? submissionLoader : null);

  const [status, setStatus] = useState<"" | AssignmentStatus>("");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim().toLowerCase());
  const [grading, setGrading] = useState<Submission | null>(null);
  const [editing, setEditing] = useState(false);

  const counts = useMemo(() => {
    const all = submissions.options;
    return {
      total: all.length,
      pending: all.filter((row) => row.status === "pending").length,
      submitted: all.filter((row) => row.status === "submitted").length,
      late: all.filter((row) => row.status === "late").length,
      graded: all.filter((row) => row.status === "graded").length,
    };
  }, [submissions.options]);

  const rows = submissions.options
    .filter((row) => !status || row.status === status)
    .filter((row) => !search || row.student_name.toLowerCase().includes(search) || row.admission_no.toLowerCase().includes(search))
    .sort((a, b) => a.student_name.localeCompare(b.student_name));

  if (homeworkState.error) return <ErrorAlert error={homeworkState.error} onRetry={() => void homeworkState.reload()} />;
  if (!homework) return <div className="resource-card"><div className="skeleton" style={{ height: 160 }} /></div>;

  const columns: Column<Submission>[] = [
    { key: "student", label: "Student", render: (row) => <strong>{row.student_name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no || "—" },
    { key: "status", label: "Status", render: (row) => <SubmissionChip status={row.status} /> },
    { key: "submitted", label: "Handed in", render: (row) => formatDateTime(row.submitted_at) },
    { key: "marks", label: "Marks", render: (row) => (row.marks !== null ? `${row.marks}${homework.max_marks !== null ? ` / ${homework.max_marks}` : ""}` : "—") },
    { key: "grade", label: "Grade", render: (row) => row.grade ?? "—" },
  ];

  return (
    <>
      <HomeworkSummaryCard homework={homework} onEdit={() => setEditing(true)} />
      <div className="teach-stats">
        <Stat label="Students" value={submissions.loading && !counts.total ? "…" : counts.total} />
        <Stat label="Pending" value={counts.pending} tone="grey" />
        <Stat label="Submitted" value={counts.submitted} tone="blue" />
        <Stat label="Late" value={counts.late} tone="amber" />
        <Stat label="Graded" value={counts.graded} tone="green" />
      </div>
      <div className="school-filters">
        <input type="search" aria-label="Search students" placeholder="Search by student or admission no." value={searchInput} onChange={(event) => setSearchInput(event.target.value)} />
        <div className="teach-segmented" role="group" aria-label="Filter by status">
          {FILTERS.map((item) => (
            <button key={item || "all"} type="button" className={status === item ? "is-active" : ""} aria-pressed={status === item} onClick={() => setStatus(item)}>
              {item ? SUBMISSION_STATUS[item].label : "All"}
            </button>
          ))}
        </div>
      </div>
      <ErrorAlert error={submissions.error} onRetry={() => void submissions.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={submissions.loading}
          emptyText={submissions.error ? "Submissions couldn't be loaded." : status || search ? "No students match these filters." : "No students are enrolled in this section yet."}
          actions={(row) =>
            row.status === "pending" ? (
              <span className="muted">Not handed in</span>
            ) : (
              <button className="link-btn" type="button" onClick={() => setGrading(row)}>
                {row.status === "graded" ? "Edit grade" : "Evaluate"}
              </button>
            )
          }
        />
      </div>
      {grading ? (
        <EvaluationForm
          homework={homework}
          submission={grading}
          onClose={() => setGrading(null)}
          onSaved={() => {
            setGrading(null);
            toast("success", "Evaluation saved.");
            void submissions.reload();
          }}
        />
      ) : null}
      {editing ? (
        <HomeworkForm
          homework={homework}
          onClose={() => setEditing(false)}
          onSaved={(_, __, failures) => {
            setEditing(false);
            if (failures.length) toast("error", `Homework saved, but some files didn't upload — ${failures.join("; ")}`);
            else toast("success", "Homework updated.");
            void homeworkState.reload();
          }}
        />
      ) : null}
    </>
  );
}

function HomeworkSummaryCard({ homework, onEdit }: { homework: Homework; onEdit: () => void }) {
  return (
    <section className="resource-card teach-detail" aria-labelledby="hw-title">
      <div className="teach-detail-head">
        <div>
          <h2 id="hw-title">{homework.title}</h2>
          <p className="muted">
            {homework.class_name} {homework.section_name} · {homework.subject_name} · {homework.teacher_name}
          </p>
        </div>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={onEdit}>
          Edit homework
        </button>
      </div>
      <dl className="teach-facts">
        <div><dt>Assigned</dt><dd>{homework.assigned_date}</dd></div>
        <div><dt>Deadline</dt><dd>{formatDateTime(homework.deadline_at)}</dd></div>
        <div><dt>Max marks</dt><dd>{homework.max_marks ?? "Ungraded"}</dd></div>
        <div><dt>Late work</dt><dd>{homework.allow_late ? "Accepted" : "Not accepted"}</dd></div>
      </dl>
      {homework.instructions ? <p className="teach-response">{homework.instructions}</p> : null}
      {homework.attachments.length ? (
        <ul className="teach-list">
          {homework.attachments.map((file, index) => (
            <li key={`${file.original_filename}-${index}`}>
              <FileButton file={file} />
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
