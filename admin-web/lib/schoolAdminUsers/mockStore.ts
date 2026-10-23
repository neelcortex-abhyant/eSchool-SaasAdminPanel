import { ALL_PERMISSION_KEYS, permissionKey } from "@/lib/schoolAdminUsers/constants";
import type {
  SchoolAdminListQuery,
  SchoolAdminListResponse,
  SchoolAdminPermission,
  SchoolAdminRole,
  SchoolAdminUser,
} from "@/lib/schoolAdminUsers/types";

const MOCK_ROLES: SchoolAdminRole[] = [
  {
    key: "school_admin",
    label: "School Admin",
    description: "Full access to school operations.",
    permission_keys: [...ALL_PERMISSION_KEYS],
    editable: true,
  },
  {
    key: "school_admin_limited",
    label: "Limited Admin",
    description: "Dashboard, students, and attendance without financial modules.",
    permission_keys: ALL_PERMISSION_KEYS.filter(
      (k) =>
        k.startsWith("dashboard.") ||
        k.startsWith("student_management.") ||
        k.startsWith("attendance.") ||
        k.startsWith("reports.read"),
    ),
    editable: true,
  },
  {
    key: "school_admin_readonly",
    label: "Read-only Admin",
    description: "View-only access across modules.",
    permission_keys: ALL_PERMISSION_KEYS.filter((k) => k.endsWith(".read")),
    editable: false,
  },
];

function permissionsCatalog(): SchoolAdminPermission[] {
  return ALL_PERMISSION_KEYS.map((key) => {
    const [module, action] = key.split(".");
    const moduleLabel = module.replace(/_/g, " ");
    return {
      key,
      module,
      action,
      label: `${moduleLabel} — ${action}`,
    };
  });
}

let seq = 3;
const store: SchoolAdminUser[] = [
  {
    id: "a1000001-0000-4000-8000-000000000001",
    first_name: "Priya",
    last_name: "Sharma",
    email: "priya.admin@demoa.test",
    mobile: "+919876543210",
    school_id: 1,
    school_name: "Demo School A",
    role_key: "school_admin",
    role_label: "School Admin",
    status: 1,
    created_at: "2025-08-12T10:30:00.000Z",
    last_login_at: "2026-10-18T06:12:00.000Z",
    permission_keys: MOCK_ROLES[0].permission_keys,
    can_edit_roles: true,
  },
  {
    id: "a1000001-0000-4000-8000-000000000002",
    first_name: "Rahul",
    last_name: "Mehta",
    email: "rahul.ops@demob.test",
    mobile: "+919811223344",
    school_id: 2,
    school_name: "Demo School B",
    role_key: "school_admin_limited",
    role_label: "Limited Admin",
    status: 1,
    created_at: "2026-01-05T14:00:00.000Z",
    last_login_at: null,
    permission_keys: MOCK_ROLES[1].permission_keys,
    can_edit_roles: true,
  },
  {
    id: "a1000001-0000-4000-8000-000000000003",
    first_name: "Inactive",
    last_name: "User",
    email: "inactive.admin@demoa.test",
    mobile: null,
    school_id: 1,
    school_name: "Demo School A",
    role_key: "school_admin_readonly",
    role_label: "Read-only Admin",
    status: 0,
    created_at: "2026-03-20T09:15:00.000Z",
    last_login_at: "2026-04-01T11:00:00.000Z",
    permission_keys: MOCK_ROLES[2].permission_keys,
    can_edit_roles: false,
  },
];

function fullName(u: SchoolAdminUser): string {
  return `${u.first_name} ${u.last_name}`.trim().toLowerCase();
}

function applyQuery(items: SchoolAdminUser[], query: SchoolAdminListQuery): SchoolAdminUser[] {
  let rows = [...items];
  const q = query.q?.trim().toLowerCase();
  if (q) {
    rows = rows.filter((u) => fullName(u).includes(q) || u.email.toLowerCase().includes(q));
  }
  if (typeof query.school_id === "number" && query.school_id > 0) {
    rows = rows.filter((u) => u.school_id === query.school_id);
  }
  if (query.role_key) {
    rows = rows.filter((u) => u.role_key === query.role_key);
  }
  if (query.status === "0" || query.status === "1") {
    rows = rows.filter((u) => u.status === Number(query.status));
  }
  const sort = query.sort ?? "created_at";
  const order = query.order ?? "desc";
  rows.sort((a, b) => {
    let cmp = 0;
    if (sort === "name") cmp = fullName(a).localeCompare(fullName(b));
    else cmp = a.created_at.localeCompare(b.created_at);
    return order === "asc" ? cmp : -cmp;
  });
  return rows;
}

