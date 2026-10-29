"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextAreaField, TextField } from "@/components/academics/Fields";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, StudentSearch } from "@/components/extras/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { create, displayValue, getOne, remove, type Raw } from "@/lib/extras/api";
import { csvRows, csvTemplate, importErrors, STAFF_IMPORT_COLUMNS, STUDENT_IMPORT_COLUMNS, TEACHER_IMPORT_COLUMNS, teacherRowProblems, type ImportColumn } from "@/lib/extras/csv";
import { refOptions } from "@/lib/extras/refs";
import { listAll } from "@/lib/academics";
import { peopleService, type StudentRow } from "@/lib/people";
import { num } from "@/lib/teaching/client";
import { IconStaff, IconUsers } from "@/lib/icons";

const icon = <IconUsers width={18} height={18} />;

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ---------- Promote ----------

export function PromoteStudents() {
  return (
    <ExtrasPage title="Promote students" description="Move the students of a section to their next class, in the same or a new session." icon={icon}>
      <PromoteBody />
    </ExtrasPage>
  );
}

function PromoteBody() {
  const toast = useToast();
  const [filter, setFilter] = usePlacementFilter();
  const students = useOptions(
    useCallback(
      () => listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, status: "1", sort: "name" })),
      [filter.sessionId, filter.sectionId],
    ),
  );
  const sessions = useOptions(useCallback(() => refOptions("session"), []));
  const sections = useOptions(useCallback(() => refOptions("section"), []));
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [toSession, setToSession] = useState("");
  const [toSection, setToSection] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const ready = Boolean(filter.sessionId && filter.sectionId);
  const rows = ready ? students.options : [];
  const allPicked = rows.length > 0 && rows.every((row) => picked.has(row.id));

  const columns: Column<StudentRow>[] = [
    {
      key: "pick",
      label: "Promote",
      render: (row) => (
        <input
          type="checkbox"
          aria-label={`Promote ${row.name}`}
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
      ),
    },
    { key: "roll", label: "Roll", render: (row) => row.roll_number ?? "—" },
    { key: "name", label: "Student", render: (row) => <strong>{row.name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no },
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPicked(new Set()); }} />
      </div>
      <ErrorAlert error={students.error} onRetry={() => void students.reload()} />
      {ready ? (
        <>
          <div className="resource-card resource-fields">
            <SelectField id="pr-session" label="To session" placeholder="Keep the same session" value={toSession} onChange={setToSession} loading={sessions.loading} options={sessions.options} />
            <SelectField id="pr-section" label="To class and section" required placeholder="Choose the new section" value={toSection} onChange={setToSection} loading={sections.loading} options={sections.options} />
            <div className="field-span page-actions">
              <button className="link-btn" type="button" disabled={!rows.length} onClick={() => setPicked(allPicked ? new Set() : new Set(rows.map((row) => row.id)))}>
                {allPicked ? "Clear all" : "Select all"}
              </button>
              <button className="btn-pill btn-pill-green" type="button" disabled={!picked.size || !toSection} onClick={() => setConfirming(true)}>
                Promote {picked.size} student{picked.size === 1 ? "" : "s"}
              </button>
            </div>
          </div>
          <div className="resource-card">
            <DataTable columns={columns} rows={rows} loading={students.loading} emptyText="No active students in this section." />
          </div>
        </>
      ) : (
        <div className="resource-card">
          <div className="empty-state">Choose the session, class and section to promote from.</div>
        </div>
      )}
      {confirming ? (
        <ConfirmDialog
          title={`Promote ${picked.size} student${picked.size === 1 ? "" : "s"}?`}
          body={`They move to ${sections.options.find((item) => item.value === toSection)?.label ?? "the chosen section"}${toSession ? ` in ${sessions.options.find((item) => item.value === toSession)?.label}` : ""}. Their old class stays in their history.`}
          confirmLabel="Promote"
          pending={pending}
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            setPending(true);
            try {
              const result = await create("/students/promote", { student_ids: [...picked], to_class_section_id: Number(toSection), to_session_year_id: toSession ? Number(toSession) : null });
              toast("success", `${num(result.count)} student${num(result.count) === 1 ? "" : "s"} promoted.`);
              setPicked(new Set());
              void students.reload();
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to promote the students."));
            } finally {
              setPending(false);
              setConfirming(false);
            }
          }}
        />
      ) : null}
    </>
  );
}

