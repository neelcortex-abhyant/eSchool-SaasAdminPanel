"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { Chip, formatDateTime, Stat, TeachingPage } from "@/components/teaching/Frame";
import { MarksEntry, OFFLINE_LIVE_NOTE, OfflineExamForm, PaperForm, PublishChip, dayLabel, paperTime } from "@/components/teaching/offline";
import { useTeachers } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { activeScale } from "@/lib/ops/grading";
import { gradeFor } from "@/lib/ops/grading-math";
import { offlineService, paperEditing } from "@/lib/teaching/offline";
import type { OfflineExamDetail, OfflineResult, OfflineSchedule } from "@/lib/teaching/offlineTypes";
import { IconExam } from "@/lib/icons";

export default function OfflineExamPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <TeachingPage
      module="offline"
      title="Manage offline exam"
      icon={<IconExam width={18} height={18} />}
      liveNote={OFFLINE_LIVE_NOTE}
      back={{ href: "/school/offline-exams", label: "All offline exams" }}
    >
      {Number.isInteger(id) && id > 0 ? (
        <Suspense fallback={<div className="skeleton" style={{ height: 180 }} />}>
          <ExamBody id={id} />
        </Suspense>
      ) : (
        <div className="alert alert-danger">This exam link isn't valid.</div>
      )}
    </TeachingPage>
  );
}

type Tab = "papers" | "marks" | "results";

function ExamBody({ id }: { id: number }) {
  const toast = useToast();
  const state = useOptions(useCallback(() => offlineService().get(id).then((row) => [row]), [id]));
  const exam = state.options[0] ?? null;
  const params = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (["papers", "marks", "results"].includes(params.get("tab") ?? "") ? (params.get("tab") as Tab) : "papers"));
  const [paperId, setPaperId] = useState<number | "">("");
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState<OfflineSchedule | "new" | null>(null);
  const [removing, setRemoving] = useState<OfflineSchedule | null>(null);
  const [confirm, setConfirm] = useState<"publish" | "unpublish" | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [resultsVersion, setResultsVersion] = useState(0);

  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!exam) return <div className="resource-card"><div className="skeleton" style={{ height: 180 }} /></div>;

  const paper = exam.schedules.find((item) => item.id === paperId) ?? exam.schedules[0] ?? null;

  async function setPublish(publish: boolean) {
    setBusy(true);
    setActionError("");
    try {
      await offlineService().setPublish(id, publish);
      toast("success", publish ? "Results published to students and parents." : "Results unpublished. Marks can be changed again.");
      void state.reload();
      setResultsVersion((value) => value + 1);
    } catch (caught) {
      setActionError(errorMessage(caught, "Unable to change publishing."));
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }

  return (
    <>
      <section className="resource-card teach-detail" aria-labelledby="ox-title">
        <div className="teach-detail-head">
          <div>
            <h2 id="ox-title">
              {exam.name} <PublishChip exam={exam} />
            </h2>
            <p className="muted">
              {exam.class_name} {exam.section_name}
              {exam.exam_type ? ` · ${exam.exam_type}` : ""}
              {exam.exam_date ? ` · starts ${dayLabel(exam.exam_date)}` : ""}
            </p>
          </div>
          <div className="teach-detail-actions">
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => setEditing(true)}>
              Edit details
            </button>
            {exam.publish ? (
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => setConfirm("unpublish")}>
                Unpublish results
              </button>
            ) : (
              <button className="btn-pill btn-pill-green" type="button" disabled={busy || !exam.results_processed_at} title={exam.results_processed_at ? undefined : "Process the results first"} onClick={() => setConfirm("publish")}>
                Publish results
              </button>
            )}
          </div>
        </div>
        {actionError ? <div className="alert alert-danger" role="alert">{actionError}</div> : null}
        {exam.description ? <p className="teach-response">{exam.description}</p> : null}
        {exam.results_processed_at ? <p className="muted">Results last processed {formatDateTime(exam.results_processed_at)}.</p> : null}
      </section>

      <nav className="acad-tabs" aria-label="Exam sections">
        {([
          ["papers", `Papers (${exam.schedules.length})`],
          ["marks", "Marks entry"],
          ["results", "Results"],
        ] as [Tab, string][]).map(([key, label]) => (
          <button key={key} type="button" className={`acad-tab${tab === key ? " is-active" : ""}`} aria-pressed={tab === key} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>

      {tab === "papers" ? (
        <PapersPanel
          exam={exam}
          onAdd={() => setAdding("new")}
          onEdit={(paper) => setAdding(paper)}
          onRemove={(paper) => setRemoving(paper)}
          onMarks={(paperIdValue) => {
            setPaperId(paperIdValue);
            setTab("marks");
          }}
        />
      ) : tab === "marks" ? (
        <section className="resource-card" aria-label="Marks entry">
          {exam.schedules.length === 0 ? (
            <div className="empty-state">Add a subject paper first, then enter its marks here.</div>
          ) : (
            <>
              <div className="school-filters">
                <select aria-label="Subject paper" value={paper?.id ?? ""} onChange={(event) => setPaperId(Number(event.target.value))}>
                  {exam.schedules.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.subject_name || `Subject #${item.subject_id}`} · {dayLabel(item.exam_date)}
                    </option>
                  ))}
                </select>
              </div>
              {paper ? <MarksEntry key={`${paper.id}-${exam.publish}-${exam.results_processed_at}`} exam={exam} paper={paper} onSaved={() => void state.reload()} /> : null}
            </>
          )}
        </section>
      ) : (
        <ResultsPanel key={resultsVersion} exam={exam} onProcessed={() => void state.reload()} />
      )}

      {editing ? (
        <OfflineExamForm
          exam={exam}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            toast("success", "Exam updated.");
            void state.reload();
          }}
        />
      ) : null}
      {adding ? (
        <PaperForm
          exam={exam}
          paper={adding === "new" ? null : adding}
          onClose={() => setAdding(null)}
          onSaved={(saved) => {
            const edited = adding !== "new";
            setAdding(null);
            toast("success", `${saved.subject_name ?? "Paper"} ${edited ? "updated" : "added to the exam timetable"}.`);
            void state.reload();
          }}
        />
      ) : null}
      {removing ? (
        <ConfirmDialog
          title="Remove this paper?"
          body={`${removing.subject_name ?? "This paper"} on ${dayLabel(removing.exam_date)} will be taken off the exam timetable. Papers with marks can't be removed.`}
          confirmLabel="Remove paper"
          tone="danger"
          pending={busy}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            setBusy(true);
            try {
              await offlineService().removeSchedule(removing.id);
              toast("success", "Paper removed.");
              void state.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to remove the paper."));
            } finally {
              setBusy(false);
              setRemoving(null);
            }
          }}
        />
      ) : null}
      {confirm ? (
        <ConfirmDialog
          title={confirm === "publish" ? "Publish results?" : "Unpublish results?"}
          body={
            confirm === "publish"
              ? "Students and parents will see these results. Marks can't be changed while results are published."
              : "Students and parents will no longer see these results, and marks can be changed again."
          }
          confirmLabel={confirm === "publish" ? "Publish results" : "Unpublish"}
          pending={busy}
          onCancel={() => setConfirm(null)}
          onConfirm={() => void setPublish(confirm === "publish")}
        />
      ) : null}
    </>
  );
}

