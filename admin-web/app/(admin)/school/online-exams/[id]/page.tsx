"use client";

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { Chip, formatDateTime, Stat, TeachingPage } from "@/components/teaching/Frame";
import {
  ATTEMPT_STATUS,
  BankPicker,
  EXAMS_LIVE_NOTE,
  ExamForm,
  ExamStatusChip,
  ImportQuestions,
  QuestionCard,
  QuestionForm,
  examWindow,
} from "@/components/teaching/exams";
import { AcademicApiError, errorMessage } from "@/lib/academics";
import { examService } from "@/lib/teaching/exams";
import type { Attempt, ExamDetail, ExamStatus, Question } from "@/lib/teaching/types";
import { IconExam } from "@/lib/icons";

export default function OnlineExamPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <TeachingPage
      module="exams"
      title="Manage online exam"
      icon={<IconExam width={18} height={18} />}
      liveNote={EXAMS_LIVE_NOTE}
      back={{ href: "/school/online-exams", label: "All online exams" }}
    >
      {Number.isInteger(id) && id > 0 ? <ExamBody id={id} /> : <div className="alert alert-danger">This exam link isn't valid.</div>}
    </TeachingPage>
  );
}

type Dialog =
  | { kind: "edit" }
  | { kind: "question"; question: Question | null }
  | { kind: "delete-question"; question: Question }
  | { kind: "import" }
  | { kind: "bank" }
  | { kind: "attempt"; attempt: Attempt }
  | null;

