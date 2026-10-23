/** Proposed RBAC modules — aligned with Super Admin contract (Nitish). */
export const PERMISSION_MODULES = [
  { key: "dashboard", label: "Dashboard" },
  { key: "school_management", label: "School Management" },
  { key: "student_management", label: "Student Management" },
  { key: "teacher_management", label: "Teacher Management" },
  { key: "attendance", label: "Attendance" },
  { key: "fees", label: "Fees" },
  { key: "exams", label: "Exams" },
  { key: "reports", label: "Reports" },
  { key: "settings", label: "Settings" },
] as const;

export type PermissionModuleKey = (typeof PERMISSION_MODULES)[number]["key"];

export const PERMISSION_ACTIONS = ["read", "write", "manage"] as const;
export type PermissionAction = (typeof PERMISSION_ACTIONS)[number];

export function permissionKey(module: PermissionModuleKey, action: PermissionAction): string {
  return `${module}.${action}`;
}

/** All permission keys for mock / contract fixtures. */
export const ALL_PERMISSION_KEYS: string[] = PERMISSION_MODULES.flatMap((m) =>
  PERMISSION_ACTIONS.map((a) => permissionKey(m.key, a)),
);
