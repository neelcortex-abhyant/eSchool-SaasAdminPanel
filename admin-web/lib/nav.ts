import type { ComponentType, SVGProps } from "react";
import {
  IconBell,
  IconBook,
  IconBuilding,
  IconCalendar,
  IconExam,
  IconFees,
  IconHome,
  IconPackage,
  IconSettings,
  IconSupport,
  IconUsers,
} from "@/lib/icons";

export type NavIcon = ComponentType<SVGProps<SVGSVGElement>>;

export type NavChild = {
  href?: string;
  label: string;
  children?: NavChild[];
};

export type NavItem = {
  href?: string;
  label: string;
  icon: NavIcon;
  children?: NavChild[];
  note?: string;
};

/** Maps to existing App Router pages only — no fake routes. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: IconHome },
  {
    label: "Institutions",
    icon: IconBuilding,
    children: [
      { href: "/schools", label: "Schools" },
      { href: "/packages", label: "Plans" },
      { href: "/addons", label: "Add-ons" },
    ],
  },
  {
    label: "Insights",
    icon: IconFees,
    children: [
      { href: "/reports", label: "Reports" },
      { href: "/audit-logs", label: "Audit logs" },
    ],
  },
  {
    label: "People",
    icon: IconUsers,
    children: [{ href: "/announcements", label: "Notifications" }],
  },
  { href: "/settings", label: "Settings", icon: IconSettings },
];

/** School Admin menu, matching the school admin product groups. */
export const SCHOOL_ADMIN_NAV: NavItem[] = [
  { href: "/school", label: "Dashboard", icon: IconHome },
  {
    label: "Academic management",
    icon: IconBook,
    children: [
      {
        label: "Academics",
        children: [
          { href: "/school/medium", label: "Medium" },
          { href: "/school/section", label: "Section" },
          { href: "/school/subject", label: "Subject" },
          { href: "/school/semester", label: "Semester" },
          { href: "/school/stream", label: "Stream" },
          { href: "/school/shift", label: "Shift" },
          { href: "/school/class", label: "Class" },
          { href: "/school/syllabus", label: "Syllabus" },
          { href: "/school/class-subject", label: "Class subject" },
          { href: "/school/class-section-teachers", label: "Class section teachers" },
        ],
      },
      {
        label: "Students",
        children: [
          { href: "/school/students-admission", label: "Students admission" },
          { href: "/school/admission-inquiries", label: "Admission inquiries" },
          { href: "/school/student-details", label: "Student details" },
          { href: "/school/add-bulk-data", label: "Add bulk data" },
          { href: "/school/guardian", label: "Guardian" },
          { href: "/school/assign-roll-number", label: "Assign roll number" },
          { href: "/school/upload-profile-images", label: "Upload profile images" },
          { href: "/school/assign-elective-subject", label: "Assign elective subject" },
          { href: "/school/transfer-student", label: "Transfer student" },
          { href: "/school/promote-students", label: "Promote students" },
          { href: "/school/students-reset-password", label: "Reset password" },
        ],
      },
      {
        label: "Teacher",
        children: [
          { href: "/school/manage-teachers", label: "Manage teachers" },
          { href: "/school/salary-structure", label: "Salary structure" },
          { href: "/school/bulk-upload-teachers", label: "Bulk upload teachers" },
        ],
      },
    ],
  },
  {
    label: "Academic calendar",
    icon: IconCalendar,
    children: [
      {
        label: "Timetable",
        children: [
          { href: "/school/create-timetable", label: "Create timetable" },
          { href: "/school/teacher-timetable", label: "Teacher timetable" },
          { href: "/school/online-classes", label: "Online classes" },
        ],
      },
      {
        label: "Attendance",
        children: [
          { href: "/school/student-attendance", label: "Student attendance" },
          { href: "/school/month-wise-attendance", label: "Month-wise attendance" },
        ],
      },
      { href: "/school/student-leave", label: "Student leave" },
      { href: "/school/holiday-list", label: "Holiday list" },
    ],
  },
  {
    label: "Exam & performance",
    icon: IconExam,
    children: [
      {
        label: "Assignment",
        children: [{ href: "/school/assignment-submission", label: "Assignment submission" }],
      },
      {
        label: "Offline exam",
        children: [
          { href: "/school/manage-offline-exam", label: "Manage offline exam" },
          { href: "/school/exam-timetable", label: "Exam timetable" },
          { href: "/school/track-exam-marks", label: "Track exam marks" },
          { href: "/school/offline-exam-result", label: "Offline exam result" },
          { href: "/school/exam-grade", label: "Exam grade" },
        ],
      },
      {
        label: "Online exam",
        children: [
          { href: "/school/manage-online-exam", label: "Manage online exam" },
          { href: "/school/manage-questions", label: "Manage questions" },
          { href: "/school/add-bulk-questions", label: "Add bulk questions" },
        ],
      },
    ],
  },
  {
    label: "Communication & media",
    icon: IconBell,
    children: [
      {
        label: "Student diary",
        children: [
          { href: "/school/diary-category", label: "Diary category" },
          { href: "/school/student-diary", label: "Student diary" },
        ],
      },
      { href: "/school/notification", label: "Notification" },
      { href: "/school/announcement", label: "Announcement" },
      { href: "/school/sliders", label: "Sliders" },
      { href: "/school/gallery", label: "Gallery" },
    ],
  },
  {
    label: "Personnel management",
    icon: IconUsers,
    children: [
      {
        label: "Staff management",
        children: [
          { href: "/school/role-permission", label: "Role permission" },
          { href: "/school/staff", label: "Staff" },
          { href: "/school/bulk-upload-staffs", label: "Bulk upload staff" },
        ],
      },
      {
        label: "Staff leave",
        children: [
          { href: "/school/staff-leave", label: "Staff leave" },
          { href: "/school/leave-report", label: "Leave report" },
        ],
      },
      { href: "/school/staff-attendance", label: "Staff attendance" },
      { href: "/school/todays-attendance", label: "Today's attendance" },
      { href: "/school/attendance-register", label: "Attendance register" },
      { href: "/school/attendance-reports", label: "Attendance reports" },
      { href: "/school/qr-attendance-settings", label: "QR attendance settings" },
      { href: "/school/tasks", label: "Tasks" },
    ],
  },
  {
    label: "Institutional finance",
    icon: IconFees,
    children: [
      {
        label: "Fees",
        children: [
          { href: "/school/fees-type", label: "Fees type" },
          { href: "/school/manage-fees", label: "Manage fees" },
          { href: "/school/fee-paid", label: "Fee paid" },
          { href: "/school/optional-fees-log", label: "Optional fees log" },
          { href: "/school/fee-transaction-logs", label: "Fee transaction logs" },
          { href: "/school/student-fees-discount", label: "Student fees discount" },
        ],
      },
      {
        label: "Expense",
        children: [
          { href: "/school/manage-expense-category", label: "Expense category" },
          { href: "/school/manage-expense", label: "Manage expense" },
        ],
      },
      {
        label: "Income",
        children: [
          { href: "/school/income-dashboard", label: "Income dashboard" },
          { href: "/school/manage-income-category", label: "Income category" },
          { href: "/school/manage-income", label: "Manage income" },
        ],
      },
      {
        label: "Payroll",
        children: [
          { href: "/school/payroll", label: "Payroll" },
          { href: "/school/payroll-settings", label: "Payroll settings" },
        ],
      },
    ],
  },
  {
    label: "Transportation module",
    icon: IconBuilding,
    children: [{ href: "/school/transportation", label: "Transportation" }],
  },
  {
    label: "Certificate & ID card",
    icon: IconExam,
    children: [
      { href: "/school/certificate-template", label: "Certificate template" },
      { href: "/school/certificate-assign", label: "Certificate assign" },
      { href: "/school/id-card-settings", label: "ID card settings" },
      { href: "/school/student-id-card", label: "Student ID card" },
      { href: "/school/staff-id-card", label: "Staff ID card" },
    ],
  },
  {
    label: "Reports",
    icon: IconSupport,
    children: [
      { href: "/school/student-reports", label: "Student reports" },
      { href: "/school/teacher-reports", label: "Teacher reports" },
      { href: "/school/staff-reports", label: "Staff reports" },
      { href: "/school/exam-reports", label: "Exam reports" },
      { href: "/school/expense-report", label: "Expense report" },
      { href: "/school/income-report", label: "Income report" },
      { href: "/school/financial-summary-report", label: "Financial summary" },
    ],
  },
  {
    label: "Subscription & plans",
    icon: IconPackage,
    children: [
      { href: "/school/subscription", label: "Subscription" },
      { href: "/school/plans", label: "Plans" },
      { href: "/school/addons", label: "Addons" },
    ],
  },
  {
    label: "Settings",
    icon: IconSettings,
    children: [
      {
        label: "System settings",
        children: [
          { href: "/settings", label: "General settings" },
          { href: "/school/session-year", label: "Session year" },
          { href: "/school/leave-settings", label: "Leave settings" },
          { href: "/school/additional-user-fields", label: "Additional user fields" },
          { href: "/school/whatsapp", label: "WhatsApp" },
          { href: "/school/meta-whatsapp-credentials", label: "Meta WhatsApp credentials" },
          { href: "/school/online-exam-terms", label: "Online exam terms" },
          { href: "/school/email-template", label: "Email template" },
          { href: "/school/payment-settings", label: "Payment settings" },
          { href: "/school/third-party-api", label: "Third party API" },
          { href: "/school/privacy-policy", label: "Privacy policy" },
          { href: "/school/terms-and-conditions", label: "Terms and conditions" },
          { href: "/school/refund-cancellation", label: "Refund cancellation" },
          { href: "/school/contact-us", label: "Contact us" },
          { href: "/school/about-us", label: "About us" },
        ],
      },
      {
        label: "Web settings",
        children: [
          { href: "/school/web-content", label: "Content" },
          { href: "/school/faqs", label: "FAQs" },
        ],
      },
      { href: "/school/database-backup", label: "Database backup" },
    ],
  },
  { href: "/school/contact-inquiry", label: "Contact inquiry", icon: IconBell },
  { href: "/school/support", label: "Support", icon: IconSupport },
];

function walkMenu(items: NavChild[] | undefined, slug: string): string | null {
  if (!items) return null;
  for (const item of items) {
    if (item.href === `/school/${slug}`) return item.label;
    const nested = walkMenu(item.children, slug);
    if (nested) return nested;
  }
  return null;
}

export function schoolMenuTitle(slug: string): string | null {
  for (const item of SCHOOL_ADMIN_NAV) {
    if (item.href === `/school/${slug}`) return item.label;
    const nested = walkMenu(item.children, slug);
    if (nested) return nested;
  }
  return null;
}

/** Extra links mapped only to existing pages (no fake routes). */
export const SECONDARY_NAV: NavItem[] = [
  { href: "/announcements", label: "Notifications", icon: IconBell },
  { href: "/packages", label: "Plans", icon: IconPackage },
  { href: "/reports", label: "Reports", icon: IconSupport },
];
