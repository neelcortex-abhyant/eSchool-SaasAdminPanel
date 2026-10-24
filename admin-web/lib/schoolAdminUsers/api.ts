/**
 * Super Admin → School admin users.
 *
 * Live calls use the RBAC routes on the backend (Nitish's /super-admin API):
 *   GET  /super-admin/school-admins                      list across schools
 *   GET  /super-admin/roles, /super-admin/permissions    catalog
 *   POST /super-admin/schools/{school}/admins            create (no password → invitation email)
 *   GET/PATCH /super-admin/schools/{school}/admins/{id}  detail, name and mobile
 *   PATCH .../admins/{id}/status, .../admins/{id}/roles  status, role
 *
 * NEXT_PUBLIC_SCHOOL_ADMIN_API_MODE: "live", "mock", or unset ("auto": live, falling back to
 * mock data when the backend doesn't have these routes yet).
 *
 * The backend grants permissions through roles only, so a live admin's permission_keys are the
 * role's permissions, mapped onto the module × read/write/manage matrix used by the UI.
 */
import { api, type ApiResult } from "@/lib/api";
import { loadSchool } from "@/lib/school";
import { PERMISSION_MODULES, permissionKey } from "@/lib/schoolAdminUsers/constants";
import {
  mockCreateSchoolAdmin,
  mockGetSchoolAdmin,
  mockListPermissions,
  mockListRoles,
  mockListSchoolAdmins,
  mockSetSchoolAdminStatus,
  mockUpdateSchoolAdmin,
  mockUpdateSchoolAdminRoles,
} from "@/lib/schoolAdminUsers/mockStore";
import type {
  SchoolAdminListQuery,
  SchoolAdminListResponse,
  SchoolAdminPermission,
  SchoolAdminRole,
  SchoolAdminUser,
} from "@/lib/schoolAdminUsers/types";

type ApiMode = "mock" | "live" | "auto";

const MODE_KEY = "school_admin_api_mode";

function configuredMode(): ApiMode {
  const env = process.env.NEXT_PUBLIC_SCHOOL_ADMIN_API_MODE;
  if (env === "mock" || env === "live") return env;
  return "auto";
}

function resolvedMode(): ApiMode {
  if (typeof window === "undefined") return configuredMode();
  if (configuredMode() !== "auto") return configuredMode();
  const cached = window.sessionStorage.getItem(MODE_KEY);
  if (cached === "mock" || cached === "live") return cached;
  return "auto";
}

function cacheMode(mode: "mock" | "live"): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(MODE_KEY, mode);
}

function useMock(): boolean {
  return resolvedMode() === "mock";
}

/** In auto mode a 404 on the list route means the backend has no RBAC routes yet. */
function fallBackToMock(status: number): boolean {
  if (status === 404 && configuredMode() === "auto") {
    cacheMode("mock");
    return true;
  }
  return false;
}

// ---------- backend shapes ----------

type BackendAdmin = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  mobile: string | null;
  role: string;
  school_id: number | null;
  school_name?: string | null;
  status: number;
  roles?: string[];
  permissions?: string[];
  created_at?: string | null;
  invite_sent?: boolean | null;
};

type BackendRole = { key: string; label: string; permissions: string[] };
type BackendPermission = { key: string; label: string };

// Backend permission prefix → UI matrix module.
const MODULE_BY_PREFIX: Record<string, (typeof PERMISSION_MODULES)[number]["key"]> = {
  dashboard: "dashboard",
  school: "school_management",
  students: "student_management",
  teachers: "teacher_management",
  attendance: "attendance",
  fees: "fees",
  exams: "exams",
  reports: "reports",
  settings: "settings",
};

/** "students.manage" → read, write and manage on Student Management; "reports.view" → read only. */
function matrixKeys(permissions: string[] = []): string[] {
  const keys = new Set<string>();
  for (const permission of permissions) {
    const [prefix, action] = permission.split(".");
    const module = MODULE_BY_PREFIX[prefix];
    if (!module) continue;
    keys.add(permissionKey(module, "read"));
    if (action === "manage") {
      keys.add(permissionKey(module, "write"));
      keys.add(permissionKey(module, "manage"));
    }
  }
  return [...keys];
}

