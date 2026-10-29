"use client";

import { useCallback, useMemo, useState } from "react";
import { TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { Chip, formatDateTime, fromLocalInput, toLocalInput, type ChipTone } from "@/components/teaching/Frame";
import { EMPTY_PLACEMENT, PlacementFields, SubjectTeacherFields, type PlacementValue } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { bankQuestions, copyBankQuestionsToExam, examService, questionProblems } from "@/lib/teaching/exams";
import type { AttemptStatus, BankQuestion, Choice, ExamStatus, OnlineExam, OnlineExamInput, Question, QuestionInput } from "@/lib/teaching/types";

export const EXAM_TABS = [
  { href: "/school/online-exams", label: "Exams" },
  { href: "/school/online-exams/question-bank", label: "Question bank" },
];

export const EXAMS_LIVE_NOTE = "Connected to the school's server.";

export const EXAM_STATUS: Record<ExamStatus, { label: string; tone: ChipTone }> = {
  draft: { label: "Draft", tone: "grey" },
  published: { label: "Published", tone: "green" },
  closed: { label: "Closed", tone: "red" },
};

export const ATTEMPT_STATUS: Record<AttemptStatus, { label: string; tone: ChipTone }> = {
  in_progress: { label: "In progress", tone: "amber" },
  submitted: { label: "Submitted", tone: "blue" },
  expired: { label: "Expired", tone: "grey" },
  evaluated: { label: "Evaluated", tone: "green" },
};

export function ExamStatusChip({ status }: { status: ExamStatus }) {
  return <Chip tone={EXAM_STATUS[status].tone}>{EXAM_STATUS[status].label}</Chip>;
}

export const MAX_CHOICES = 8;
export const MAX_IMPORT = 100;

/** Create or edit an exam's details. Questions are managed on the exam page. */
export function ExamForm({ exam, onClose, onSaved }: { exam: OnlineExam | null; onClose: () => void; onSaved: (saved: OnlineExam, created: boolean) => void }) {
  const [placement, setPlacement] = useState<PlacementValue>(
    exam ? { session_year_id: String(exam.session_year_id), class_id: String(exam.class_id), class_section_id: String(exam.class_section_id) } : EMPTY_PLACEMENT,
  );
  const [subjectId, setSubjectId] = useState(exam ? String(exam.subject_id) : "");
  const [teacherId, setTeacherId] = useState(exam ? String(exam.teacher_user_id) : "");
  const [title, setTitle] = useState(exam?.title ?? "");
  const [instructions, setInstructions] = useState(exam?.instructions ?? "");
  const [duration, setDuration] = useState(exam ? String(exam.duration_minutes) : "30");
  const [total, setTotal] = useState(exam ? String(exam.total_marks) : "");
  const [passing, setPassing] = useState(exam ? String(exam.passing_marks) : "");
  const [from, setFrom] = useState(toLocalInput(exam?.available_from));
  const [until, setUntil] = useState(toLocalInput(exam?.available_until));
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const onPlacement = useCallback((value: PlacementValue) => setPlacement(value), []);
  const onTeacher = useCallback((value: string) => setTeacherId(value), []);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!placement.session_year_id) invalid.session_year_id = "Choose an academic session.";
    if (!placement.class_id) invalid.class_id = "Choose a class.";
    if (!placement.class_section_id) invalid.class_section_id = "Choose a section.";
    if (!subjectId) invalid.subject_id = "Choose a subject.";
    if (!teacherId) invalid.teacher_user_id = "Choose a teacher.";
    if (!title.trim()) invalid.title = "Enter the exam name.";
    if (!(Number(duration) >= 1)) invalid.duration_minutes = "Duration must be at least 1 minute.";
    if (!(Number(total) > 0)) invalid.total_marks = "Total marks must be more than 0.";
    if (passing === "" || Number(passing) < 0 || Number(passing) > Number(total)) invalid.passing_marks = "Passing marks must be between 0 and the total marks.";
    if (!from) invalid.available_from = "Choose when the exam opens.";
    if (!until) invalid.available_until = "Choose when the exam closes.";
    else if (from && until <= from) invalid.available_until = "The exam must close after it opens.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const input: OnlineExamInput = {
      session_year_id: Number(placement.session_year_id),
      class_section_id: Number(placement.class_section_id),
      subject_id: Number(subjectId),
      teacher_user_id: Number(teacherId),
      title: title.trim(),
      instructions: instructions.trim() || null,
      duration_minutes: Number(duration),
      total_marks: Number(total),
      passing_marks: Number(passing),
      available_from: fromLocalInput(from),
      available_until: fromLocalInput(until),
    };
    try {
      onSaved(exam ? await examService().update(exam.id, input) : await examService().create(input), !exam);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the exam.");
      setSaving(false);
    }
  }

  const dateField = (id: string, label: string, value: string, set: (value: string) => void, key: string) => (
    <div className="form-field">
      <label htmlFor={id}>{label} *</label>
      <input id={id} type="datetime-local" value={value} className={errors.fieldErrors[key] ? "invalid" : undefined} aria-invalid={Boolean(errors.fieldErrors[key])} onChange={(event) => set(event.target.value)} />
      {errors.fieldErrors[key] ? <p className="field-error">{errors.fieldErrors[key]}</p> : null}
    </div>
  );

  return (
    <FormModal
      title={exam ? "Edit online exam" : "Create online exam"}
      description={exam ? undefined : "The exam starts as a draft. Add questions, then publish it for students."}
      error={errors.formError}
      saving={saving}
      submitLabel={exam ? "Save changes" : "Create exam"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <PlacementFields idPrefix="ex" value={placement} onChange={onPlacement} errors={errors.fieldErrors} />
      <SubjectTeacherFields idPrefix="ex" placement={placement} subjectId={subjectId} teacherId={teacherId} onSubject={setSubjectId} onTeacher={onTeacher} errors={errors.fieldErrors} />
      <TextField id="ex-title" label="Exam name" required span maxLength={200} value={title} onChange={setTitle} error={errors.fieldErrors.title} />
      <TextAreaField id="ex-instructions" label="Instructions for students" span maxLength={5000} value={instructions} onChange={setInstructions} error={errors.fieldErrors.instructions} />
      <TextField id="ex-duration" label="Duration (minutes)" type="number" min="1" required value={duration} onChange={setDuration} error={errors.fieldErrors.duration_minutes} />
      <TextField id="ex-total" label="Total marks" type="number" min="1" required value={total} onChange={setTotal} error={errors.fieldErrors.total_marks} hint="Question marks must add up to this before publishing." />
      <TextField id="ex-passing" label="Passing marks" type="number" min="0" required value={passing} onChange={setPassing} error={errors.fieldErrors.passing_marks} />
      {dateField("ex-from", "Opens", from, setFrom, "available_from")}
      {dateField("ex-until", "Closes", until, setUntil, "available_until")}
    </FormModal>
  );
}

