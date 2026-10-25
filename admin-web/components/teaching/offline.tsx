"use client";

import { useCallback, useMemo, useState } from "react";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { Chip, formatDateTime } from "@/components/teaching/Frame";
import { EMPTY_PLACEMENT, PlacementFields, useSubjects, useTeachers, type PlacementValue } from "@/components/teaching/Pickers";
import { MARK_STATUS_LABEL, examRoster, markProblem, offlineService, scheduleProblems } from "@/lib/teaching/offline";
import { MARKS_CSV_TEMPLATE_HEADER, parseMarksCsv } from "@/lib/teaching/marksCsv";
import type { MarkInput, MarkStatus, OfflineExam, OfflineExamDetail, OfflineExamInput, OfflineMark, OfflineSchedule } from "@/lib/teaching/offlineTypes";

export const OFFLINE_TABS = [
  { href: "/school/offline-exams", label: "Exams" },
  { href: "/school/offline-exams/timetable", label: "Exam timetable" },
];

export const OFFLINE_LIVE_NOTE =
  "Connected to the school's server. The server can't edit or remove a subject paper yet, and doesn't grade results; grades come from the school's grading scale (sample data until the server has one).";

export function PublishChip({ exam }: { exam: Pick<OfflineExam, "publish" | "results_processed_at"> }) {
  if (exam.publish) return <Chip tone="green">Results published</Chip>;
  if (exam.results_processed_at) return <Chip tone="blue">Results ready</Chip>;
  return <Chip tone="grey">Draft</Chip>;
}

export function paperTime(paper: Pick<OfflineSchedule, "start_time" | "end_time">): string {
  return paper.start_time && paper.end_time ? `${paper.start_time}–${paper.end_time}` : "Time not set";
}