function ExamBody({ id }: { id: number }) {
  const toast = useToast();
  const examLoader = useCallback(() => examService().get(id).then((row) => [row]), [id]);
  const examState = useOptions(examLoader);
  const exam = examState.options[0] ?? null;
  const attemptsLoader = useCallback(() => examService().attempts(id), [id]);
  const attempts = useOptions(attemptsLoader);
  const [tab, setTab] = useState<"questions" | "attempts">("questions");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [busy, setBusy] = useState(false);
  const [statusError, setStatusError] = useState("");

  const reload = useCallback(() => {
    void examState.reload();
    void attempts.reload();
  }, [examState, attempts]);

  if (examState.error) return <ErrorAlert error={examState.error} onRetry={() => void examState.reload()} />;
  if (!exam) return <div className="resource-card"><div className="skeleton" style={{ height: 180 }} /></div>;

  const questionTotal = exam.questions.reduce((sum, question) => sum + question.marks, 0);
  const marksMatch = Math.abs(questionTotal - exam.total_marks) < 0.001;
  const nextOrder = exam.questions.reduce((max, question) => Math.max(max, question.sort_order), 0) + 1;
  const canEditQuestions = !exam.locked;

  async function run(label: string, action: () => Promise<unknown>) {
    setBusy(true);
    setStatusError("");
    try {
      await action();
      toast("success", label);
      reload();
    } catch (caught) {
      // A 422 list carries the reasons per field; show them rather than "Check the highlighted fields."
      const reasons = caught instanceof AcademicApiError ? Object.values(caught.fieldErrors) : [];
      setStatusError(reasons.length ? reasons.join(" ") : errorMessage(caught, "The exam couldn't be updated."));
    } finally {
      setBusy(false);
    }
  }

  const setStatus = (status: ExamStatus, label: string) => run(label, () => examService().setStatus(id, status));

  const attemptColumns: Column<Attempt>[] = [
    { key: "student", label: "Student", render: (row) => <strong>{row.student_name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no || "—" },
    { key: "status", label: "Status", render: (row) => <Chip tone={ATTEMPT_STATUS[row.status]?.tone ?? "grey"}>{ATTEMPT_STATUS[row.status]?.label ?? row.status}</Chip> },
    { key: "submitted", label: "Submitted", render: (row) => formatDateTime(row.submitted_at) },
    { key: "score", label: "Score", render: (row) => (row.score !== null ? `${row.score} / ${exam.total_marks}` : "—") },
    { key: "percent", label: "%", render: (row) => (row.percentage !== null ? `${Math.round(row.percentage * 10) / 10}%` : "—") },
    { key: "result", label: "Result", render: (row) => (row.passed === null ? "—" : row.passed ? <Chip tone="green">Pass</Chip> : <Chip tone="red">Fail</Chip>) },
  ];

  return (
    <>
      <section className="resource-card teach-detail" aria-labelledby="exam-title">
        <div className="teach-detail-head">
          <div>
            <h2 id="exam-title">
              {exam.title} <ExamStatusChip status={exam.status} />{" "}
              {exam.status !== "draft" ? <Chip tone={exam.results_published ? "green" : "grey"}>{exam.results_published ? "Results visible" : "Results hidden"}</Chip> : null}
            </h2>
            <p className="muted">
              {exam.class_name} {exam.section_name} · {exam.subject_name}
            </p>
          </div>
          <div className="teach-detail-actions">
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy || exam.locked} onClick={() => setDialog({ kind: "edit" })}>
              Edit details
            </button>
            {exam.status === "draft" ? (
              <button className="btn-pill btn-pill-green" type="button" disabled={busy} onClick={() => void setStatus("published", "Exam published. Students can take it during its open window.")}>
                Publish
              </button>
            ) : null}
            {exam.status === "published" && !exam.locked ? (
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => void setStatus("draft", "Exam moved back to draft.")}>
                Unpublish
              </button>
            ) : null}
            {exam.status === "published" ? (
              <button className="btn-pill btn-pill-danger" type="button" disabled={busy} onClick={() => void setStatus("closed", "Exam closed. No new attempts can start.")}>
                Close exam
              </button>
            ) : null}
            {exam.status === "closed" ? (
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={() => void setStatus("published", "Exam reopened.")}>
                Reopen
              </button>
            ) : null}
            {exam.status !== "draft" ? (
              <button
                className="btn-pill btn-pill-green-soft"
                type="button"
                disabled={busy}
                onClick={() => void run(exam.results_published ? "Results hidden from students." : "Results published to students.", () => examService().setResultsPublished(id, !exam.results_published))}
              >
                {exam.results_published ? "Hide results" : "Publish results"}
              </button>
            ) : null}
          </div>
        </div>
        {statusError ? (
          <div className="alert alert-danger" role="alert">
            {statusError}
          </div>
        ) : null}
        <dl className="teach-facts">
          <div><dt>Open</dt><dd>{examWindow(exam)}</dd></div>
          <div><dt>Duration</dt><dd>{exam.duration_minutes} minutes</dd></div>
          <div><dt>Total marks</dt><dd>{exam.total_marks}</dd></div>
          <div><dt>Passing marks</dt><dd>{exam.passing_marks}</dd></div>
        </dl>
        {exam.instructions ? <p className="teach-response">{exam.instructions}</p> : null}
        {exam.locked ? (
          <div className="alert alert-info">Students have already attempted this exam, so its details and questions are locked. You can still close it and publish results.</div>
        ) : null}
      </section>

      <div className="teach-stats">
        <Stat label="Questions" value={exam.questions.length} />
        <Stat label="Question marks" value={`${questionTotal} / ${exam.total_marks}`} tone={marksMatch ? "green" : "amber"} />
        <Stat label="Attempts" value={attempts.loading && !attempts.options.length ? "…" : attempts.options.length} tone="blue" />
        <Stat label="Passed" value={attempts.options.filter((row) => row.passed).length} tone="green" />
      </div>
      {!marksMatch && exam.status === "draft" ? (
        <p className="alert alert-warning">
          Question marks add up to {questionTotal}, but the exam is out of {exam.total_marks}. They must match before you can publish.
        </p>
      ) : null}

      <nav className="acad-tabs" aria-label="Exam sections">
        <button type="button" className={`acad-tab${tab === "questions" ? " is-active" : ""}`} aria-pressed={tab === "questions"} onClick={() => setTab("questions")}>
          Questions ({exam.questions.length})
        </button>
        <button type="button" className={`acad-tab${tab === "attempts" ? " is-active" : ""}`} aria-pressed={tab === "attempts"} onClick={() => setTab("attempts")}>
          Attempts ({attempts.options.length})
        </button>
      </nav>

      {tab === "questions" ? (
        <section className="resource-card" aria-label="Questions">
          <div className="teach-toolbar">
            <button className="btn-pill btn-pill-green" type="button" disabled={!canEditQuestions} onClick={() => setDialog({ kind: "question", question: null })}>
              Add question
            </button>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={!canEditQuestions} onClick={() => setDialog({ kind: "import" })}>
              Import CSV / JSON
            </button>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={!canEditQuestions} onClick={() => setDialog({ kind: "bank" })}>
              Add from question bank
            </button>
          </div>
          {exam.questions.length === 0 ? (
            <div className="empty-state">No questions yet. Add them one by one, import a file or pick from the question bank.</div>
          ) : (
            <ol className="teach-questions">
              {exam.questions.map((question, index) => (
                <QuestionCard
                  key={question.id}
                  index={index}
                  question={question}
                  actions={
                    canEditQuestions ? (
                      <>
                        <button className="link-btn" type="button" onClick={() => setDialog({ kind: "question", question })}>
                          Edit
                        </button>
                        <button className="link-btn danger" type="button" onClick={() => setDialog({ kind: "delete-question", question })}>
                          Delete
                        </button>
                      </>
                    ) : null
                  }
                />
              ))}
            </ol>
          )}
        </section>
      ) : (
        <>
          <ErrorAlert error={attempts.error} onRetry={() => void attempts.reload()} />
          <div className="resource-card">
            <DataTable
              columns={attemptColumns}
              rows={attempts.options}
              loading={attempts.loading}
              emptyText={attempts.error ? "Attempts couldn't be loaded." : exam.status === "draft" ? "Publish the exam so students can attempt it." : "No student has attempted this exam yet."}
              actions={(row) => (
                <button className="link-btn" type="button" onClick={() => setDialog({ kind: "attempt", attempt: row })}>
                  View answers
                </button>
              )}
            />
          </div>
        </>
      )}

      {dialog?.kind === "edit" ? (
        <ExamForm
          exam={exam}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            toast("success", "Exam updated.");
            reload();
          }}
        />
      ) : null}
      {dialog?.kind === "question" ? (
        <QuestionForm
          title={dialog.question ? "Edit question" : "Add question"}
          question={dialog.question}
          nextOrder={nextOrder}
          onClose={() => setDialog(null)}
          onSubmit={async (input) => {
            if (dialog.question) await examService().updateQuestion(id, dialog.question.id, input);
            else await examService().addQuestion(id, input);
            setDialog(null);
            toast("success", dialog.question ? "Question updated." : "Question added.");
            reload();
          }}
        />
      ) : null}
      {dialog?.kind === "delete-question" ? (
        <ConfirmDialog
          title="Delete this question?"
          body={dialog.question.question_text}
          confirmLabel="Delete question"
          tone="danger"
          pending={busy}
          onCancel={() => setDialog(null)}
          onConfirm={async () => {
            setBusy(true);
            try {
              await examService().removeQuestion(id, dialog.question.id);
              toast("success", "Question deleted.");
              reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to delete the question."));
            } finally {
              setBusy(false);
              setDialog(null);
            }
          }}
        />
      ) : null}
      {dialog?.kind === "import" ? (
        <ImportQuestions
          examId={id}
          nextOrder={nextOrder}
          onClose={() => setDialog(null)}
          onImported={(count) => {
            setDialog(null);
            toast("success", `${count} question${count === 1 ? "" : "s"} imported.`);
            reload();
          }}
        />
      ) : null}
      {dialog?.kind === "bank" ? (
        <BankPicker
          examId={id}
          nextOrder={nextOrder}
          onClose={() => setDialog(null)}
          onCopied={(count, failures) => {
            setDialog(null);
            if (failures.length) toast("error", `${count} added; ${failures.length} failed — ${failures.join("; ")}`);
            else toast("success", `${count} question${count === 1 ? "" : "s"} added from the bank.`);
            reload();
          }}
        />
      ) : null}
      {dialog?.kind === "attempt" ? <AttemptDialog exam={exam} attempt={dialog.attempt} onClose={() => setDialog(null)} /> : null}
    </>
  );
}