function PapersPanel({
  exam,
  onAdd,
  onEdit,
  onRemove,
  onMarks,
}: {
  exam: OfflineExamDetail;
  onAdd: () => void;
  onEdit: (paper: OfflineSchedule) => void;
  onRemove: (paper: OfflineSchedule) => void;
  onMarks: (paperId: number) => void;
}) {
  const editable = paperEditing();
  const teachers = useTeachers();
  const names = useMemo(() => new Map(teachers.options.map((row) => [row.id, row.name])), [teachers.options]);
  const columns: Column<OfflineSchedule>[] = [
    { key: "subject", label: "Subject", render: (row) => <strong>{row.subject_name || `Subject #${row.subject_id}`}</strong> },
    { key: "date", label: "Date", render: (row) => dayLabel(row.exam_date) },
    { key: "time", label: "Time", render: (row) => paperTime(row) },
    { key: "marks", label: "Marks", render: (row) => `${row.max_marks} (pass ${row.passing_marks})` },
    { key: "teacher", label: "Teacher", render: (row) => (row.teacher_user_id ? names.get(row.teacher_user_id) ?? `#${row.teacher_user_id}` : "—") },
  ];
  return (
    <section className="resource-card" aria-label="Subject papers">
      <div className="teach-toolbar">
        <button className="btn-pill btn-pill-green" type="button" onClick={onAdd}>
          Add subject paper
        </button>
        {!editable ? <span className="muted">The server can't edit or remove a paper yet.</span> : null}
      </div>
      <DataTable
        columns={columns}
        rows={exam.schedules}
        loading={false}
        emptyText="No subject papers yet. Add one for each subject in this exam."
        actions={(row) => (
          <>
            <button className="link-btn" type="button" onClick={() => onMarks(row.id)}>
              Enter marks
            </button>
            {editable ? (
              <>
                <button className="link-btn" type="button" disabled={exam.publish} onClick={() => onEdit(row)}>
                  Edit
                </button>
                <button className="link-btn danger" type="button" disabled={exam.publish} onClick={() => onRemove(row)}>
                  Remove
                </button>
              </>
            ) : null}
          </>
        )}
      />
    </section>
  );
}

function csvCell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function ResultsPanel({ exam, onProcessed }: { exam: OfflineExamDetail; onProcessed: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loader = useCallback(async () => {
    const [summary, results, scale] = await Promise.all([offlineService().summary(exam.id), offlineService().results(exam.id), activeScale()]);
    return [{ summary, results, scale }];
  }, [exam.id]);
  const state = useOptions(loader);
  const data = state.options[0] ?? null;

  async function process() {
    setBusy(true);
    setError("");
    try {
      const outcome = await offlineService().processResults(exam.id);
      toast(
        outcome.pending_students ? "error" : "success",
        `Results worked out for ${outcome.processed_students} of ${outcome.enrolled_students} students.${outcome.pending_students ? ` ${outcome.pending_students} still have papers without marks.` : ""}`,
      );
      onProcessed();
      void state.reload();
    } catch (caught) {
      setError(errorMessage(caught, "Unable to process results."));
    } finally {
      setBusy(false);
    }
  }

  function exportCsv() {
    if (!data) return;
    const subjects = exam.schedules.map((paper) => paper.subject_name || `Subject ${paper.subject_id}`);
    const header = ["Student", "Admission no.", ...subjects, "Total", "Out of", "Percentage", "Grade", "Result"];
    const lines = data.results.map((row) =>
      [
        row.student_name,
        row.admission_no ?? "",
        ...exam.schedules.map((paper) => {
          const subject = row.subjects.find((item) => item.schedule_id === paper.id);
          return subject ? (subject.status === "present" ? subject.marks_obtained ?? "" : subject.status) : "";
        }),
        row.total_obtained,
        row.total_max_marks,
        row.percentage,
        gradeFor(row.percentage, data.scale)?.grade ?? "",
        row.passed ? "Pass" : "Fail",
      ]
        .map(csvCell)
        .join(","),
    );
    const blob = new Blob([[header.map(csvCell).join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exam.name.replace(/[^\w-]+/g, "-")}-results.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const columns: Column<OfflineResult>[] = [
    { key: "student", label: "Student", render: (row) => <strong>{row.student_name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no ?? "—" },
    {
      key: "subjects",
      label: "Subjects",
      render: (row) =>
        row.subjects.length ? (
          <span className="muted">
            {row.subjects
              .map((subject) => `${subject.subject_name ?? "Subject"} ${subject.status === "present" ? `${subject.marks_obtained}/${subject.max_marks}` : subject.status}`)
              .join(" · ")}
          </span>
        ) : (
          "—"
        ),
    },
    { key: "total", label: "Total", render: (row) => `${row.total_obtained} / ${row.total_max_marks}` },
    { key: "percent", label: "%", render: (row) => `${row.percentage}%` },
    { key: "grade", label: "Grade", render: (row) => gradeFor(row.percentage, data?.scale)?.grade ?? "—" },
    { key: "result", label: "Result", render: (row) => <Chip tone={row.passed ? "green" : "red"}>{row.passed ? "Pass" : "Fail"}</Chip> },
  ];

  return (
    <section className="resource-card" aria-label="Results">
      <div className="teach-toolbar">
        <button className="btn-pill btn-pill-green" type="button" disabled={busy || exam.publish || exam.schedules.length === 0} onClick={() => void process()}>
          {busy ? "Processing…" : exam.results_processed_at ? "Process results again" : "Process results"}
        </button>
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={!data?.results.length} onClick={exportCsv}>
          Export CSV
        </button>
      </div>
      {exam.publish ? <p className="muted">Results are published. Unpublish them to correct marks or process again.</p> : null}
      {data ? (
        <p className="muted">
          {data.scale ? `Grades use “${data.scale.name}”` : "No grading scale is set up, so grades aren't shown"}
          {" · "}
          <Link className="link-btn" href="/school/grading">
            Grading scales
          </Link>
          {" · "}
          <Link className="link-btn" href="/school/report-cards">
            Student report cards
          </Link>
        </p>
      ) : null}
      {error ? <div className="alert alert-danger" role="alert">{error}</div> : null}
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      {data ? (
        <div className="teach-stats">
          <Stat label="Students" value={data.summary.enrolled_students} />
          <Stat label="Processed" value={data.summary.processed_students} tone="blue" />
          <Stat label="Missing marks" value={data.summary.pending_students} tone={data.summary.pending_students ? "amber" : "grey"} />
          <Stat label="Passed" value={data.summary.passed_count} tone="green" />
          <Stat label="Failed" value={data.summary.failed_count} tone="red" />
        </div>
      ) : null}
      <DataTable
        columns={columns}
        rows={data?.results ?? []}
        loading={state.loading}
        emptyText={state.error ? "Results couldn't be loaded." : "No results yet. Enter marks for every paper, then use Process results."}
      />
    </section>
  );
}
