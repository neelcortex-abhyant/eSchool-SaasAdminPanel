import type { ComponentType, SVGProps } from "react";
import {
  IconBell,
  IconBuilding,
  IconClasses,
  IconFees,
  IconHome,
  IconPackage,
  IconSettings,
  IconSupport,
  IconUsers,
} from "@/lib/icons";

export type NavIcon = ComponentType<SVGProps<SVGSVGElement>>;

export type NavChild = {
  href: string;
  label: string;
};

export type NavItem = {
  href?: string;
  label: string;
  icon: NavIcon;
  children?: NavChild[];
};

/** Maps to existing App Router pages only — no fake routes. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: IconHome },
  {
    label: "Institutions",
    icon: IconBuilding,
    children: [
      { href: "/schools", label: "Schools" },
      { href: "/packages", label: "Packages" },
    ],
  },
  {
    label: "Academics",
    icon: IconClasses,
    children: [
      { href: "/students", label: "Students" },
      { href: "/classes", label: "Classes" },
      { href: "/subjects", label: "Subjects / Courses" },
      { href: "/attendances", label: "Attendance" },
      { href: "/exams", label: "Exams" },
    ],
  },
  {
    label: "Finance",
    icon: IconFees,
    children: [
      { href: "/fees", label: "Fees / Payments" },
      { href: "/expenses", label: "Expenses" },
    ],
  },
  {
    label: "People",
    icon: IconUsers,
    children: [
      { href: "/leaves", label: "Leaves" },
      { href: "/announcements", label: "Announcements" },
    ],
  },
  { href: "/settings", label: "Settings", icon: IconSettings },
];

/** Extra links mapped only to existing pages (no fake routes). */
export const SECONDARY_NAV: NavItem[] = [
  { href: "/announcements", label: "Notifications", icon: IconBell },
  { href: "/packages", label: "Subscriptions", icon: IconPackage },
  { href: "/settings", label: "Support", icon: IconSupport },
];