function AttemptDialog({ exam, attempt, onClose }: { exam: ExamDetail; attempt: Attempt; onClose: () => void }) {
  const loader = useCallback(() => examService().attempt(attempt.id).then((row) => [row]), [attempt.id]);
  const detail = useOptions(loader);
  const data = detail.options[0];
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card acad-modal is-wide" role="dialog" aria-modal="true" aria-labelledby="attempt-title">
        <h2 id="attempt-title">{attempt.student_name}</h2>
        <p className="muted">
          {exam.title} · {attempt.score !== null ? `${attempt.score} / ${exam.total_marks}` : "Not scored yet"}
          {attempt.passed !== null ? (attempt.passed ? " · Pass" : " · Fail") : ""}
        </p>
        {detail.error ? (
          <div className="alert alert-danger" role="alert">
            {errorMessage(detail.error)}
            {!exam.results_published ? " Publish the results to see each answer." : ""}
          </div>
        ) : !data ? (
          <div className="skeleton" style={{ height: 120 }} />
        ) : data.answers.length === 0 ? (
          <div className="empty-state">No answers were recorded for this attempt.</div>
        ) : (
          <ol className="teach-questions">
            {data.answers.map((answer, index) => {
              const right = answer.chosen !== null && answer.chosen === answer.correct;
              return (
                <li key={index} className="teach-question">
                  <div className="teach-question-head">
                    <strong>
                      Q{index + 1}. {answer.question_text}
                    </strong>
                    <span className="muted">
                      {answer.awarded ?? 0} / {answer.marks}
                    </span>
                  </div>
                  <p>
                    Answer: {answer.chosen ?? <em className="muted">Not answered</em>} {answer.chosen !== null ? <Chip tone={right ? "green" : "red"}>{right ? "Correct" : "Wrong"}</Chip> : null}
                  </p>
                  {!right && answer.correct ? <p className="muted">Correct answer: {answer.correct}</p> : null}
                </li>
              );
            })}
          </ol>
        )}
        <div className="page-actions">
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
