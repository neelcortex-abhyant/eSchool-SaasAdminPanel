"use client";

import { useCallback } from "react";
import { useOptions } from "@/components/academics/hooks";
import { academicsService, listAll, type AcademicSession, type ClassSection, type SchoolClass } from "@/lib/academics";

const sessionService = academicsService("sessions");
const classService = academicsService("classes");
const sectionService = academicsService("sections");

export function classLabel(row: SchoolClass): string {
  return `${row.name}${row.medium_name ? ` · ${row.medium_name}` : ""}${row.status === 1 ? "" : " (inactive)"}`;
}

export function sessionLabel(row: AcademicSession): string {
  return `${row.name}${row.is_active ? " (current)" : ""}`;
}

export function sectionLabel(row: ClassSection): string {
  return `Section ${row.section_name}${row.status === 1 ? "" : " (inactive)"}`;
}

export function useSessions() {
  return useOptions(useCallback(() => listAll((page) => sessionService.listSessions({ page, pageSize: 50 })), []));
}

/** Classes that run in the session (including classes used in every session). Empty until a session is chosen when `requireSession` is set. */
export function useClassesFor(sessionYearId: number | "", requireSession = false) {
  const loader = useCallback(
    () => listAll((page) => classService.listClasses({ page, pageSize: 50, sessionYearId })),
    [sessionYearId],
  );
  return useOptions(requireSession && !sessionYearId ? null : loader);
}

/** Sections of one class. Empty until a class is chosen. */
export function useSectionsFor(classId: number | "") {
  const loader = useCallback(() => listAll((page) => sectionService.listSections({ page, pageSize: 50, classId })), [classId]);
  return useOptions(classId ? loader : null);
}