const blankChoices = (): Choice[] => [
  { choice_text: "", is_correct: true },
  { choice_text: "", is_correct: false },
  { choice_text: "", is_correct: false },
  { choice_text: "", is_correct: false },
];

/** Editor for one multiple-choice question: 2–8 choices with exactly one correct answer. */
export function QuestionForm({
  title,
  question,
  nextOrder,
  extra,
  onClose,
  onSubmit,
}: {
  title: string;
  question: QuestionInput | null;
  nextOrder: number;
  extra?: React.ReactNode;
  onClose: () => void;
  /** Saves the question; throw to show the error in the form. */
  onSubmit: (input: QuestionInput) => Promise<void>;
}) {
  const [text, setText] = useState(question?.question_text ?? "");
  const [topic, setTopic] = useState(question?.topic ?? "");
  const [marks, setMarks] = useState(question ? String(question.marks) : "1");
  const [choices, setChoices] = useState<Choice[]>(question ? question.choices.map((c) => ({ choice_text: c.choice_text, is_correct: c.is_correct })) : blankChoices());
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  function update(index: number, patch: Partial<Choice>) {
    setChoices((list) => list.map((choice, i) => (i === index ? { ...choice, ...patch } : patch.is_correct ? { ...choice, is_correct: false } : choice)));
  }

  async function submit() {
    const input: QuestionInput = { question_text: text, topic: topic.trim() || null, marks: Number(marks), sort_order: question?.sort_order ?? nextOrder, choices };
    const problems = questionProblems(input);
    if (choices.some((choice) => choice.is_correct && !choice.choice_text.trim())) problems.choices = "The choice marked correct is empty.";
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await onSubmit(input);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the question.");
      setSaving(false);
    }
  }

  return (
    <FormModal title={title} error={errors.formError} saving={saving} submitLabel="Save question" wide onSubmit={() => void submit()} onClose={onClose}>
      <TextAreaField id="q-text" label="Question" required span rows={3} maxLength={5000} value={text} onChange={setText} error={errors.fieldErrors.question_text} />
      <TextField id="q-marks" label="Marks" type="number" min="0.5" required value={marks} onChange={setMarks} error={errors.fieldErrors.marks} />
      <TextField id="q-topic" label="Topic" maxLength={120} value={topic} onChange={setTopic} />
      <fieldset className="form-field field-span teach-choices">
        <legend>Answer choices * <span className="muted">(select the correct one)</span></legend>
        {choices.map((choice, index) => (
          <div key={index} className="teach-choice">
            <input type="radio" name="q-correct" id={`q-correct-${index}`} checked={choice.is_correct} onChange={() => update(index, { is_correct: true })} aria-label={`Choice ${index + 1} is correct`} />
            <input
              type="text"
              aria-label={`Choice ${index + 1}`}
              placeholder={`Choice ${index + 1}`}
              maxLength={1000}
              value={choice.choice_text}
              onChange={(event) => update(index, { choice_text: event.target.value })}
            />
            <button className="link-btn" type="button" disabled={choices.length <= 2} onClick={() => setChoices((list) => {
              const next = list.filter((_, i) => i !== index);
              if (!next.some((c) => c.is_correct)) next[0] = { ...next[0], is_correct: true };
              return next;
            })}>
              Remove<span className="acad-sr"> choice {index + 1}</span>
            </button>
          </div>
        ))}
        <button className="link-btn" type="button" disabled={choices.length >= MAX_CHOICES} onClick={() => setChoices((list) => [...list, { choice_text: "", is_correct: false }])}>
          + Add choice
        </button>
        {errors.fieldErrors.choices ? <p className="field-error">{errors.fieldErrors.choices}</p> : <p className="field-hint">2 to {MAX_CHOICES} choices, exactly one correct.</p>}
      </fieldset>
      {extra}
    </FormModal>
  );
}

