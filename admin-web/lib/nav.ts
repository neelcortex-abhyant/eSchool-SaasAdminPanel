import type { ComponentType, SVGProps } from "react";
import {
  IconBell,
  IconBuilding,
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

/** School Admin sees only the school bound to their account. */
export const SCHOOL_ADMIN_NAV: NavItem[] = [
  { href: "/school", label: "My school", icon: IconHome },
  { href: "/settings", label: "Settings", icon: IconSettings },
];

/** Extra links mapped only to existing pages (no fake routes). */
export const SECONDARY_NAV: NavItem[] = [
  { href: "/announcements", label: "Notifications", icon: IconBell },
  { href: "/packages", label: "Plans", icon: IconPackage },
  { href: "/reports", label: "Reports", icon: IconSupport },
];
