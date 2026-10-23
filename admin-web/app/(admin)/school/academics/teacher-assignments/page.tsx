"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { AcademicPage } from "@/components/academics/AcademicPage";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useToast } from "@/components/academics/Toasts";
import { useDebounced, useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { academicsService, errorMessage, listAll, toId, type AcademicSession, type TeacherAssignment } from "@/lib/academics";
import { IconTeacher } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = academicsService("assignments");
const sessionService = academicsService("sessions");
const classService = academicsService("classes");
const sectionService = academicsService("sections");
const subjectService = academicsService("subjects");

type Editing = TeacherAssignment | "new" | null;

export default function TeacherAssignmentsPage() {
  const [editing, setEditing] = useState<Editing>(null);
  return (
    <AcademicPage
      feature="assignments"
      title="Teacher assignments"
      description="Choose who teaches each subject in every class section."
      icon={<IconTeacher width={18} height={18} />}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Assign teacher
        </button>
      }
    >
      <AssignmentsBody editing={editing} setEditing={setEditing} />
    </AcademicPage>
  );
}

/** Class options for one session: active classes in that session plus classes used in every session. */
function useClassOptions(sessionId: number | "") {
  return useOptions(
    useCallback(
      () => (sessionId ? listAll((p) => classService.listClasses({ page: p, pageSize: 50, sessionYearId: sessionId, status: "1" })) : Promise.resolve([])),
      [sessionId],
    ),
  );
}

function useSectionOptions(classId: number | "") {
  return useOptions(useCallback(() => (classId ? listAll((p) => sectionService.listSections({ page: p, pageSize: 50, classId, status: "1" })) : Promise.resolve([])), [classId]));
}

function useSubjectOptions(classId: number | "") {
  return useOptions(useCallback(() => (classId ? listAll((p) => subjectService.listSubjects({ page: p, pageSize: 50, classId, status: "1" })) : Promise.resolve([])), [classId]));
}

function sessionLabel(session: AcademicSession) {
  return `${session.name}${session.is_active ? " (active)" : ""}`;
}