// ---------- Transfer ----------

export function TransferStudent() {
  return (
    <ExtrasPage title="Transfer student" description="Record that a student is leaving for another school." icon={icon}>
      <TransferBody />
    </ExtrasPage>
  );
}

function TransferBody() {
  const toast = useToast();
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [school, setSchool] = useState("");
  const [date, setDate] = useState(today());
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const errors = useFormErrors();
  return (
    <>
      <form
        className="resource-card resource-fields"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (!student) {
            errors.setFieldErrors({ student: "Choose the student." });
            return;
          }
          errors.clear();
          setConfirming(true);
        }}
      >
        <StudentSearch id="tr-student" label="Student" required value={student} onChange={setStudent} error={errors.fieldErrors.student} />
        <TextField id="tr-school" label="New school" maxLength={255} value={school} onChange={setSchool} />
        <TextField id="tr-date" label="Leaving date" type="date" value={date} onChange={setDate} />
        <TextAreaField id="tr-reason" label="Reason" value={reason} onChange={setReason} span />
        <div className="field-span">
          <button className="btn-pill btn-pill-green ops-inline-btn" type="submit">
            Transfer student
          </button>
        </div>
      </form>
      {confirming && student ? (
        <ConfirmDialog
          title={`Transfer ${student.name}?`}
          body={`${student.name} will be marked as transferred${school ? ` to ${school}` : ""}.`}
          confirmLabel="Transfer"
          tone="danger"
          pending={pending}
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            setPending(true);
            try {
              await create(`/students/${student.id}/transfer`, { to_school_name: school.trim() || null, transfer_date: date || null, reason: reason.trim() || null });
              toast("success", `${student.name} marked as transferred.`);
              setStudent(null);
              setSchool("");
              setReason("");
            } catch (caught) {
              toast("error", errorMessage(caught, "Unable to transfer the student."));
            } finally {
              setPending(false);
              setConfirming(false);
            }
          }}
        />
      ) : null}
    </>
  );
}

// ---------- Reset password ----------

export function ResetStudentPassword() {
  return (
    <ExtrasPage title="Reset student password" description="Set a new sign-in password for a student." icon={icon}>
      <ResetBody />
    </ExtrasPage>
  );
}

function ResetBody() {
  const toast = useToast();
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    const invalid: Record<string, string> = {};
    if (!student) invalid.student = "Choose the student.";
    if (password.length < 8) invalid.password = "Use at least 8 characters.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await create(`/students/${(student as StudentRow).id}/reset-password`, { password });
      toast("success", `Password changed for ${(student as StudentRow).name}. Share it with them privately.`);
      setPassword("");
      setStudent(null);
    } catch (caught) {
      errors.fromError(caught, "Unable to reset the password.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <form
      className="resource-card resource-fields"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {errors.formError ? <div className="alert alert-danger field-span">{errors.formError}</div> : null}
      <StudentSearch id="rp-student" label="Student" required value={student} onChange={setStudent} error={errors.fieldErrors.student} />
      <TextField id="rp-password" label="New password" type="password" required autoComplete="new-password" value={password} onChange={setPassword} error={errors.fieldErrors.password} hint="At least 8 characters." />
      <div className="field-span">
        <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Reset password"}
        </button>
      </div>
    </form>
  );
}

// ---------- Electives ----------

export function AssignElectives() {
  return (
    <ExtrasPage title="Assign elective subject" description="The optional subjects each student takes." icon={icon}>
      <ElectivesBody />
    </ExtrasPage>
  );
}