// Role labels from the last catalog load, so rows can show "Academic Admin" instead of a key.
let roleLabels: Record<string, string> = {};
// School of each admin seen in a list, so detail routes don't have to search every school.
const schoolOfAdmin = new Map<string, number>();

function toUser(row: BackendAdmin, schoolName?: string | null): SchoolAdminUser {
  const roleKey = row.roles?.[0] ?? (row.role === "school_admin" ? "school_admin" : row.role);
  if (row.school_id) schoolOfAdmin.set(row.id, row.school_id);
  return {
    id: row.id,
    first_name: row.first_name,
    last_name: row.last_name,
    email: row.email,
    mobile: row.mobile,
    school_id: row.school_id ?? 0,
    school_name: row.school_name || schoolName || (row.school_id ? `School #${row.school_id}` : "—"),
    role_key: roleKey,
    role_label: roleLabels[roleKey] || roleKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    status: row.status === 1 ? 1 : 0,
    created_at: row.created_at || new Date(0).toISOString(),
    last_login_at: null,
    permission_keys: matrixKeys(row.permissions),
    can_edit_roles: true,
  };
}

function fail<T>(status: number, data: unknown): ApiResult<T> {
  return { ok: false, status, data: data as T };
}

function listParams(query: SchoolAdminListQuery): string {
  const sortKey = query.sort ?? "created_at";
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
    sort: (query.order ?? "desc") === "desc" ? `-${sortKey}` : sortKey,
  });
  const search = query.q?.trim();
  if (search) params.set("q", search);
  if (typeof query.school_id === "number" && query.school_id > 0) params.set("school_id", String(query.school_id));
  if (query.role_key) params.set("role", query.role_key);
  if (query.status === "0" || query.status === "1") params.set("status", query.status);
  return params.toString();
}

/** The admin's school: remembered from a list, or found by paging the cross-school list. */
async function schoolIdFor(adminId: string): Promise<number | null> {
  const known = schoolOfAdmin.get(adminId);
  if (known) return known;
  for (let page = 1; page <= 20; page += 1) {
    const result = await api<{ items: BackendAdmin[]; total: number }>(`/super-admin/school-admins?page=${page}&page_size=100`);
    if (!result.ok) return null;
    const items = result.data.items || [];
    for (const row of items) if (row.school_id) schoolOfAdmin.set(row.id, row.school_id);
    const found = schoolOfAdmin.get(adminId);
    if (found) return found;
    if (items.length === 0 || page * 100 >= result.data.total) return null;
  }
  return null;
}

async function adminPath(adminId: string): Promise<string | null> {
  const schoolId = await schoolIdFor(adminId);
  return schoolId ? `/super-admin/schools/${schoolId}/admins/${adminId}` : null;
}

async function ensureRoleLabels(): Promise<void> {
  if (Object.keys(roleLabels).length) return;
  const result = await api<{ items: BackendRole[] }>("/super-admin/roles");
  if (result.ok) roleLabels = Object.fromEntries((result.data.items || []).map((role) => [role.key, role.label]));
}

// ---------- service ----------

export async function listSchoolAdminUsers(query: SchoolAdminListQuery): Promise<ApiResult<SchoolAdminListResponse>> {
  if (useMock()) return { ok: true, status: 200, data: mockListSchoolAdmins(query) };
  await ensureRoleLabels();
  const result = await api<{ items: BackendAdmin[]; total: number; page: number; page_size: number }>(
    `/super-admin/school-admins?${listParams(query)}`,
  );
  if (!result.ok) {
    if (fallBackToMock(result.status)) return { ok: true, status: 200, data: mockListSchoolAdmins(query) };
    return fail(result.status, result.data);
  }
  cacheMode("live");
  return {
    ok: true,
    status: 200,
    data: { ...result.data, items: (result.data.items || []).map((row) => toUser(row)) },
  };
}

