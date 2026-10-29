"use client";

import { useCallback, useEffect, useState } from "react";
import { SelectField } from "@/components/academics/Fields";
import { useOptions } from "@/components/academics/hooks";
import { classLabel, sectionLabel, sessionLabel, useClassesFor, useSectionsFor, useSessions } from "@/components/people/academicOptions";
import { academicsService, listAll } from "@/lib/academics";

/** Session, class and section as strings, the way form state keeps them. */
export type PlacementValue = { session_year_id: string; class_id: string; class_section_id: string };

export const EMPTY_PLACEMENT: PlacementValue = { session_year_id: "", class_id: "", class_section_id: "" };

/**
 * Dependent Session → Class → Section dropdowns. Picking a session clears the class and
 * section; picking a class clears the section. New records start in the current session.
 */
export function PlacementFields({
  value,
  onChange,
  errors = {},
  idPrefix,
  disabled,
}: {
  value: PlacementValue;
  onChange: (value: PlacementValue) => void;
  errors?: Record<string, string>;
  idPrefix: string;
  disabled?: boolean;
}) {
  const sessions = useSessions();
  const classes = useClassesFor(value.session_year_id ? Number(value.session_year_id) : "", true);
  const sections = useSectionsFor(value.class_id ? Number(value.class_id) : "");

  useEffect(() => {
    if (value.session_year_id) return;
    const current = sessions.options.find((row) => row.is_active);
    if (current) onChange({ ...value, session_year_id: String(current.id) });
  }, [sessions.options, value, onChange]);

  return (
    <>
      <SelectField
        id={`${idPrefix}-session`}
        label="Academic session"
        required
        placeholder="Choose a session"
        loading={sessions.loading}
        disabled={disabled}
        value={value.session_year_id}
        onChange={(v) => onChange({ session_year_id: v, class_id: "", class_section_id: "" })}
        options={sessions.options.map((row) => ({ value: String(row.id), label: sessionLabel(row) }))}
        error={errors.session_year_id}
      />
      <SelectField
        id={`${idPrefix}-class`}
        label="Class"
        required
        placeholder={value.session_year_id ? "Choose a class" : "Choose a session first"}
        loading={classes.loading}
        disabled={disabled || !value.session_year_id}
        value={value.class_id}
        onChange={(v) => onChange({ ...value, class_id: v, class_section_id: "" })}
        options={classes.options.filter((row) => row.status === 1 || String(row.id) === value.class_id).map((row) => ({ value: String(row.id), label: classLabel(row) }))}
        error={errors.class_id}
      />
      <SelectField
        id={`${idPrefix}-section`}
        label="Section"
        required
        placeholder={value.class_id ? "Choose a section" : "Choose a class first"}
        loading={sections.loading}
        disabled={disabled || !value.class_id}
        value={value.class_section_id}
        onChange={(v) => onChange({ ...value, class_section_id: v })}
        options={sections.options.filter((row) => row.status === 1 || String(row.id) === value.class_section_id).map((row) => ({ value: String(row.id), label: sectionLabel(row) }))}
        error={errors.class_section_id}
      />
    </>
  );
}

/** Subjects taught in a class (all subjects when no class is picked). */
export function useSubjects(classId: string) {
  const loader = useCallback(
    () => listAll((page) => academicsService("subjects").listSubjects({ page, pageSize: 50, classId: classId ? Number(classId) : "" })),
    [classId],
  );
  return useOptions(loader);
}

export function useTeachers() {
  return useOptions(useCallback(() => academicsService("assignments").listTeachers(), []));
}

/**
 * Teachers assigned to a subject in a section, from teacher assignments. The backend only
 * accepts a teacher who teaches that subject in that section, so the form suggests these first.
 */
export function useAssignedTeacherIds(sessionYearId: string, classSectionId: string, subjectId: string) {
  const loader = useCallback(
    () =>
      listAll((page) =>
        academicsService("assignments").listAssignments({
          page,
          pageSize: 50,
          sessionYearId: Number(sessionYearId),
          classSectionId: Number(classSectionId),
          subjectId: Number(subjectId),
        }),
      ).then((rows) => [...new Set(rows.map((row) => row.teacher_id))]),
    [sessionYearId, classSectionId, subjectId],
  );
  return useOptions(sessionYearId && classSectionId && subjectId ? loader : null);
}

