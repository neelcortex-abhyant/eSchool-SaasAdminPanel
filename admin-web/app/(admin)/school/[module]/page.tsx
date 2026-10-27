"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import SchoolModulePage from "@/components/school-admin/SchoolModulePage";
import { extraPageFor } from "@/components/extras/registry";

/** Old menu slugs now served by dedicated pages. */
const MOVED: Record<string, string> = {
  medium: "/school/academics/mediums",
  class: "/school/academics/classes",
  section: "/school/academics/sections",
  subject: "/school/academics/subjects",
  "class-subject": "/school/academics/subjects",
  "class-section-teachers": "/school/academics/teacher-assignments",
  "create-timetable": "/school/timetable",
  "teacher-timetable": "/school/timetable/teachers",
  "student-attendance": "/school/attendance",
  "month-wise-attendance": "/school/attendance/reports",
  "assignment-submission": "/school/homework",
  "study-material": "/school/study-materials",
  "manage-online-exam": "/school/online-exams",
  "manage-questions": "/school/online-exams",
  "add-bulk-questions": "/school/online-exams",
  "manage-offline-exam": "/school/offline-exams",
  "exam-timetable": "/school/offline-exams/timetable",
  "track-exam-marks": "/school/offline-exams",
  "offline-exam-result": "/school/offline-exams",
  "exam-reports": "/school/offline-exams",
  "session-year": "/school/academics/sessions",
  "exam-grade": "/school/grading",
  "fees-type": "/school/fees/types",
  "fee-paid": "/school/fees/payments",
  "optional-fees-log": "/school/fees/payments",
  "fee-transaction-logs": "/school/fees/payments",
  "student-fees-discount": "/school/fees/assignments",
  transportation: "/school/transport/vehicles",
};

export default function SchoolModuleRoute() {
  const params = useParams<{ module: string }>();
  const router = useRouter();
  const moved = MOVED[params.module];

  useEffect(() => {
    if (moved) router.replace(moved);
  }, [moved, router]);

  if (moved) return null;
  return extraPageFor(params.module) ?? <SchoolModulePage moduleKey={params.module} />;
}