// ---------- bulk import ----------

export type ParsedImport = { items: QuestionInput[]; problems: string[] };

/** Splits one CSV line, honouring double-quoted fields. */
function csvCells(line: string): string[] {
  const cells: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      cells.push(cell.trim());
      cell = "";
    } else cell += ch;
  }
  cells.push(cell.trim());
  return cells;
}

/** Correct answer as a letter (A–H), a number (1–8) or the choice text. */
function correctIndex(answer: string, choices: string[]): number {
  const value = answer.trim();
  if (/^[A-Ha-h]$/.test(value)) return value.toUpperCase().charCodeAt(0) - 65;
  if (/^[1-8]$/.test(value)) return Number(value) - 1;
  return choices.findIndex((choice) => choice.toLowerCase() === value.toLowerCase());
}

function toInput(question: string, marks: number, topic: string | null, options: string[], answer: string, order: number): QuestionInput {
  const index = correctIndex(answer, options);
  return { question_text: question, marks, topic, sort_order: order, choices: options.map((choice_text, i) => ({ choice_text, is_correct: i === index })) };
}

/**
 * Reads questions from CSV (header: question, marks, topic, choice_a … choice_h, correct) or JSON
 * (an array of {question_text, marks, topic, choices:[{choice_text, is_correct}]} or
 * {question, options:[…], answer}). Every question is checked with the same rules as the form.
 */
