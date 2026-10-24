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
      { href: "/plans", label: "Plans" },
      { href: "/subscriptions", label: "Subscriptions" },
      { href: "/payments", label: "Payments" },
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
    children: [
      { href: "/school-admins", label: "School admins" },
      { href: "/announcements", label: "Notifications" },
    ],
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
          { href: "/school/academics/sessions", label: "Academic sessions" },
          { href: "/school/academics/classes", label: "Classes" },
          { href: "/school/academics/sections", label: "Sections" },
          { href: "/school/academics/subjects", label: "Subjects" },
          { href: "/school/academics/teacher-assignments", label: "Teacher assignments" },
          { href: "/school/academics/mediums", label: "Medium" },
          { href: "/school/semester", label: "Semester" },
          { href: "/school/stream", label: "Stream" },
          { href: "/school/shift", label: "Shift" },
          { href: "/school/syllabus", label: "Syllabus" },
        ],
      },
      {
        label: "Students",
        children: [
          { href: "/school/students/new", label: "Students admission" },
          { href: "/school/admission-inquiries", label: "Admission inquiries" },
          { href: "/school/students", label: "Student details" },
          { href: "/school/add-bulk-data", label: "Add bulk data" },
          { href: "/school/parents", label: "Parents and guardians" },
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
          { href: "/school/teachers", label: "Manage teachers" },
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
          { href: "/school/timetable", label: "Class timetable" },
          { href: "/school/timetable/teachers", label: "Teacher schedules" },
          { href: "/school/online-classes", label: "Online classes" },
        ],
      },
      {
        label: "Attendance",
        children: [
          { href: "/school/attendance", label: "Attendance dashboard" },
          { href: "/school/attendance/mark", label: "Mark attendance" },
          { href: "/school/attendance/history", label: "Student history" },
          { href: "/school/attendance/reports", label: "Monthly report" },
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
        label: "Homework & materials",
        children: [
          { href: "/school/homework", label: "Homework & assignments" },
          { href: "/school/study-materials", label: "Study materials" },
        ],
      },
      {
        label: "Offline exam",
        children: [
          { href: "/school/offline-exams", label: "Manage offline exams" },
          { href: "/school/offline-exams/timetable", label: "Exam timetable" },
          { href: "/school/exam-grade", label: "Exam grade" },
        ],
      },
      {
        label: "Online exam",
        children: [
          { href: "/school/online-exams", label: "Manage online exams" },
          { href: "/school/online-exams/question-bank", label: "Question bank" },
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
      { href: "/school/offline-exams", label: "Exam reports" },
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
