"use client";

import type { ComponentType, ReactNode } from "react";
import { ResourcePage } from "@/components/extras/ResourcePage";
import { ReportPage, SettingsPage } from "@/components/extras/SettingsPage";
import { MarkStaffAttendance, StaffAttendanceRegister, StaffAttendanceReports, TodaysStaffAttendance } from "@/components/extras/StaffAttendance";
import { AssignElectives, ImportStaff, ImportStudents, ImportTeachers, PromoteStudents, ResetStudentPassword, TransferStudent } from "@/components/extras/StudentTools";
import { CertificateAssign, IdCardSettingsPage, PayrollPage, RolePermission, SalaryStructurePage, StaffIdCard, StudentIdCard } from "@/components/extras/Tools";
import { SupportPage, ThirdPartyPage } from "@/components/extras/Support";
import { EXTRA_PAGES } from "@/lib/extras/pages";
import { IconBell, IconBook, IconCalendar, IconChart, IconClasses, IconFees, IconGlobe, IconPackage, IconSettings, IconStaff, IconUsers } from "@/lib/icons";

/** Pages with their own screens, by menu slug. */
const CUSTOM: Record<string, ComponentType> = {
  "staff-attendance": MarkStaffAttendance,
  "todays-attendance": TodaysStaffAttendance,
  "attendance-register": StaffAttendanceRegister,
  "attendance-reports": StaffAttendanceReports,
  "promote-students": PromoteStudents,
  "transfer-student": TransferStudent,
  "students-reset-password": ResetStudentPassword,
  "assign-elective-subject": AssignElectives,
  "add-bulk-data": ImportStudents,
  "bulk-upload-staffs": ImportStaff,
  "certificate-assign": CertificateAssign,
  "student-id-card": StudentIdCard,
  "staff-id-card": StaffIdCard,
  "id-card-settings": IdCardSettingsPage,
  "role-permission": RolePermission,
  payroll: PayrollPage,
  "salary-structure": SalaryStructurePage,
  "bulk-upload-teachers": ImportTeachers,
  support: SupportPage,
  "third-party-api": ThirdPartyPage,
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
