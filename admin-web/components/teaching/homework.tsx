"use client";

import { useCallback, useState } from "react";
import { StatusToggle, TextAreaField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors } from "@/components/academics/hooks";
import { Chip, FileButton, formatBytes, fromLocalInput, toLocalInput, type ChipTone } from "@/components/teaching/Frame";
import { EMPTY_PLACEMENT, PlacementFields, SubjectTeacherFields, type PlacementValue } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { homeworkService } from "@/lib/teaching/homework";
import { MATERIAL_FILE_ACCEPT, materialFileProblem } from "@/lib/teaching/materials";
import type { AssignmentStatus, Evaluation, Homework, HomeworkInput, Submission } from "@/lib/teaching/types";

export const MAX_ATTACHMENTS = 10;

export const HOMEWORK_LIVE_NOTE = "Connected to the school's server. Attachment names are shown, but the server doesn't offer downloads for homework files yet.";

export const SUBMISSION_STATUS: Record<AssignmentStatus, { label: string; tone: ChipTone }> = {
  pending: { label: "Pending", tone: "grey" },
  submitted: { label: "Submitted", tone: "blue" },
  late: { label: "Late", tone: "amber" },
  graded: { label: "Graded", tone: "green" },
};

export function SubmissionChip({ status }: { status: AssignmentStatus }) {
  return <Chip tone={SUBMISSION_STATUS[status].tone}>{SUBMISSION_STATUS[status].label}</Chip>;
}