function AssignmentsBody({ editing, setEditing }: { editing: Editing; setEditing: (value: Editing) => void }) {
  const toast = useToast();
  const sessions = useOptions(useCallback(() => listAll((p) => sessionService.listSessions({ page: p, pageSize: 50 })), []));
  const teachers = useOptions(useCallback(() => service.listTeachers(), []));

  const [sessionId, setSessionId] = useState<number | "">("");
  const [classId, setClassId] = useState<number | "">("");
  const [sectionId, setSectionId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [teacherId, setTeacherId] = useState<number | "">("");
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [page, setPage] = useState(1);
  const [removing, setRemoving] = useState<TeacherAssignment | null>(null);
  const [pending, setPending] = useState(false);

  // Start on the school's active session once sessions load.
  useEffect(() => {
    if (sessionId !== "" || sessions.options.length === 0) return;
    const active = sessions.options.find((session) => session.is_active) ?? sessions.options[0];
    setSessionId(active.id);
  }, [sessions.options, sessionId]);

  const classes = useClassOptions(sessionId);
  const sections = useSectionOptions(classId);
  const subjects = useSubjectOptions(classId);

  const loader = useCallback(
    () =>
      sessionId
        ? service.listAssignments({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: sessionId, classId, classSectionId: sectionId, subjectId, teacherId })
        : Promise.resolve({ items: [], total: 0, page: 1, page_size: PAGE_SIZE }),
    [page, search, sessionId, classId, sectionId, subjectId, teacherId],
  );
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || classId || sectionId || subjectId || teacherId);

  function chooseSession(value: string) {
    setSessionId(toId(value));
    setClassId("");
    setSectionId("");
    setSubjectId("");
    setPage(1);
  }

  function chooseClass(value: string) {
    setClassId(toId(value));
    setSectionId("");
    setSubjectId("");
    setPage(1);
  }

  async function remove() {
    if (!removing) return;
    setPending(true);
    try {
      await service.deleteAssignment(removing.id);
      toast("success", `${removing.teacher_name} removed from ${removing.subject_name} in ${removing.class_name} ${removing.section_name}.`);
      setRemoving(null);
      await reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to remove the assignment."));
    } finally {
      setPending(false);
    }
  }

  const columns = useMemo<Column<TeacherAssignment>[]>(
    () => [
      { key: "class", label: "Class", render: (row) => <strong>{`${row.class_name} ${row.section_name}`}</strong> },
      { key: "subject", label: "Subject", render: (row) => row.subject_name },
      { key: "teacher", label: "Teacher", render: (row) => row.teacher_name },
      { key: "session", label: "Session", render: (row) => row.session_name },
    ],
    [],
  );

  const noSessions = !sessions.loading && sessions.options.length === 0 && !sessions.error;

  return (
    <>
      <div className="school-filters">
        <select aria-label="Academic session" value={sessionId} onChange={(event) => chooseSession(event.target.value)}>
          {sessionId === "" ? <option value="">{sessions.loading ? "Loading sessions…" : "Choose a session"}</option> : null}
          {sessions.options.map((session) => (
            <option key={session.id} value={session.id}>
              {sessionLabel(session)}
            </option>
          ))}
        </select>
        <select aria-label="Filter by class" value={classId} disabled={!sessionId} onChange={(event) => chooseClass(event.target.value)}>
          <option value="">{classes.loading ? "Loading classes…" : "All classes"}</option>
          {classes.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name} · {row.medium_name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by section" value={sectionId} disabled={!classId} onChange={(event) => { setSectionId(toId(event.target.value)); setPage(1); }}>
          <option value="">{classId ? "All sections" : "Pick a class first"}</option>
          {sections.options.map((row) => (
            <option key={row.id} value={row.id}>
              Section {row.section_name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by subject" value={subjectId} disabled={!classId} onChange={(event) => { setSubjectId(toId(event.target.value)); setPage(1); }}>
          <option value="">{classId ? "All subjects" : "Pick a class first"}</option>
          {subjects.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by teacher" value={teacherId} onChange={(event) => { setTeacherId(toId(event.target.value)); setPage(1); }}>
          <option value="">All teachers</option>
          {teachers.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <input type="search" aria-label="Search assignments" placeholder="Search teacher or subject" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
      </div>

      <ErrorAlert error={sessions.error ?? error} onRetry={() => { void sessions.reload(); void reload(); }} />

      {noSessions ? (
        <div className="resource-card">
          <div className="empty-state">Add an academic session before assigning teachers.</div>
        </div>
      ) : !error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading || sessions.loading}
            emptyText={filtered ? "No assignments match these filters." : "No teachers are assigned in this session yet."}
            actions={(row) => (
              <>
                <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                  Edit
                </button>
                <button className="link-btn acad-danger-link" type="button" onClick={() => setRemoving(row)}>
                  Remove
                </button>
              </>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}

      {editing ? (
        <AssignmentForm
          assignment={editing === "new" ? null : editing}
          defaults={{ sessionId, classId, sectionId, subjectId }}
          sessions={sessions.options}
          teachers={teachers.options}
          teachersLoading={teachers.loading}
          onClose={() => setEditing(null)}
          onSaved={async (saved, created) => {
            setEditing(null);
            toast(
              "success",
              created
                ? `${saved.teacher_name} now teaches ${saved.subject_name} in ${saved.class_name} ${saved.section_name}.`
                : `Assignment for ${saved.subject_name} in ${saved.class_name} ${saved.section_name} updated.`,
            );
            await reload();
          }}
        />
      ) : null}

      {removing ? (
        <ConfirmDialog
          title="Remove this assignment?"
          body={`${removing.teacher_name} will no longer teach ${removing.subject_name} in ${removing.class_name} ${removing.section_name} for ${removing.session_name}.`}
          confirmLabel="Remove"
          tone="danger"
          pending={pending}
          onConfirm={() => void remove()}
          onCancel={() => setRemoving(null)}
        />
      ) : null}
    </>
  );
}

function AssignmentForm({
  assignment,
  defaults,
  sessions,
  teachers,
  teachersLoading,
  onClose,
  onSaved,
}: {
  assignment: TeacherAssignment | null;
  defaults: { sessionId: number | ""; classId: number | ""; sectionId: number | ""; subjectId: number | "" };
  sessions: AcademicSession[];
  teachers: { id: number; name: string; email: string }[];
  teachersLoading: boolean;
  onClose: () => void;
  onSaved: (saved: TeacherAssignment, created: boolean) => Promise<void>;
}) {
  const [sessionId, setSessionId] = useState<number | "">(assignment?.session_year_id ?? defaults.sessionId);
  const [classId, setClassId] = useState<number | "">(assignment?.class_id ?? defaults.classId);
  const [sectionId, setSectionId] = useState<number | "">(assignment?.class_section_id ?? defaults.sectionId);
  const [subjectId, setSubjectId] = useState<number | "">(assignment?.subject_id ?? defaults.subjectId);
  const [teacherId, setTeacherId] = useState<number | "">(assignment?.teacher_id ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();

  const classes = useClassOptions(sessionId);
  const sections = useSectionOptions(classId);
  const subjects = useSubjectOptions(classId);
  // Existing assignments in the chosen section, so taken subjects are marked before saving.
  const taken = useOptions(
    useCallback(
      () => (sessionId && sectionId ? listAll((p) => service.listAssignments({ page: p, pageSize: 50, sessionYearId: sessionId, classSectionId: sectionId })) : Promise.resolve([])),
      [sessionId, sectionId],
    ),
  );
  const takenBySubject = new Map(taken.options.filter((row) => row.id !== assignment?.id).map((row) => [row.subject_id, row.teacher_name]));

  function chooseSession(value: string) {
    setSessionId(toId(value));
    setClassId("");
    setSectionId("");
    setSubjectId("");
  }

  function chooseClass(value: string) {
    setClassId(toId(value));
    setSectionId("");
    setSubjectId("");
  }

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!sessionId) invalid.session_year_id = "Choose a session.";
    if (!classId) invalid.class_id = "Choose a class.";
    if (!sectionId) invalid.class_section_id = "Choose a section.";
    if (!subjectId) invalid.subject_id = "Choose a subject.";
    if (!teacherId) invalid.teacher_id = "Choose a teacher.";
    if (subjectId && takenBySubject.has(subjectId)) invalid.subject_id = `Already taught by ${takenBySubject.get(subjectId)} in this section.`;
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const body = { session_year_id: Number(sessionId), class_section_id: Number(sectionId), subject_id: Number(subjectId), teacher_id: Number(teacherId) };
    try {
      const saved = assignment ? await service.updateAssignment(assignment.id, body) : await service.createAssignment(body);
      await onSaved(saved, !assignment);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the assignment.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={assignment ? "Edit assignment" : "Assign teacher"}
      description="Each subject in a section can have one teacher per session."
      error={errors.formError}
      saving={saving}
      submitLabel={assignment ? "Save changes" : "Assign teacher"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <SelectField
        id="assign-session"
        label="Academic session"
        required
        placeholder="Choose a session"
        value={String(sessionId)}
        onChange={chooseSession}
        options={sessions.map((session) => ({ value: String(session.id), label: sessionLabel(session) }))}
        error={errors.fieldErrors.session_year_id}
      />
      <SelectField
        id="assign-class"
        label="Class"
        required
        placeholder={sessionId ? "Choose a class" : "Choose a session first"}
        disabled={!sessionId}
        loading={classes.loading}
        value={String(classId)}
        onChange={chooseClass}
        options={classes.options.map((row) => ({ value: String(row.id), label: `${row.name} · ${row.medium_name}` }))}
        error={errors.fieldErrors.class_id ?? (classes.error ? errorMessage(classes.error) : undefined)}
        hint={sessionId && !classes.loading && classes.options.length === 0 ? "No active classes in this session." : undefined}
      />
      <SelectField
        id="assign-section"
        label="Section"
        required
        placeholder={classId ? "Choose a section" : "Choose a class first"}
        disabled={!classId}
        loading={sections.loading}
        value={String(sectionId)}
        onChange={(value) => setSectionId(toId(value))}
        options={sections.options.map((row) => ({ value: String(row.id), label: `Section ${row.section_name}` }))}
        error={errors.fieldErrors.class_section_id ?? (sections.error ? errorMessage(sections.error) : undefined)}
        hint={classId && !sections.loading && sections.options.length === 0 ? "This class has no active sections." : undefined}
      />
      <SelectField
        id="assign-subject"
        label="Subject"
        required
        placeholder={classId ? "Choose a subject" : "Choose a class first"}
        disabled={!classId}
        loading={subjects.loading}
        value={String(subjectId)}
        onChange={(value) => setSubjectId(toId(value))}
        options={subjects.options.map((row) => {
          const holder = takenBySubject.get(row.id);
          const elective = row.classes.find((link) => link.class_id === classId)?.type === "Elective";
          return {
            value: String(row.id),
            label: `${row.name}${elective ? " (elective)" : ""}${holder ? ` · taught by ${holder}` : ""}`,
            disabled: Boolean(holder),
          };
        })}
        error={errors.fieldErrors.subject_id ?? (subjects.error ? errorMessage(subjects.error) : undefined)}
        hint={classId && !subjects.loading && subjects.options.length === 0 ? "No subjects are mapped to this class yet." : undefined}
      />
      <SelectField
        id="assign-teacher"
        label="Teacher"
        required
        span
        placeholder="Choose a teacher"
        loading={teachersLoading}
        value={String(teacherId)}
        onChange={(value) => setTeacherId(toId(value))}
        options={teachers.map((row) => ({ value: String(row.id), label: row.email ? `${row.name} · ${row.email}` : row.name }))}
        error={errors.fieldErrors.teacher_id}
      />
    </FormModal>
  );
}
