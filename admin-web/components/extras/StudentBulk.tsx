"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage } from "@/components/extras/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { errorMessage, listAll } from "@/lib/academics";
import { peopleService, type Student, type StudentInput, type StudentRow } from "@/lib/people";
import { PHOTO_ACCEPT, photoProblem } from "@/lib/people/files";
import { settleLimited } from "@/lib/teaching/client";
import { IconUsers } from "@/lib/icons";

const icon = <IconUsers width={18} height={18} />;

function useSectionStudents() {
  const [filter, setFilter] = usePlacementFilter();
  const ready = Boolean(filter.sessionId && filter.sectionId);
  const students = useOptions(
    useCallback(
      () => listAll((page) => peopleService("students").listStudents({ page, pageSize: 50, sessionYearId: filter.sessionId, classSectionId: filter.sectionId, status: "1", sort: "name" })),
      [filter.sessionId, filter.sectionId],
    ),
  );
  // In name order, as the numbering by name goes, whatever order the server sends.
  const rows = useMemo(() => (ready ? [...students.options].sort((a, b) => a.name.localeCompare(b.name)) : []), [ready, students.options]);
  return { filter, setFilter, ready, students, rows };
}

// ---------- Assign roll numbers ----------

/** Problems by student id: roll numbers must be whole numbers from 1 and not repeat in the section. */
export function rollProblems(values: Record<number, string>): Record<number, string> {
  const problems: Record<number, string> = {};
  const seen = new Map<number, number>();
  for (const [id, raw] of Object.entries(values)) {
    const text = raw.trim();
    if (!text) continue;
    const value = Number(text);
    if (!Number.isInteger(value) || value < 1 || value > 9999) {
      problems[Number(id)] = "Use a whole number from 1.";
      continue;
    }
    const other = seen.get(value);
    if (other !== undefined) {
      problems[Number(id)] = `Roll ${value} is used twice.`;
      problems[other] = `Roll ${value} is used twice.`;
    } else seen.set(value, Number(id));
  }
  return problems;
}

/** Roll numbers 1, 2, 3… in alphabetical order of name. */
export function numberByName(rows: Pick<StudentRow, "id" | "name">[]): Record<number, string> {
  return Object.fromEntries([...rows].sort((a, b) => a.name.localeCompare(b.name)).map((row, index) => [row.id, String(index + 1)]));
}

/** The student's saved details with a new roll number; the server's update needs the full record. */
export function withRoll(student: Student, roll: number | null): StudentInput {
  return {
    first_name: student.first_name,
    last_name: student.last_name,
    dob: student.dob,
    gender: student.gender,
    admission_no: student.admission_no,
    admission_date: student.admission_date,
    session_year_id: student.session_year_id,
    class_section_id: student.class_section_id,
    roll_number: roll,
    email: student.email,
    mobile: student.mobile,
    current_address: student.current_address,
    permanent_address: student.permanent_address,
    status: student.status,
  };
}

export function RollNumbersPage() {
  return (
    <ExtrasPage title="Assign roll numbers" description="Set the roll numbers of a section's students, by hand or in order of name." icon={icon}>
      <RollNumbersBody />
    </ExtrasPage>
  );
}