function today(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

/** Files waiting to upload after a form is saved. */
export function AttachmentPicker({ id, files, onChange, existingCount }: { id: string; files: File[]; onChange: (files: File[]) => void; existingCount: number }) {
  const [problems, setProblems] = useState<string[]>([]);
  const room = MAX_ATTACHMENTS - existingCount - files.length;
  return (
    <div className="form-field field-span">
      <label htmlFor={id}>Attachments</label>
      <input
        id={id}
        type="file"
        multiple
        accept={MATERIAL_FILE_ACCEPT}
        disabled={room <= 0}
        onChange={(event) => {
          const errors: string[] = [];
          const accepted: File[] = [];
          for (const file of Array.from(event.target.files ?? [])) {
            const problem = materialFileProblem(file);
            if (problem) errors.push(problem);
            else if (accepted.length >= room) errors.push(`${file.name} wasn't added. Homework can have up to ${MAX_ATTACHMENTS} attachments.`);
            else accepted.push(file);
          }
          setProblems(errors);
          if (accepted.length) onChange([...files, ...accepted]);
          event.target.value = "";
        }}
      />
      <p className="field-hint">PDF, images or Office files, up to 10 MB each and {MAX_ATTACHMENTS} per homework.</p>
      {problems.map((problem) => (
        <p key={problem} className="field-error" role="alert">
          {problem}
        </p>
      ))}
      {files.length ? (
        <ul className="teach-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`}>
              {file.name} ({formatBytes(file.size)}){" "}
              <button className="link-btn" type="button" onClick={() => onChange(files.filter((_, i) => i !== index))}>
                Remove<span className="acad-sr"> {file.name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Add or edit homework. New attachments upload one by one after the homework is saved. */
export function HomeworkForm({
  homework,
  onClose,
  onSaved,
}: {
  homework: Homework | null;
  onClose: () => void;
  onSaved: (saved: Homework, created: boolean, uploadFailures: string[]) => void;
}) {
  const [placement, setPlacement] = useState<PlacementValue>(
    homework ? { session_year_id: String(homework.session_year_id), class_id: String(homework.class_id), class_section_id: String(homework.class_section_id) } : EMPTY_PLACEMENT,
  );
  const [subjectId, setSubjectId] = useState(homework ? String(homework.subject_id) : "");
  const [teacherId, setTeacherId] = useState(homework ? String(homework.teacher_user_id) : "");
  const [title, setTitle] = useState(homework?.title ?? "");
  const [instructions, setInstructions] = useState(homework?.instructions ?? "");
  const [assigned, setAssigned] = useState(homework?.assigned_date ?? today());
  const [deadline, setDeadline] = useState(toLocalInput(homework?.deadline_at));
  const [maxMarks, setMaxMarks] = useState(homework?.max_marks !== null && homework?.max_marks !== undefined ? String(homework.max_marks) : "");
  const [allowLate, setAllowLate] = useState(homework?.allow_late ?? false);
  const [files, setFiles] = useState<File[]>([]);
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
    if (!title.trim()) invalid.title = "Enter a title.";
    if (!assigned) invalid.assigned_date = "Enter the assigned date.";
    if (!deadline) invalid.deadline_at = "Enter the deadline.";
    else if (assigned && deadline.slice(0, 10) < assigned) invalid.deadline_at = "The deadline can't be before the assigned date.";
    if (maxMarks && !(Number(maxMarks) > 0)) invalid.max_marks = "Maximum marks must be more than 0.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const input: HomeworkInput = {
      session_year_id: Number(placement.session_year_id),
      class_section_id: Number(placement.class_section_id),
      subject_id: Number(subjectId),
      teacher_user_id: Number(teacherId),
      title: title.trim(),
      instructions: instructions.trim() || null,
      assigned_date: assigned,
      deadline_at: fromLocalInput(deadline),
      max_marks: maxMarks ? Number(maxMarks) : null,
      allow_late: allowLate,
    };
    let saved: Homework;
    try {
      saved = homework ? await homeworkService().update(homework.id, input) : await homeworkService().create(input);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the homework.");
      setSaving(false);
      return;
    }
    const failures: string[] = [];
    for (const file of files) {
      try {
        await homeworkService().addAttachment(saved.id, file);
      } catch (caught) {
        failures.push(`${file.name}: ${errorMessage(caught, "upload failed")}`);
      }
    }
    onSaved(saved, !homework, failures);
  }

  return (
    <FormModal
      title={homework ? "Edit homework" : "Add homework"}
      error={errors.formError}
      saving={saving}
      submitLabel={homework ? "Save changes" : "Add homework"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <PlacementFields idPrefix="hw" value={placement} onChange={onPlacement} errors={errors.fieldErrors} />
      <SubjectTeacherFields idPrefix="hw" placement={placement} subjectId={subjectId} teacherId={teacherId} onSubject={setSubjectId} onTeacher={onTeacher} errors={errors.fieldErrors} />
      <TextField id="hw-title" label="Title" required span maxLength={200} value={title} onChange={setTitle} error={errors.fieldErrors.title} />
      <TextAreaField id="hw-instructions" label="Instructions" span rows={4} maxLength={5000} value={instructions} onChange={setInstructions} error={errors.fieldErrors.instructions} />
      <TextField id="hw-assigned" label="Assigned on" type="date" required value={assigned} onChange={setAssigned} error={errors.fieldErrors.assigned_date} />
      <div className="form-field">
        <label htmlFor="hw-deadline">Deadline *</label>
        <input
          id="hw-deadline"
          type="datetime-local"
          value={deadline}
          className={errors.fieldErrors.deadline_at ? "invalid" : undefined}
          aria-invalid={Boolean(errors.fieldErrors.deadline_at)}
          onChange={(event) => setDeadline(event.target.value)}
        />
        {errors.fieldErrors.deadline_at ? <p className="field-error">{errors.fieldErrors.deadline_at}</p> : null}
      </div>
      <TextField id="hw-marks" label="Maximum marks" type="number" min="1" value={maxMarks} onChange={setMaxMarks} error={errors.fieldErrors.max_marks} hint="Leave empty for ungraded homework." />
      <div className="form-field">
        <span className="field-label">Late work</span>
        <StatusToggle id="hw-late" checked={allowLate} onChange={setAllowLate} label="Accept submissions after the deadline" />
      </div>
      {homework?.attachments.length ? (
        <div className="form-field field-span">
          <span className="field-label">Current attachments</span>
          <ul className="teach-list">
            {homework.attachments.map((file, index) => (
              <li key={`${file.original_filename}-${index}`}>
                <FileButton file={file} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <AttachmentPicker id="hw-files" files={files} onChange={setFiles} existingCount={homework?.attachments.length ?? 0} />
    </FormModal>
  );
}

/** Marks, grade and feedback for one submission. */
export function EvaluationForm({
  homework,
  submission,
  onClose,
  onSaved,
}: {
  homework: Homework;
  submission: Submission;
  onClose: () => void;
  onSaved: (saved: Submission) => void;
}) {
  const [marks, setMarks] = useState(submission.marks !== null ? String(submission.marks) : "");
  const [grade, setGrade] = useState(submission.grade ?? "");
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  async function submit() {
    const invalid: Record<string, string> = {};
    const value = marks === "" ? null : Number(marks);
    if (value !== null && (Number.isNaN(value) || value < 0)) invalid.marks = "Marks can't be negative.";
    else if (value !== null && homework.max_marks !== null && value > homework.max_marks) invalid.marks = `Marks can't be more than ${homework.max_marks}.`;
    if (value === null && !grade.trim() && !feedback.trim()) invalid.marks = "Enter marks, a grade or feedback.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const evaluation: Evaluation = { marks: value, grade: grade.trim() || null, feedback: feedback.trim() || null };
    try {
      onSaved(await homeworkService().evaluate(submission.id, evaluation));
    } catch (caught) {
      errors.fromError(caught, "Unable to save the evaluation.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={`Evaluate ${submission.student_name}`}
      description={`${homework.title}${submission.submitted_at ? ` · handed in ${new Date(submission.submitted_at).toLocaleString()}` : ""}${submission.is_late ? " (late)" : ""}`}
      error={errors.formError}
      saving={saving}
      submitLabel="Save evaluation"
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <div className="form-field field-span">
        <span className="field-label">Answer</span>
        {submission.text_response ? <p className="teach-response">{submission.text_response}</p> : <p className="muted">No written answer.</p>}
        {submission.attachments.length ? (
          <ul className="teach-list">
            {submission.attachments.map((file, index) => (
              <li key={`${file.original_filename}-${index}`}>
                <FileButton file={file} />
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <TextField
        id="ev-marks"
        label={homework.max_marks !== null ? `Marks (out of ${homework.max_marks})` : "Marks"}
        type="number"
        min="0"
        max={homework.max_marks !== null ? String(homework.max_marks) : undefined}
        value={marks}
        onChange={setMarks}
        error={errors.fieldErrors.marks}
      />
      <TextField id="ev-grade" label="Grade" maxLength={20} placeholder="A, B+, …" value={grade} onChange={setGrade} error={errors.fieldErrors.grade} />
      <TextAreaField id="ev-feedback" label="Feedback" span rows={4} maxLength={5000} value={feedback} onChange={setFeedback} error={errors.fieldErrors.feedback} />
    </FormModal>
  );
}