export function parseQuestionFile(text: string, firstOrder: number): ParsedImport {
  const problems: string[] = [];
  const items: QuestionInput[] = [];
  const trimmed = text.trim();
  if (!trimmed) return { items, problems: ["The file is empty."] };
  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    let data: unknown;
    try {
      data = JSON.parse(trimmed);
    } catch {
      return { items, problems: ["The JSON couldn't be read. Check for missing commas or quotes."] };
    }
    const list = Array.isArray(data) ? data : Array.isArray((data as { items?: unknown }).items) ? (data as { items: unknown[] }).items : null;
    if (!list) return { items, problems: ["The JSON must be a list of questions."] };
    list.forEach((raw, index) => {
      const row = (raw ?? {}) as Record<string, unknown>;
      const question = String(row.question_text ?? row.question ?? "");
      const marks = Number(row.marks ?? 1);
      const topic = row.topic ? String(row.topic) : null;
      let input: QuestionInput;
      if (Array.isArray(row.choices)) {
        input = {
          question_text: question,
          marks,
          topic,
          sort_order: firstOrder + index,
          choices: (row.choices as Record<string, unknown>[]).map((c) => ({ choice_text: String(c?.choice_text ?? c?.text ?? ""), is_correct: Boolean(c?.is_correct) })),
        };
      } else {
        const options = Array.isArray(row.options) ? (row.options as unknown[]).map(String) : [];
        input = toInput(question, marks, topic, options, String(row.answer ?? row.correct ?? ""), firstOrder + index);
      }
      const errors = Object.values(questionProblems(input));
      if (errors.length) problems.push(`Question ${index + 1}: ${errors[0]}`);
      else items.push(input);
    });
  } else {
    const lines = trimmed.split(/\r?\n/).filter((line) => line.trim());
    const header = csvCells(lines[0]).map((cell) => cell.toLowerCase());
    const col = (name: string) => header.indexOf(name);
    if (col("question") < 0 || col("correct") < 0) return { items, problems: ["The CSV needs a header row with at least question, choice_a, choice_b and correct columns."] };
    const choiceCols = header.map((name, index) => (/^choice_[a-h]$/.test(name) ? index : -1)).filter((index) => index >= 0);
    lines.slice(1).forEach((line, index) => {
      const cells = csvCells(line);
      const options = choiceCols.map((i) => cells[i] ?? "").filter(Boolean);
      const marks = col("marks") >= 0 && cells[col("marks")] ? Number(cells[col("marks")]) : 1;
      const topic = col("topic") >= 0 ? cells[col("topic")] || null : null;
      const input = toInput(cells[col("question")] ?? "", marks, topic, options, cells[col("correct")] ?? "", firstOrder + index);
      const errors = Object.values(questionProblems(input));
      if (errors.length) problems.push(`Row ${index + 2}: ${errors[0]}`);
      else items.push(input);
    });
  }
  if (items.length + problems.length > MAX_IMPORT) problems.unshift(`Import up to ${MAX_IMPORT} questions at a time. Split the file and try again.`);
  return { items, problems };
}

export const CSV_TEMPLATE = 'question,marks,topic,choice_a,choice_b,choice_c,choice_d,correct\n"What is 7 × 8?",1,Multiplication,54,56,63,48,B\n';