export async function getSchoolAdminUser(id: string): Promise<ApiResult<SchoolAdminUser>> {
  if (useMock()) {
    const row = mockGetSchoolAdmin(id);
    return row ? { ok: true, status: 200, data: row } : fail(404, {});
  }
  await ensureRoleLabels();
  const path = await adminPath(id);
  if (!path) {
    if (configuredMode() === "auto") {
      const mock = mockGetSchoolAdmin(id);
      if (mock) return { ok: true, status: 200, data: mock };
    }
    return fail(404, { detail: "School admin not found" });
  }
  const result = await api<BackendAdmin>(path);
  return result.ok ? { ok: true, status: 200, data: toUser(result.data) } : fail(result.status, result.data);
}

export async function createSchoolAdminUser(body: {
  first_name: string;
  last_name: string;
  email: string;
  mobile: string | null;
  school_id: number;
  role_key: string;
  status: 0 | 1;
  send_invitation: boolean;
}): Promise<ApiResult<SchoolAdminUser>> {
  if (useMock()) {
    const school = await loadSchool(String(body.school_id));
    const schoolName = school.ok && school.data.name ? school.data.name : `School #${body.school_id}`;
    return { ok: true, status: 201, data: mockCreateSchoolAdmin({ ...body, school_name: schoolName }) };
  }
  // Without a password the backend emails an invitation link. Without an invitation, the
  // account gets a random password and the admin can be invited or reset later.
  const result = await api<BackendAdmin>(`/super-admin/schools/${body.school_id}/admins`, {
    method: "POST",
    body: JSON.stringify({
      email: body.email,
      first_name: body.first_name,
      last_name: body.last_name,
      mobile: body.mobile,
      roles: [body.role_key],
      status: body.status,
      ...(body.send_invitation ? {} : { password: `${crypto.randomUUID().replace(/-/g, "")}Aa1!` }),
    }),
  });
  if (!result.ok) return fail(result.status, result.data);
  await ensureRoleLabels();
  return { ok: true, status: 201, data: toUser(result.data) };
}

export async function updateSchoolAdminUser(
  id: string,
  body: {
    first_name?: string;
    last_name?: string;
    mobile?: string | null;
    role_key?: string;
    status?: 0 | 1;
    school_id?: number;
  },
): Promise<ApiResult<SchoolAdminUser>> {
  if (useMock()) {
    const updated = mockUpdateSchoolAdmin(id, body);
    return updated ? { ok: true, status: 200, data: updated } : fail(404, {});
  }
  const path = await adminPath(id);
  if (!path) return fail(404, { detail: "School admin not found" });
  // An admin stays in their school; the backend has no route to move them.
  const patch = await api<BackendAdmin>(path, {
    method: "PATCH",
    body: JSON.stringify({ first_name: body.first_name, last_name: body.last_name, mobile: body.mobile }),
  });
  if (!patch.ok) return fail(patch.status, patch.data);
  let latest = patch.data;
  if (body.status === 0 || body.status === 1) {
    const status = await api<BackendAdmin>(`${path}/status`, { method: "PATCH", body: JSON.stringify({ status: body.status }) });
    if (!status.ok) return fail(status.status, status.data);
    latest = status.data;
  }
  if (body.role_key && body.role_key !== (latest.roles?.[0] ?? latest.role)) {
    const roles = await api<BackendAdmin>(`${path}/roles`, { method: "PATCH", body: JSON.stringify({ roles: [body.role_key] }) });
    if (!roles.ok) return fail(roles.status, roles.data);
    latest = roles.data;
  }
  await ensureRoleLabels();
  return { ok: true, status: 200, data: toUser(latest) };
}