export function mockListRoles(): SchoolAdminRole[] {
  return MOCK_ROLES.map((r) => ({ ...r, permission_keys: [...r.permission_keys] }));
}

export function mockListPermissions(): SchoolAdminPermission[] {
  return permissionsCatalog();
}

export function mockListSchoolAdmins(query: SchoolAdminListQuery): SchoolAdminListResponse {
  const page = query.page ?? 1;
  const pageSize = query.pageSize ?? 20;
  const filtered = applyQuery(store, query);
  const start = (page - 1) * pageSize;
  const items = filtered.slice(start, start + pageSize);
  return { items, total: filtered.length, page, page_size: pageSize };
}

export function mockGetSchoolAdmin(id: string): SchoolAdminUser | null {
  const row = store.find((u) => u.id === id);
  return row ? { ...row, permission_keys: [...row.permission_keys] } : null;
}

export function mockCreateSchoolAdmin(input: {
  first_name: string;
  last_name: string;
  email: string;
  mobile: string | null;
  school_id: number;
  school_name: string;
  role_key: string;
  status: 0 | 1;
}): SchoolAdminUser {
  const role = MOCK_ROLES.find((r) => r.key === input.role_key) ?? MOCK_ROLES[0];
  const id = `a1000001-0000-4000-8000-${String(seq++).padStart(12, "0")}`;
  const user: SchoolAdminUser = {
    id,
    first_name: input.first_name,
    last_name: input.last_name,
    email: input.email,
    mobile: input.mobile,
    school_id: input.school_id,
    school_name: input.school_name,
    role_key: role.key,
    role_label: role.label,
    status: input.status,
    created_at: new Date().toISOString(),
    last_login_at: null,
    permission_keys: [...role.permission_keys],
    can_edit_roles: role.editable,
  };
  store.unshift(user);
  return { ...user };
}

export function mockUpdateSchoolAdmin(
  id: string,
  patch: Partial<Pick<SchoolAdminUser, "first_name" | "last_name" | "mobile" | "role_key" | "status">>,
): SchoolAdminUser | null {
  const idx = store.findIndex((u) => u.id === id);
  if (idx < 0) return null;
  const current = store[idx];
  let role = MOCK_ROLES.find((r) => r.key === (patch.role_key ?? current.role_key)) ?? MOCK_ROLES[0];
  if (patch.role_key && patch.role_key !== current.role_key) {
    role = MOCK_ROLES.find((r) => r.key === patch.role_key) ?? role;
  }
  const next: SchoolAdminUser = {
    ...current,
    ...patch,
    role_key: role.key,
    role_label: role.label,
    permission_keys: patch.role_key ? [...role.permission_keys] : [...current.permission_keys],
    can_edit_roles: role.editable,
  };
  store[idx] = next;
  return { ...next, permission_keys: [...next.permission_keys] };
}

export function mockSetSchoolAdminStatus(id: string, status: 0 | 1): SchoolAdminUser | null {
  return mockUpdateSchoolAdmin(id, { status });
}

export function mockUpdateSchoolAdminRoles(id: string, role_key: string, permission_keys: string[]): SchoolAdminUser | null {
  const idx = store.findIndex((u) => u.id === id);
  if (idx < 0) return null;
  const role = MOCK_ROLES.find((r) => r.key === role_key) ?? MOCK_ROLES[0];
  const next: SchoolAdminUser = {
    ...store[idx],
    role_key: role.key,
    role_label: role.label,
    permission_keys: [...permission_keys],
    can_edit_roles: role.editable,
  };
  store[idx] = next;
  return { ...next, permission_keys: [...next.permission_keys] };
}

/** Seed extra permission for demos when role is custom. */
export function mockDefaultPermissionsForRole(roleKey: string): string[] {
  const role = MOCK_ROLES.find((r) => r.key === roleKey);
  return role ? [...role.permission_keys] : [permissionKey("dashboard", "read")];
}
