"use client";

import dynamic from "next/dynamic";
import type { ComponentType, ReactNode } from "react";
import { ResourcePage } from "@/components/extras/ResourcePage";
import { ReportPage, SettingsPage } from "@/components/extras/SettingsPage";
import { EXTRA_PAGES } from "@/lib/extras/pages";
import { IconBell, IconBook, IconCalendar, IconChart, IconClasses, IconFees, IconGlobe, IconPackage, IconSettings, IconStaff, IconUsers } from "@/lib/icons";

function PageLoading() {
  return (
    <div className="acad-page" aria-busy="true" aria-label="Loading page">
      <div className="skeleton" style={{ height: 28, width: 240, marginBottom: 16 }} />
      <div className="skeleton" style={{ height: 220 }} />
    </div>
  );
}

/** Each screen is its own chunk, loaded when its menu item is opened. */
const lazy = (load: () => Promise<ComponentType>) => dynamic(load, { loading: PageLoading });

/** Pages with their own screens, by menu slug. */
const CUSTOM: Record<string, ComponentType> = {
  "staff-attendance": lazy(() => import("@/components/extras/StaffAttendance").then((mod) => mod.MarkStaffAttendance)),
  "todays-attendance": lazy(() => import("@/components/extras/StaffAttendance").then((mod) => mod.TodaysStaffAttendance)),
  "attendance-register": lazy(() => import("@/components/extras/StaffAttendance").then((mod) => mod.StaffAttendanceRegister)),
  "attendance-reports": lazy(() => import("@/components/extras/StaffAttendance").then((mod) => mod.StaffAttendanceReports)),
  "promote-students": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.PromoteStudents)),
  "transfer-student": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.TransferStudent)),
  "students-reset-password": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.ResetStudentPassword)),
  "assign-elective-subject": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.AssignElectives)),
  "add-bulk-data": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.ImportStudents)),
  "bulk-upload-staffs": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.ImportStaff)),
  "certificate-assign": lazy(() => import("@/components/operations/Documents").then((mod) => mod.CertificatesPage)),
  "bulk-id-cards": lazy(() => import("@/components/operations/Documents").then((mod) => mod.BulkIdCardsPage)),
  "student-id-card": lazy(() => import("@/components/extras/Tools").then((mod) => mod.StudentIdCard)),
  "staff-id-card": lazy(() => import("@/components/extras/Tools").then((mod) => mod.StaffIdCard)),
  "id-card-settings": lazy(() => import("@/components/extras/Tools").then((mod) => mod.IdCardSettingsPage)),
  "role-permission": lazy(() => import("@/components/extras/Tools").then((mod) => mod.RolePermission)),
  payroll: lazy(() => import("@/components/operations/Payroll").then((mod) => mod.PayrollProcessPage)),
  "payroll-runs": lazy(() => import("@/components/extras/Tools").then((mod) => mod.PayrollPage)),
  payslips: lazy(() => import("@/components/operations/Payroll").then((mod) => mod.PayslipsPage)),
  "payroll-reports": lazy(() => import("@/components/operations/Payroll").then((mod) => mod.PayrollReportsPage)),
  "salary-structure": lazy(() => import("@/components/operations/Payroll").then((mod) => mod.SalaryStructuresPage)),
  "monthly-salary": lazy(() => import("@/components/extras/Tools").then((mod) => mod.SalaryStructurePage)),
  "bulk-upload-teachers": lazy(() => import("@/components/extras/StudentTools").then((mod) => mod.ImportTeachers)),
  support: lazy(() => import("@/components/extras/Support").then((mod) => mod.SupportPage)),
  "third-party-api": lazy(() => import("@/components/extras/Support").then((mod) => mod.ThirdPartyPage)),
  "assign-roll-number": lazy(() => import("@/components/extras/StudentBulk").then((mod) => mod.RollNumbersPage)),
  "upload-profile-images": lazy(() => import("@/components/extras/StudentBulk").then((mod) => mod.ProfilePhotosPage)),
  "staff-leave": lazy(() => import("@/components/operations/Leave").then((mod) => mod.StaffLeavePage)),
  announcement: lazy(() => import("@/components/operations/Notices").then((mod) => mod.AnnouncementsPage)),
  notification: lazy(() => import("@/components/operations/Notices").then((mod) => mod.NotificationsPage)),
  messages: lazy(() => import("@/components/operations/Messages").then((mod) => mod.MessagesPage)),
};

const ICONS: Record<string, ReactNode> = {
  semester: <IconClasses width={18} height={18} />,
  stream: <IconClasses width={18} height={18} />,
  shift: <IconClasses width={18} height={18} />,
  syllabus: <IconBook width={18} height={18} />,
  "admission-inquiries": <IconUsers width={18} height={18} />,
  "online-classes": <IconCalendar width={18} height={18} />,
  "holiday-list": <IconCalendar width={18} height={18} />,
  "diary-category": <IconBook width={18} height={18} />,
  "student-diary": <IconBook width={18} height={18} />,
  notification: <IconBell width={18} height={18} />,
  announcement: <IconBell width={18} height={18} />,
  sliders: <IconGlobe width={18} height={18} />,
  gallery: <IconGlobe width={18} height={18} />,
  tasks: <IconStaff width={18} height={18} />,
  "qr-attendance-settings": <IconStaff width={18} height={18} />,
  plans: <IconPackage width={18} height={18} />,
  "contact-inquiry": <IconBell width={18} height={18} />,
  faqs: <IconGlobe width={18} height={18} />,
  "web-content": <IconGlobe width={18} height={18} />,
  addons: <IconPackage width={18} height={18} />,
};

/** The page for a menu slug served by the 0039 routes, or null if there isn't one. */
export function extraPageFor(slug: string): ReactNode | null {
  const Custom = CUSTOM[slug];
  if (Custom) return <Custom />;
  const config = EXTRA_PAGES[slug];
  if (!config) return null;
  const icon = ICONS[slug] ?? (config.kind === "settings" ? <IconSettings width={18} height={18} /> : config.kind === "report" ? <IconChart width={18} height={18} /> : /income|expense|payroll/.test(slug) ? <IconFees width={18} height={18} /> : <IconBook width={18} height={18} />);
  if (config.kind === "settings") return <SettingsPage config={config} icon={icon} />;
  if (config.kind === "report") return <ReportPage config={config} icon={icon} />;
  return <ResourcePage config={config} icon={icon} />;
}

export const EXTRA_SLUGS = [...Object.keys(CUSTOM), ...Object.keys(EXTRA_PAGES)];