/** Subject and teacher dropdowns for a placement; assigned teachers are listed first. */
export function SubjectTeacherFields({
  placement,
  subjectId,
  teacherId,
  onSubject,
  onTeacher,
  errors = {},
  idPrefix,
  disabled,
}: {
  placement: PlacementValue;
  subjectId: string;
  teacherId: string;
  onSubject: (value: string) => void;
  onTeacher: (value: string) => void;
  errors?: Record<string, string>;
  idPrefix: string;
  disabled?: boolean;
}) {
  const subjects = useSubjects(placement.class_id);
  const teachers = useTeachers();
  const assigned = useAssignedTeacherIds(placement.session_year_id, placement.class_section_id, subjectId);
  const assignedSet = new Set(assigned.options);
  const ordered = [...teachers.options].sort((a, b) => Number(assignedSet.has(b.id)) - Number(assignedSet.has(a.id)) || a.name.localeCompare(b.name));

  useEffect(() => {
    if (!teacherId && assigned.options.length === 1) onTeacher(String(assigned.options[0]));
  }, [assigned.options, teacherId, onTeacher]);

  return (
    <>
      <SelectField
        id={`${idPrefix}-subject`}
        label="Subject"
        required
        placeholder={placement.class_id ? "Choose a subject" : "Choose a class first"}
        loading={subjects.loading}
        disabled={disabled || !placement.class_id}
        value={subjectId}
        onChange={onSubject}
        options={subjects.options.map((row) => ({ value: String(row.id), label: row.code ? `${row.name} (${row.code})` : row.name }))}
        error={errors.subject_id}
      />
      <SelectField
        id={`${idPrefix}-teacher`}
        label="Teacher"
        required
        placeholder="Choose a teacher"
        loading={teachers.loading}
        disabled={disabled}
        value={teacherId}
        onChange={onTeacher}
        options={ordered.map((row) => ({ value: String(row.id), label: assignedSet.has(row.id) ? `${row.name} · teaches this subject here` : row.name }))}
        error={errors.teacher_user_id}
        hint={subjectId && placement.class_section_id && !assigned.loading && assigned.options.length === 0 ? "No teacher is assigned to this subject in this section yet. Add one under Academics → Teacher assignments." : undefined}
      />
    </>
  );
}

/** Session, class and section filters for list pages. Values are "" for "all". */
export function PlacementFilters({
  sessionId,
  classId,
  sectionId,
  onChange,
}: {
  sessionId: number | "";
  classId: number | "";
  sectionId: number | "";
  onChange: (next: { sessionId: number | ""; classId: number | ""; sectionId: number | "" }) => void;
}) {
  const sessions = useSessions();
  const classes = useClassesFor(sessionId);
  const sections = useSectionsFor(classId);
  return (
    <>
      <select aria-label="Filter by session" value={sessionId} onChange={(event) => onChange({ sessionId: event.target.value ? Number(event.target.value) : "", classId: "", sectionId: "" })}>
        <option value="">{sessions.loading ? "Loading sessions…" : "All sessions"}</option>
        {sessions.options.map((row) => (
          <option key={row.id} value={row.id}>
            {sessionLabel(row)}
          </option>
        ))}
      </select>
      <select aria-label="Filter by class" value={classId} onChange={(event) => onChange({ sessionId, classId: event.target.value ? Number(event.target.value) : "", sectionId: "" })}>
        <option value="">{classes.loading ? "Loading classes…" : "All classes"}</option>
        {classes.options.map((row) => (
          <option key={row.id} value={row.id}>
            {classLabel(row)}
          </option>
        ))}
      </select>
      <select aria-label="Filter by section" value={sectionId} disabled={!classId} onChange={(event) => onChange({ sessionId, classId, sectionId: event.target.value ? Number(event.target.value) : "" })}>
        <option value="">{classId ? "All sections" : "Choose a class first"}</option>
        {sections.options.map((row) => (
          <option key={row.id} value={row.id}>
            {sectionLabel(row)}
          </option>
        ))}
      </select>
    </>
  );
}

export type PlacementFilter = { sessionId: number | ""; classId: number | ""; sectionId: number | "" };

/** The current academic session's id once sessions load ("" until then). */
export function useCurrentSessionId(): number | "" {
  const sessions = useSessions();
  const current = sessions.options.find((row) => row.is_active) ?? sessions.options[0];
  return current ? current.id : "";
}

/** Filter state for Session/Class/Section that starts on the current session. */
export function usePlacementFilter(): [PlacementFilter, (next: PlacementFilter) => void] {
  const currentSessionId = useCurrentSessionId();
  const [chosen, setChosen] = useState<PlacementFilter | null>(null);
  return [chosen ?? { sessionId: currentSessionId, classId: "", sectionId: "" }, setChosen];
}