function RollNumbersBody() {
  const toast = useToast();
  const { filter, setFilter, ready, students, rows } = useSectionStudents();
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [failures, setFailures] = useState<string[]>([]);

  useEffect(() => {
    setDraft(Object.fromEntries(rows.map((row) => [row.id, row.roll_number ? String(row.roll_number) : ""])));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset when the list changes
  }, [students.options]);

  const problems = useMemo(() => rollProblems(draft), [draft]);
  const changed = rows.filter((row) => (draft[row.id] ?? "").trim() !== (row.roll_number ? String(row.roll_number) : ""));

  async function save() {
    if (saving || !changed.length || Object.keys(problems).length) return;
    setSaving(true);
    setFailures([]);
    const service = peopleService("students");
    const results = await settleLimited(
      changed.map((row) => async () => {
        const text = (draft[row.id] ?? "").trim();
        await service.updateStudent(row.id, withRoll(await service.getStudent(row.id), text ? Number(text) : null));
      }),
      4,
    );
    const failed = results.flatMap((result, index) => (result.ok ? [] : [`${changed[index].name}: ${errorMessage(result.error)}`]));
    setSaving(false);
    setFailures(failed);
    if (failed.length < changed.length) toast("success", `Saved ${changed.length - failed.length} roll number${changed.length - failed.length === 1 ? "" : "s"}.`);
    await students.reload();
  }

  const columns: Column<StudentRow>[] = [
    { key: "name", label: "Student", render: (row) => <strong>{row.name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no },
    { key: "current", label: "Current roll", render: (row) => row.roll_number ?? "—" },
    {
      key: "roll",
      label: "New roll",
      render: (row) => (
        <div>
          <input
            type="number"
            min={1}
            className="salary-input"
            aria-label={`Roll number for ${row.name}`}
            aria-invalid={Boolean(problems[row.id])}
            value={draft[row.id] ?? ""}
            onChange={(event) => setDraft((current) => ({ ...current, [row.id]: event.target.value }))}
          />
          {problems[row.id] ? <div className="field-error">{problems[row.id]}</div> : null}
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
      </div>
      <ErrorAlert error={students.error} onRetry={() => void students.reload()} />
      {failures.length ? (
        <div className="alert alert-danger" role="alert">
          {failures.length} couldn&apos;t be saved: {failures.join(" · ")}
        </div>
      ) : null}
      {ready ? (
        <>
          <div className="teach-toolbar">
            <button className="link-btn" type="button" disabled={!rows.length || saving} onClick={() => setDraft(numberByName(rows))}>
              Number in order of name
            </button>
            <button className="btn-pill btn-pill-green" type="button" disabled={saving || !changed.length || Object.keys(problems).length > 0} onClick={() => void save()}>
              {saving ? "Saving…" : `Save ${changed.length} change${changed.length === 1 ? "" : "s"}`}
            </button>
          </div>
          <div className="resource-card">
            <DataTable columns={columns} rows={rows} loading={students.loading} emptyText="No active students in this section." />
          </div>
        </>
      ) : (
        <div className="resource-card">
          <div className="empty-state">Choose a session, class and section.</div>
        </div>
      )}
    </>
  );
}

// ---------- Upload profile photos ----------

export function ProfilePhotosPage() {
  return (
    <ExtrasPage title="Upload profile photos" description="Add or replace student photos for a whole section. JPG, PNG or WebP up to 2 MB." icon={icon}>
      <ProfilePhotosBody />
    </ExtrasPage>
  );
}

type UploadState = { state: "uploading" } | { state: "done" } | { state: "failed"; message: string };

function ProfilePhotosBody() {
  const { filter, setFilter, ready, students, rows } = useSectionStudents();
  const [uploads, setUploads] = useState<Record<number, UploadState>>({});

  async function upload(row: StudentRow, file: File | undefined) {
    if (!file || uploads[row.id]?.state === "uploading") return;
    const problem = photoProblem(file);
    if (problem) {
      setUploads((current) => ({ ...current, [row.id]: { state: "failed", message: problem } }));
      return;
    }
    setUploads((current) => ({ ...current, [row.id]: { state: "uploading" } }));
    try {
      await peopleService("students").uploadPhoto("students", row.id, file);
      setUploads((current) => ({ ...current, [row.id]: { state: "done" } }));
    } catch (error) {
      setUploads((current) => ({ ...current, [row.id]: { state: "failed", message: errorMessage(error) } }));
    }
  }

  const columns: Column<StudentRow>[] = [
    { key: "roll", label: "Roll", render: (row) => row.roll_number ?? "—" },
    { key: "name", label: "Student", render: (row) => <strong>{row.name}</strong> },
    { key: "admission", label: "Admission no.", render: (row) => row.admission_no },
    {
      key: "photo",
      label: "Photo",
      render: (row) => {
        const status = uploads[row.id];
        return status?.state === "done" ? "Uploaded" : status?.state === "uploading" ? "Uploading…" : row.photo_url ? "Has a photo" : "No photo";
      },
    },
    {
      key: "file",
      label: "Upload",
      render: (row) => {
        const status = uploads[row.id];
        return (
          <div>
            <input type="file" accept={PHOTO_ACCEPT} aria-label={`Photo for ${row.name}`} disabled={status?.state === "uploading"} onChange={(event) => {
              void upload(row, event.target.files?.[0]);
              event.target.value = "";
            }} />
            {status?.state === "failed" ? <div className="field-error">{status.message}</div> : null}
          </div>
        );
      },
    },
  ];

  const done = Object.values(uploads).filter((item) => item.state === "done").length;
  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setUploads({}); }} />
      </div>
      <ErrorAlert error={students.error} onRetry={() => void students.reload()} />
      {done ? <div className="alert alert-success" role="status">{done} photo{done === 1 ? "" : "s"} uploaded.</div> : null}
      <div className="resource-card">
        {ready ? <DataTable columns={columns} rows={rows} loading={students.loading} emptyText="No active students in this section." /> : <div className="empty-state">Choose a session, class and section.</div>}
      </div>
    </>
  );
}