/** Upload or paste a CSV/JSON file of questions and import the valid ones in one request. */
export function ImportQuestions({ examId, nextOrder, onClose, onImported }: { examId: number; nextOrder: number; onClose: () => void; onImported: (count: number) => void }) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const parsed = useMemo(() => (text.trim() ? parseQuestionFile(text, nextOrder) : null), [text, nextOrder]);
  const tooMany = (parsed?.items.length ?? 0) + (parsed?.problems.length ?? 0) > MAX_IMPORT;

  async function submit() {
    if (!parsed || parsed.items.length === 0) {
      errors.setFormError("There are no valid questions to import yet.");
      return;
    }
    if (tooMany) {
      errors.setFormError(`Import up to ${MAX_IMPORT} questions at a time.`);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      onImported(await examService().importQuestions(examId, parsed.items));
    } catch (caught) {
      errors.fromError(caught, "Unable to import the questions.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title="Import questions"
      description={`Upload a CSV or JSON file, or paste its contents. Up to ${MAX_IMPORT} questions per import.`}
      error={errors.formError || errors.fieldErrors.import || errors.fieldErrors.items}
      saving={saving}
      submitLabel={parsed?.items.length ? `Import ${parsed.items.length} question${parsed.items.length === 1 ? "" : "s"}` : "Import"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <div className="form-field field-span">
        <label htmlFor="imp-file">File</label>
        <input
          id="imp-file"
          type="file"
          accept=".csv,.json,text/csv,application/json"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            if (file.size > 1024 * 1024) {
              errors.setFormError("The file is larger than 1 MB.");
              return;
            }
            setText(await file.text());
          }}
        />
        <p className="field-hint">
          CSV columns: question, marks, topic, choice_a … choice_h, correct (a letter like B).{" "}
          <a className="link-btn" href={`data:text/csv;charset=utf-8,${encodeURIComponent(CSV_TEMPLATE)}`} download="questions-template.csv">
            Download a template
          </a>
        </p>
      </div>
      <TextAreaField id="imp-text" label="Or paste CSV / JSON" span rows={6} value={text} onChange={setText} />
      {parsed ? (
        <div className="field-span" role="status">
          <p>
            <Chip tone={parsed.items.length ? "green" : "grey"}>{parsed.items.length} ready</Chip>{" "}
            {parsed.problems.length ? <Chip tone="red">{parsed.problems.length} with problems</Chip> : null}
          </p>
          {parsed.problems.length ? (
            <ul className="teach-list teach-problems">
              {parsed.problems.slice(0, 10).map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
              {parsed.problems.length > 10 ? <li>…and {parsed.problems.length - 10} more</li> : null}
            </ul>
          ) : null}
        </div>
      ) : null}
    </FormModal>
  );
}

/** Pick questions from the bank and copy them into an exam. */
export function BankPicker({ examId, nextOrder, onClose, onCopied }: { examId: number; nextOrder: number; onClose: () => void; onCopied: (count: number, failures: string[]) => void }) {
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const all = useOptions(useCallback(() => bankQuestions(), []));
  const rows = all.options.filter((row) => !search.trim() || `${row.question_text} ${row.topic ?? ""} ${row.subject_name ?? ""}`.toLowerCase().includes(search.trim().toLowerCase()));

  async function submit() {
    const chosen = all.options.filter((row) => picked.has(row.id));
    if (!chosen.length) {
      setError("Pick at least one question.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const failures = await copyBankQuestionsToExam(examId, chosen.map((row, index) => ({ ...row, sort_order: nextOrder + index }) as BankQuestion));
      onCopied(chosen.length - failures.length, failures);
    } catch (caught) {
      setError(errorMessage(caught, "Unable to copy the questions."));
      setSaving(false);
    }
  }

  return (
    <FormModal title="Add from question bank" error={error} saving={saving} submitLabel={`Add ${picked.size || ""} question${picked.size === 1 ? "" : "s"}`.replace("  ", " ")} wide onSubmit={() => void submit()} onClose={onClose}>
      <div className="form-field field-span">
        <label htmlFor="bank-search">Search</label>
        <input id="bank-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Question, topic or subject" />
      </div>
      <ul className="teach-bank-list field-span">
        {rows.length === 0 ? <li className="muted">{all.options.length ? "No questions match." : "The question bank is empty. Add questions under Question bank."}</li> : null}
        {rows.map((row) => (
          <li key={row.id}>
            <label className="acad-check">
              <input
                type="checkbox"
                checked={picked.has(row.id)}
                onChange={(event) =>
                  setPicked((current) => {
                    const next = new Set(current);
                    if (event.target.checked) next.add(row.id);
                    else next.delete(row.id);
                    return next;
                  })
                }
              />
              <span>
                {row.question_text}
                <span className="muted">
                  {" "}
                  · {row.marks} mark{row.marks === 1 ? "" : "s"}
                  {row.subject_name ? ` · ${row.subject_name}` : ""}
                  {row.topic ? ` · ${row.topic}` : ""}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </FormModal>
  );
}

/** Read-only view of one question with its correct answer (admins only). */
export function QuestionCard({ index, question, actions }: { index: number; question: Question; actions?: React.ReactNode }) {
  return (
    <li className="teach-question">
      <div className="teach-question-head">
        <strong>
          Q{index + 1}. {question.question_text}
        </strong>
        <span className="muted">
          {question.marks} mark{question.marks === 1 ? "" : "s"}
          {question.topic ? ` · ${question.topic}` : ""}
        </span>
      </div>
      <ol className="teach-choice-list" type="A">
        {question.choices.map((choice, i) => (
          <li key={choice.id ?? i} className={choice.is_correct ? "is-correct" : undefined}>
            {choice.choice_text}
            {choice.is_correct ? <span className="acad-sr"> (correct answer)</span> : null}
            {choice.is_correct ? <span aria-hidden> ✓</span> : null}
          </li>
        ))}
      </ol>
      {actions ? <div className="teach-question-actions">{actions}</div> : null}
    </li>
  );
}

export function examWindow(exam: OnlineExam): string {
  return `${formatDateTime(exam.available_from)} → ${formatDateTime(exam.available_until)}`;
}