export async function setSchoolAdminStatus(id: string, status: 0 | 1): Promise<ApiResult<SchoolAdminUser>> {
  if (useMock()) {
    const updated = mockSetSchoolAdminStatus(id, status);
    return updated ? { ok: true, status: 200, data: updated } : fail(404, {});
  }
  const path = await adminPath(id);
  if (!path) return fail(404, { detail: "School admin not found" });
  const result = await api<BackendAdmin>(`${path}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
  return result.ok ? { ok: true, status: 200, data: toUser(result.data) } : fail(result.status, result.data);
}

export async function loadSchoolAdminRoles(): Promise<ApiResult<{ items: SchoolAdminRole[] }>> {
  if (useMock()) return { ok: true, status: 200, data: { items: mockListRoles() } };
  const result = await api<{ items: BackendRole[] }>("/super-admin/roles");
  if (!result.ok) {
    if (fallBackToMock(result.status)) return { ok: true, status: 200, data: { items: mockListRoles() } };
    return fail(result.status, result.data);
  }
  const roles = result.data.items || [];
  roleLabels = Object.fromEntries(roles.map((role) => [role.key, role.label]));
  return {
    ok: true,
    status: 200,
    // Permissions come from the role on the backend, so roles aren't custom-editable.
    data: { items: roles.map((role) => ({ key: role.key, label: role.label, permission_keys: matrixKeys(role.permissions), editable: false })) },
  };
}

export async function loadSchoolAdminPermissions(): Promise<ApiResult<{ items: SchoolAdminPermission[] }>> {
  if (useMock()) return { ok: true, status: 200, data: { items: mockListPermissions() } };
  const result = await api<{ items: BackendPermission[] }>("/super-admin/permissions");
  if (!result.ok) {
    if (fallBackToMock(result.status)) return { ok: true, status: 200, data: { items: mockListPermissions() } };
    return fail(result.status, result.data);
  }
  const items: SchoolAdminPermission[] = [];
  for (const permission of result.data.items || []) {
    const [prefix] = permission.key.split(".");
    const module = MODULE_BY_PREFIX[prefix];
    if (!module) continue;
    for (const key of matrixKeys([permission.key])) {
      const action = key.split(".")[1];
      items.push({ key, module, action, label: `${permission.label}: ${action}` });
    }
  }
  return { ok: true, status: 200, data: { items } };
}

export async function updateSchoolAdminRoles(
  id: string,
  body: { role_key: string; permission_keys: string[] },
): Promise<ApiResult<SchoolAdminUser>> {
  if (useMock()) {
    const updated = mockUpdateSchoolAdminRoles(id, body.role_key, body.permission_keys);
    return updated ? { ok: true, status: 200, data: updated } : fail(404, {});
  }
  // The backend stores roles only; the permissions follow from the role.
  const path = await adminPath(id);
  if (!path) return fail(404, { detail: "School admin not found" });
  const result = await api<BackendAdmin>(`${path}/roles`, { method: "PATCH", body: JSON.stringify({ roles: [body.role_key] }) });
  if (!result.ok) return fail(result.status, result.data);
  await ensureRoleLabels();
  return { ok: true, status: 200, data: toUser(result.data) };
}

/**
 * Emails a new password-setup link through /super-admin/schools/{school}/admins/{id}/invite.
 * Earlier unused links stop working. The server reports invite_sent=false when mail isn't
 * configured or delivery failed, which is returned as an error so the page doesn't claim it went.
 */
export async function sendSchoolAdminPasswordReset(id: string, email: string): Promise<ApiResult<{ message: string }>> {
  if (useMock()) return { ok: true, status: 200, data: { message: "Password reset link sent." } };
  void email;
  const path = await adminPath(id);
  if (!path) return fail(404, { detail: "School admin not found" });
  const result = await api<BackendAdmin>(`${path}/invite`, { method: "POST" });
  if (!result.ok) return fail(result.status, result.data);
  if (result.data.invite_sent === false) {
    return fail(503, { detail: "The server couldn't send the email (mail isn't set up or delivery failed). Try again later." });
  }
  return { ok: true, status: 200, data: { message: "Password-setup link sent." } };
}

export function schoolAdminDisplayName(user: Pick<SchoolAdminUser, "first_name" | "last_name">): string {
  return `${user.first_name} ${user.last_name}`.trim() || "—";
}

export function schoolAdminStatusLabel(status: number): string {
  return status === 1 ? "Active" : "Inactive";
}

/** True when the role decides the permissions (live backend); the matrix then follows the role. */
export function permissionsFollowRole(): boolean {
  return !useMock();
}