export function dayLabel(date: string | null): string {
  if (!date) return "—";
  const value = new Date(`${date}T00:00:00`);
  return Number.isNaN(value.getTime()) ? date : value.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

/** Create or edit an exam's name, class and date. */
export function OfflineExamForm({ exam, onClose, onSaved }: { exam: OfflineExam | null; onClose: () => void; onSaved: (saved: OfflineExam, created: boolean) => void }) {
  const [placement, setPlacement] = useState<PlacementValue>(
    exam ? { session_year_id: String(exam.session_year_id), class_id: String(exam.class_id), class_section_id: String(exam.class_section_id) } : EMPTY_PLACEMENT,
  );
  const [name, setName] = useState(exam?.name ?? "");
  const [type, setType] = useState(exam?.exam_type ?? "");
  const [date, setDate] = useState(exam?.exam_date ?? "");
  const [description, setDescription] = useState(exam?.description ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const onPlacement = useCallback((value: PlacementValue) => setPlacement(value), []);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!name.trim()) invalid.name = "Enter the exam name.";
    if (!placement.session_year_id) invalid.session_year_id = "Choose an academic session.";
    if (!placement.class_id) invalid.class_id = "Choose a class.";
    if (!placement.class_section_id) invalid.class_section_id = "Choose a section.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const input: OfflineExamInput = {
      name: name.trim(),
      description: description.trim() || null,
      session_year_id: Number(placement.session_year_id),
      class_section_id: Number(placement.class_section_id),
      exam_type: type.trim() || null,
      exam_date: date || null,
    };
    try {
      onSaved(exam ? await offlineService().update(exam.id, input) : await offlineService().create(input), !exam);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the exam.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={exam ? "Edit offline exam" : "Create offline exam"}
      description={exam ? undefined : "After creating it, add a paper for each subject, enter marks and process the results."}
      error={errors.formError}
      saving={saving}
      submitLabel={exam ? "Save changes" : "Create exam"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <TextField id="ox-name" label="Exam name" required span maxLength={128} value={name} onChange={setName} error={errors.fieldErrors.name} placeholder="Term 1 examination" />
      <PlacementFields idPrefix="ox" value={placement} onChange={onPlacement} errors={errors.fieldErrors} />
      <TextField id="ox-type" label="Exam type" maxLength={64} value={type} onChange={setType} placeholder="Term, Unit test, Final" error={errors.fieldErrors.exam_type} />
      <TextField id="ox-date" label="Starts on" type="date" value={date} onChange={setDate} error={errors.fieldErrors.exam_date} />
      <TextAreaField id="ox-description" label="Description" span maxLength={1024} value={description} onChange={setDescription} error={errors.fieldErrors.description} />
    </FormModal>
  );
}

/** Add one subject paper (date, time, marks) to an exam. */
export function PaperForm({ exam, paper, onClose, onSaved }: { exam: OfflineExamDetail; paper?: OfflineSchedule | null; onClose: () => void; onSaved: (paper: OfflineSchedule) => void }) {
  const subjects = useSubjects(String(exam.class_id || ""));
  const teachers = useTeachers();
  const [subjectId, setSubjectId] = useState(paper ? String(paper.subject_id) : "");
  const [teacherId, setTeacherId] = useState(paper?.teacher_user_id ? String(paper.teacher_user_id) : "");
  const [date, setDate] = useState(paper?.exam_date ?? exam.exam_date ?? "");
  const [start, setStart] = useState(paper?.start_time ?? "");
  const [end, setEnd] = useState(paper?.end_time ?? "");
  const [max, setMax] = useState(paper ? String(paper.max_marks) : "100");
  const [passing, setPassing] = useState(paper ? String(paper.passing_marks) : "33");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const used = new Set(exam.schedules.filter((item) => item.id !== paper?.id).map((item) => item.subject_id));

  async function submit() {
    const input = {
      subject_id: Number(subjectId),
      teacher_user_id: teacherId ? Number(teacherId) : null,
      exam_date: date,
      start_time: start.trim() || null,
      end_time: end.trim() || null,
      max_marks: Number(max),
      passing_marks: Number(passing),
    };
    const invalid = scheduleProblems(input);
    if ((input.start_time && !/^\d{2}:\d{2}$/.test(input.start_time)) || (input.end_time && !/^\d{2}:\d{2}$/.test(input.end_time))) invalid.end_time = "Enter times as HH:MM, e.g. 09:30.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      onSaved(paper ? await offlineService().updateSchedule(paper.id, input) : await offlineService().addSchedule(exam.id, input));
    } catch (caught) {
      errors.fromError(caught, "Unable to add the paper.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={paper ? "Edit subject paper" : "Add subject paper"}
      description={`${exam.name} · ${exam.class_name} ${exam.section_name}. Papers for one class can't overlap.`}
      error={errors.formError}
      saving={saving}
      submitLabel={paper ? "Save paper" : "Add paper"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <SelectField
        id="op-subject"
        label="Subject"
        required
        placeholder="Choose a subject"
        loading={subjects.loading}
        value={subjectId}
        onChange={setSubjectId}
        options={subjects.options.map((row) => ({ value: String(row.id), label: `${row.name}${used.has(row.id) ? " (already has a paper)" : ""}`, disabled: used.has(row.id) }))}
        error={errors.fieldErrors.subject_id}
      />
      <SelectField
        id="op-teacher"
        label="Teacher entering marks"
        placeholder="Any school admin"
        loading={teachers.loading}
        value={teacherId}
        onChange={setTeacherId}
        options={teachers.options.map((row) => ({ value: String(row.id), label: row.name }))}
        error={errors.fieldErrors.teacher_user_id}
        hint="Optional. The teacher must teach this subject in this section."
      />
      <TextField id="op-date" label="Date" type="date" required value={date} onChange={setDate} error={errors.fieldErrors.exam_date} />
      <TextField id="op-start" label="Start time" placeholder="09:00" value={start} onChange={setStart} error={errors.fieldErrors.start_time} />
      <TextField id="op-end" label="End time" placeholder="12:00" value={end} onChange={setEnd} error={errors.fieldErrors.end_time} hint="Leave both times empty if not decided." />
      <TextField id="op-max" label="Maximum marks" type="number" min="1" required value={max} onChange={setMax} error={errors.fieldErrors.max_marks} />
      <TextField id="op-pass" label="Passing marks" type="number" min="0" required value={passing} onChange={setPassing} error={errors.fieldErrors.passing_marks} />
    </FormModal>
  );
}

type MarkRow = { student_id: number; name: string; admission_no: string; roll: number | null; status: MarkStatus; marks: string; reason: string; saved: OfflineMark | null };

/** Enter or correct one paper's marks for every student in the exam's section. */
export function MarksEntry({ exam, paper, onSaved }: { exam: OfflineExamDetail; paper: OfflineSchedule; onSaved: () => void }) {
  const toast = useToast();
  const loader = useCallback(async () => {
    const [roster, saved] = await Promise.all([examRoster(exam), offlineService().marks(paper.id)]);
    return [{ roster, saved }];
  }, [exam, paper.id]);
  const state = useOptions(loader);
  const data = state.options[0] ?? null;
  const [edits, setEdits] = useState<Record<number, Partial<MarkRow>>>({});
  const [failures, setFailures] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState<OfflineMark | null>(null);
  const [uploading, setUploading] = useState(false);

  const rows: MarkRow[] = useMemo(() => {
    if (!data) return [];
    const byStudent = new Map(data.saved.map((mark) => [mark.student_id, mark]));
    return [...data.roster]
      .sort((a, b) => (a.roll_number ?? 9999) - (b.roll_number ?? 9999) || a.name.localeCompare(b.name))
      .map((student) => {
        const saved = byStudent.get(student.id) ?? null;
        const base: MarkRow = {
          student_id: student.id,
          name: student.name,
          admission_no: student.admission_no,
          roll: student.roll_number,
          status: saved?.status ?? "present",
          marks: saved?.marks_obtained !== null && saved?.marks_obtained !== undefined ? String(saved.marks_obtained) : "",
          reason: "",
          saved,
        };
        return { ...base, ...edits[student.id] };
      });
  }, [data, edits]);

  const locked = exam.publish;
  const isChanged = (row: MarkRow) =>
    row.saved
      ? row.saved.status !== row.status || (row.status === "present" && String(row.saved.marks_obtained ?? "") !== row.marks.trim())
      : row.status !== "present" || row.marks.trim() !== "";
  const changed = rows.filter(isChanged);
  const needsReason = Boolean(exam.results_processed_at);
  const entered = rows.filter((row) => row.saved).length;

  function edit(studentId: number, patch: Partial<MarkRow>) {
    setEdits((current) => ({ ...current, [studentId]: { ...current[studentId], ...patch } }));
    setFailures((current) => {
      const next = { ...current };
      delete next[studentId];
      return next;
    });
  }

  async function save() {
    const problems: Record<number, string> = {};
    const items: MarkInput[] = changed.map((row) => {
      const item: MarkInput = { student_id: row.student_id, status: row.status, marks_obtained: row.status === "present" && row.marks.trim() !== "" ? Number(row.marks) : null, reason: row.reason };
      const problem = markProblem(item, paper.max_marks) || (needsReason && row.saved && !row.reason.trim() ? "Give a reason for this correction." : "");
      if (problem) problems[row.student_id] = problem;
      return item;
    });
    if (Object.keys(problems).length) {
      setFailures(problems);
      toast("error", "Fix the highlighted rows before saving.");
      return;
    }
    setSaving(true);
    try {
      const outcome = await offlineService().saveMarks(exam, paper.id, items, data?.saved ?? []);
      const next: Record<number, string> = {};
      outcome.failures.forEach((failure) => (next[failure.student_id] = failure.message));
      setFailures(next);
      setEdits((current) => Object.fromEntries(Object.entries(current).filter(([id]) => next[Number(id)])));
      if (outcome.failures.length) toast("error", `${outcome.saved} saved, ${outcome.failures.length} not saved. Check the highlighted rows.`);
      else toast("success", `Marks saved for ${outcome.saved} student${outcome.saved === 1 ? "" : "s"}.${needsReason ? " Process the results again to update them." : ""}`);
      await state.reload();
      onSaved();
    } catch (caught) {
      toast("error", caught instanceof Error ? caught.message : "Unable to save marks.");
    } finally {
      setSaving(false);
    }
  }

  if (state.error) return <div className="alert alert-danger">{state.error instanceof Error ? state.error.message : "Unable to load marks."}</div>;
  if (!data) return <div className="skeleton" style={{ height: 160 }} />;
  if (!rows.length) return <div className="empty-state">No active students in {exam.class_name} {exam.section_name} for this session.</div>;

  return (
    <>
      <div className="teach-summary">
        <Chip tone="blue">
          {paper.subject_name} · {dayLabel(paper.exam_date)} · out of {paper.max_marks} (pass {paper.passing_marks})
        </Chip>
        <Chip tone={entered === rows.length ? "green" : "amber"}>
          {entered} of {rows.length} entered
        </Chip>
      </div>
      <div className="teach-toolbar">
        <button className="btn-pill btn-pill-green-soft" type="button" disabled={locked} onClick={() => setUploading(true)}>
          Upload CSV
        </button>
      </div>
      {locked ? <div className="alert alert-info">Results are published, so marks are read-only. Unpublish the results to make changes.</div> : null}
      {!locked && needsReason ? <div className="alert alert-info">Results were already processed. Each correction needs a reason, which is kept in the mark's history.</div> : null}
      <ul className="teach-roster" aria-label="Marks">
        {rows.map((row) => (
          <li key={row.student_id} className={failures[row.student_id] ? "has-error" : undefined}>
            <div className="teach-roster-name">
              <strong>
                {row.roll !== null ? `${row.roll}. ` : ""}
                {row.name}
              </strong>
              <span className="muted">{row.admission_no}</span>
              {failures[row.student_id] ? <span className="field-error">{failures[row.student_id]}</span> : null}
              {row.saved ? (
                <button className="link-btn" type="button" onClick={() => setHistory(row.saved)}>
                  History
                </button>
              ) : null}
            </div>
            <div className="teach-mark-inputs">
              <select aria-label={`Status for ${row.name}`} value={row.status} disabled={locked} onChange={(event) => edit(row.student_id, { status: event.target.value as MarkStatus })}>
                {(Object.keys(MARK_STATUS_LABEL) as MarkStatus[]).map((status) => (
                  <option key={status} value={status}>
                    {MARK_STATUS_LABEL[status]}
                  </option>
                ))}
              </select>
              <input
                type="number"
                inputMode="decimal"
                min={0}
                max={paper.max_marks}
                step="0.5"
                aria-label={`Marks for ${row.name}`}
                placeholder={row.status === "present" ? `/ ${paper.max_marks}` : "—"}
                value={row.status === "present" ? row.marks : ""}
                disabled={locked || row.status !== "present"}
                onChange={(event) => edit(row.student_id, { marks: event.target.value })}
              />
            </div>
            {needsReason && row.saved && isChanged(row) ? (
              <input className="teach-remark" type="text" maxLength={512} aria-label={`Reason for correcting ${row.name}`} placeholder="Reason for the correction" value={row.reason} onChange={(event) => edit(row.student_id, { reason: event.target.value })} />
            ) : (
              <span />
            )}
          </li>
        ))}
      </ul>
      <div className="teach-savebar">
        <span className="muted">
          {changed.length} change{changed.length === 1 ? "" : "s"} to save
        </span>
        <button className="btn-pill btn-pill-green" type="button" disabled={saving || locked || !changed.length} onClick={() => void save()}>
          {saving ? "Saving…" : "Save marks"}
        </button>
      </div>
      {history ? <MarkHistory mark={history} onClose={() => setHistory(null)} /> : null}
      {uploading ? (
        <CsvMarksUpload
          exam={exam}
          paper={paper}
          saved={data.saved}
          roster={data.roster.map((student) => ({ id: student.id, name: student.name, admission_no: student.admission_no }))}
          onClose={() => setUploading(false)}
          onDone={() => {
            setEdits({});
            void state.reload();
            onSaved();
          }}
        />
      ) : null}
    </>
  );
}

function MarkHistory({ mark, onClose }: { mark: OfflineMark; onClose: () => void }) {
  const state = useOptions(useCallback(() => offlineService().audits(mark.id), [mark.id]));
  const describe = (marks: number | null, status: string | null) => (status && status !== "present" ? MARK_STATUS_LABEL[status as MarkStatus] ?? status : marks ?? "—");
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="mark-history-title">
        <h2 id="mark-history-title">Changes · {mark.student_name}</h2>
        {state.error ? (
          <div className="alert alert-danger">{state.error instanceof Error ? state.error.message : "Unable to load the history."}</div>
        ) : state.loading ? (
          <div className="skeleton" style={{ height: 80 }} />
        ) : state.options.length === 0 ? (
          <p className="muted">No corrections recorded. Changes made before results are processed aren't logged unless a reason is given.</p>
        ) : (
          <ul className="teach-list">
            {state.options.map((audit) => (
              <li key={audit.id}>
                {describe(audit.previous_marks, audit.previous_status)} → {describe(audit.new_marks, audit.new_status)} · {formatDateTime(audit.created_at)}
                {audit.reason ? ` · “${audit.reason}”` : ""}
              </li>
            ))}
          </ul>
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

/** Upload a CSV of one paper's marks: read → preview with per-row checks → confirm → summary. */
export function CsvMarksUpload({
  exam,
  paper,
  saved,
  roster,
  onClose,
  onDone,
}: {
  exam: OfflineExamDetail;
  paper: OfflineSchedule;
  saved: OfflineMark[];
  roster: { id: number; name: string; admission_no: string }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<{ saved: number; failures: { line: number; name: string; message: string }[] } | null>(null);
  const [error, setError] = useState("");
  const parsed = useMemo(() => (text.trim() ? parseMarksCsv(text, roster, paper.max_marks) : null), [text, roster, paper.max_marks]);
  const savedBy = useMemo(() => new Map(saved.map((mark) => [mark.student_id, mark])), [saved]);
  // After results are processed a changed mark needs a reason, which a CSV doesn't carry.
  const rows = (parsed?.rows ?? []).map((row) => {
    const current = row.student_id ? savedBy.get(row.student_id) : undefined;
    const changed = current && (current.status !== row.status || (row.status === "present" && current.marks_obtained !== row.marks_obtained));
    const unchanged = current && !changed;
    if (!row.error && exam.results_processed_at && changed) return { ...row, error: "Results are processed; correct this mark in the grid with a reason.", unchanged: false };
    return { ...row, unchanged: Boolean(unchanged) };
  });
  const ready = rows.filter((row) => !row.error && !row.unchanged);
  const problems = rows.filter((row) => row.error);

  async function confirm() {
    if (!ready.length) return;
    setBusy(true);
    setError("");
    try {
      const outcome = await offlineService().saveMarks(
        exam,
        paper.id,
        ready.map((row) => ({ student_id: row.student_id as number, status: row.status, marks_obtained: row.marks_obtained })),
        saved,
      );
      const byStudent = new Map(ready.map((row) => [row.student_id, row]));
      setSummary({
        saved: outcome.saved,
        failures: outcome.failures.map((failure) => ({ line: byStudent.get(failure.student_id)?.line ?? 0, name: byStudent.get(failure.student_id)?.student_name ?? `#${failure.student_id}`, message: failure.message })),
      });
      onDone();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save the marks.");
    } finally {
      setBusy(false);
    }
  }

  const template = `${MARKS_CSV_TEMPLATE_HEADER}\n${roster.map((student) => `${student.admission_no},,present`).join("\n")}\n`;

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal-card acad-modal is-wide" role="dialog" aria-modal="true" aria-labelledby="csv-title">
        <h2 id="csv-title">Upload marks · {paper.subject_name}</h2>
        <p className="muted">
          Columns: admission_no, marks, status (present, absent or withheld). Marks out of {paper.max_marks}.{" "}
          <a className="link-btn" href={`data:text/csv;charset=utf-8,${encodeURIComponent(template)}`} download={`marks-${(paper.subject_name ?? "paper").replace(/\W+/g, "-")}.csv`}>
            Download this class's sheet
          </a>
        </p>
        {summary ? (
          <div role="status">
            <div className="teach-stats">
              <div className="teach-stat is-green"><span className="teach-stat-value">{summary.saved}</span><span className="teach-stat-label">Saved</span></div>
              <div className={`teach-stat ${summary.failures.length ? "is-red" : "is-grey"}`}><span className="teach-stat-value">{summary.failures.length}</span><span className="teach-stat-label">Not saved</span></div>
              <div className="teach-stat is-amber"><span className="teach-stat-value">{problems.length}</span><span className="teach-stat-label">Skipped (errors)</span></div>
            </div>
            {summary.failures.length ? (
              <ul className="teach-list teach-problems">
                {summary.failures.map((failure) => (
                  <li key={`${failure.line}-${failure.name}`}>
                    Row {failure.line} ({failure.name}): {failure.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <>
            <div className="resource-fields">
              <div className="form-field field-span">
                <label htmlFor="csv-file">CSV file</label>
                <input
                  id="csv-file"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    if (file.size > 512 * 1024) {
                      setError("The file is larger than 512 KB.");
                      return;
                    }
                    setError("");
                    setText(await file.text());
                  }}
                />
              </div>
              <TextAreaField id="csv-text" label="Or paste the CSV" span rows={4} value={text} onChange={setText} />
            </div>
            {error || parsed?.problem ? <div className="alert alert-danger" role="alert">{error || parsed?.problem}</div> : null}
            {rows.length ? (
              <>
                <p role="status">
                  <Chip tone="green">{ready.length} to save</Chip> {problems.length ? <Chip tone="red">{problems.length} with errors</Chip> : null}{" "}
                  {rows.length - ready.length - problems.length ? <Chip tone="grey">{rows.length - ready.length - problems.length} unchanged</Chip> : null}
                </p>
                <div className="table-wrap teach-csv-preview">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Row</th>
                        <th scope="col">Student</th>
                        <th scope="col">Status</th>
                        <th scope="col">Marks</th>
                        <th scope="col">Check</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.line} className={row.error ? "has-error" : undefined}>
                          <td>{row.line}</td>
                          <td>
                            {row.student_name ?? row.admission_no} <span className="muted">{row.admission_no}</span>
                          </td>
                          <td>{MARK_STATUS_LABEL[row.status]}</td>
                          <td>{row.status === "present" ? row.marks_obtained ?? "—" : "—"}</td>
                          <td>{row.error ? <span className="field-error">{row.error}</span> : row.unchanged ? <span className="muted">Unchanged</span> : <Chip tone="green">OK</Chip>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : null}
          </>
        )}
        <div className="page-actions">
          {summary ? null : (
            <button className="btn-pill btn-pill-green" type="button" disabled={busy || !ready.length} onClick={() => void confirm()}>
              {busy ? "Saving…" : `Save ${ready.length} mark${ready.length === 1 ? "" : "s"}`}
            </button>
          )}
          <button className="btn-pill btn-pill-green-soft" type="button" disabled={busy} onClick={onClose}>
            {summary ? "Done" : "Cancel"}
          </button>
        </div>
      </div>
    </div>
  );
}