function ElectivesBody() {
  const toast = useToast();
  const [student, setStudent] = useState<StudentRow | null>(null);
  const subjects = useOptions(useCallback(() => refOptions("subject"), []));
  const electives = useOptions(useCallback(() => (student ? getOne(`/students/${student.id}/electives`).then((data) => (Array.isArray(data.items) ? (data.items as (Raw & { id: number })[]) : [])) : Promise.resolve([])), [student]));
  const [subjectId, setSubjectId] = useState("");
  const [saving, setSaving] = useState(false);
  const subjectName = (id: unknown) => subjects.options.find((item) => item.value === String(id))?.label ?? `Subject #${num(id)}`;

  const columns: Column<Raw & { id: number }>[] = [
    { key: "subject", label: "Subject", render: (row) => subjectName(row.subject_id) },
    { key: "added", label: "Added", render: (row) => displayValue(row.created_at) },
  ];

  return (
    <>
      <div className="resource-card resource-fields">
        <StudentSearch id="el-student" label="Student" required value={student} onChange={setStudent} />
        {student ? (
          <>
            <SelectField id="el-subject" label="Elective subject" placeholder="Choose a subject" value={subjectId} onChange={setSubjectId} loading={subjects.loading} options={subjects.options} />
            <div className="field-span">
              <button
                className="btn-pill btn-pill-green ops-inline-btn"
                type="button"
                disabled={!subjectId || saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    await create(`/students/${student.id}/electives`, { subject_id: Number(subjectId), session_year_id: student.session_year_id });
                    toast("success", `${subjectName(subjectId)} added for ${student.name}.`);
                    setSubjectId("");
                    void electives.reload();
                  } catch (caught) {
                    toast("error", errorMessage(caught, "Unable to add the elective."));
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                Add elective
              </button>
            </div>
          </>
        ) : null}
      </div>
      {student ? (
        <div className="resource-card">
          <ErrorAlert error={electives.error} onRetry={() => void electives.reload()} />
          <DataTable
            columns={columns}
            rows={electives.options}
            loading={electives.loading}
            emptyText={`${student.name} has no elective subjects yet.`}
            actions={(row) => (
              <button
                className="link-btn danger"
                type="button"
                onClick={async () => {
                  try {
                    await remove(`/students/${student.id}/electives/${row.id}`);
                    toast("success", "Elective removed.");
                    void electives.reload();
                  } catch (caught) {
                    toast("error", errorMessage(caught, "Unable to remove the elective."));
                  }
                }}
              >
                Remove
              </button>
            )}
          />
        </div>
      ) : null}
    </>
  );
}

// ---------- Bulk import ----------

export function ImportStudents() {
  return (
    <ExtrasPage title="Add bulk data" description="Add many students at once from a CSV file (up to 500 rows)." icon={icon} note="Each student needs an existing parent: put the parent's user id in guardian_id. If any row has a problem, nothing is added.">
      <ImportBody path="/students/import" columns={STUDENT_IMPORT_COLUMNS} noun="student" template="students-template.csv" />
    </ExtrasPage>
  );
}

export function ImportTeachers() {
  return (
    <ExtrasPage
      title="Bulk upload teachers"
      description="Add many teachers at once from a CSV file (up to 500 rows)."
      icon={<IconStaff width={18} height={18} />}
      note="Each teacher is added on their own, so one bad row doesn't stop the others. Each needs a password of at least 8 characters; share it with them privately. A teacher whose email already exists isn't added again."
    >
      <ImportBody path="/teachers" columns={TEACHER_IMPORT_COLUMNS} noun="teacher" template="teachers-template.csv" perRow check={teacherRowProblems} />
    </ExtrasPage>
  );
}

export function ImportStaff() {
  return (
    <ExtrasPage title="Bulk upload staff" description="Add many non-teaching staff at once from a CSV file (up to 500 rows)." icon={<IconStaff width={18} height={18} />} note="Each row needs a password of at least 8 characters. If any row has a problem, nothing is added.">
      <ImportBody path="/staff/import" columns={STAFF_IMPORT_COLUMNS} noun="staff member" template="staff-template.csv" />
    </ExtrasPage>
  );
}

/**
 * CSV import. With `perRow`, rows are sent one at a time to a route that adds one record (for
 * servers without a bulk route); each row's result is listed and the ones that failed can be
 * fixed and uploaded again. Otherwise all rows go in one request, all or nothing.
 */
function ImportBody({ path, columns, noun, template, perRow, check }: { path: string; columns: ImportColumn[]; noun: string; template: string; perRow?: boolean; check?: (rows: Record<string, string | number>[]) => string[] }) {
  const toast = useToast();
  const [fileName, setFileName] = useState("");
  const [parsed, setParsed] = useState<ReturnType<typeof csvRows> | null>(null);
  const [serverProblems, setServerProblems] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState<{ row: number; label: string; ok: boolean; message: string }[]>([]);
  const [progress, setProgress] = useState(0);
  const templateUrl = useMemo(() => `data:text/csv;charset=utf-8,${encodeURIComponent(csvTemplate(columns))}`, [columns]);

  return (
    <>
      <div className="resource-card">
        <p>
          The first line must name the columns. Required: {columns.filter((c) => c.required).map((c) => c.key).join(", ")}. Optional: {columns.filter((c) => !c.required).map((c) => c.key).join(", ")}.
        </p>
        <div className="page-actions">
          <a className="btn-pill btn-pill-green-soft" href={templateUrl} download={template}>
            Download template
          </a>
          <label className="btn-pill btn-pill-green">
            Choose CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              className="acad-sr"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                setFileName(file.name);
                setServerProblems([]);
                setResults([]);
                const result = csvRows(await file.text(), columns);
                setParsed({ ...result, problems: [...result.problems, ...(check ? check(result.rows) : [])] });
              }}
            />
          </label>
        </div>
      </div>
      {parsed ? (
        <div className="resource-card">
          <p>
            <strong>{fileName}</strong>: {parsed.rows.length} row{parsed.rows.length === 1 ? "" : "s"}
          </p>
          {[...parsed.problems, ...serverProblems].length ? (
            <div className="alert alert-danger">
              <ul className="teach-list">
                {[...parsed.problems, ...serverProblems].slice(0, 30).map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <button
            className="btn-pill btn-pill-green"
            type="button"
            disabled={saving || parsed.problems.length > 0 || parsed.rows.length === 0}
            onClick={async () => {
              setSaving(true);
              setServerProblems([]);
              if (perRow) {
                const done: typeof results = [];
                for (const [index, row] of parsed.rows.entries()) {
                  const label = `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() || String(row.email ?? `Row ${index + 2}`);
                  try {
                    await create(path, row);
                    done.push({ row: index + 2, label, ok: true, message: "Added" });
                  } catch (caught) {
                    done.push({ row: index + 2, label, ok: false, message: errorMessage(caught, "Couldn't be added.") });
                  }
                  setProgress(index + 1);
                  setResults([...done]);
                }
                const added = done.filter((item) => item.ok).length;
                toast(added === done.length ? "success" : "error", `${added} of ${done.length} ${noun}s added.${added === done.length ? "" : " The rows that failed are listed below."}`);
                setSaving(false);
                setProgress(0);
                if (added === done.length) {
                  setParsed(null);
                  setFileName("");
                }
                return;
              }
              try {
                const result = await create(path, { rows: parsed.rows });
                const count = num(result.created ?? (Array.isArray(result.items) ? result.items.length : parsed.rows.length));
                toast("success", `${count} ${noun}${count === 1 ? "" : "s"} added.`);
                setParsed(null);
                setFileName("");
              } catch (caught) {
                const rows = importErrors(caught instanceof Error ? caught.message : "");
                setServerProblems(rows.length ? rows : [errorMessage(caught, "The import failed.")]);
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? (perRow ? `Adding ${progress} of ${parsed.rows.length}…` : "Adding…") : `Add ${parsed.rows.length} ${noun}${parsed.rows.length === 1 ? "" : "s"}`}
          </button>
        </div>
      ) : null}
      {results.length ? (
        <div className="resource-card">
          <p>
            <strong>{results.filter((item) => item.ok).length}</strong> added, <strong>{results.filter((item) => !item.ok).length}</strong> failed.
          </p>
          <ul className="teach-list">
            {results.map((item) => (
              <li key={item.row} className={item.ok ? undefined : "field-error"}>
                Row {item.row}, {item.label}: {item.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}
