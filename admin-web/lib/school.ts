/**
 * School service for Super Admin pages: every /super-admin/schools call goes through here, so
 * pages never build these URLs themselves. Each function returns the api() result
 * ({ ok, status, data }); pages turn errors into messages with apiErrorMessage().
 */
import { api } from "@/lib/api";

export type SchoolAdmin = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string | null;
  status: number;
};

export type SchoolRecord = {
  id: number;
  name: string | null;
  code: string | null;
  status: number | null;
  address: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  postal_code?: string | null;
  support_email: string | null;
  support_phone: string | null;
  tagline: string | null;
  website?: string | null;
  school_type?: string | null;
  domain: string | null;
  logo?: string | null;
  installed: number | null;
  admin_id: number | null;
  v1_admin_id?: string | null;
  database_name: string | null;
  provisioned_at?: string | null;
  deleted_at?: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SchoolList = {
  items: SchoolRecord[];
  total: number;
  page: number;
  page_size: number;
};

export function schoolStatusLabel(status: number | null | undefined, installed?: number | null): string {
  if (status === 1) return "Active";
  if (installed === 0) return "Pending approval";
  return "Inactive";
}

export type SchoolListQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | "0" | "1";
  sort?: "name" | "created_at";
  order?: "asc" | "desc";
};

export function loadSchools(query: SchoolListQuery = {}) {
  const sortKey = query.sort ?? "created_at";
  const sortOrder = query.order ?? "desc";
  const params = new URLSearchParams({
    page: String(query.page ?? 1),
    page_size: String(query.pageSize ?? 20),
    sort: sortOrder === "desc" ? `-${sortKey}` : sortKey,
  });
  const search = query.q?.trim();
  if (search) params.set("q", search);
  if (query.status === "0" || query.status === "1") params.set("status", query.status);
  return api<SchoolList>(`/super-admin/schools?${params.toString()}`);
}

export function loadSchool(id: string) {
  return api<SchoolRecord>(`/super-admin/schools/${id}`);
}

export function loadSchoolAdmins(id: string) {
  return api<{ items: SchoolAdmin[] }>(`/super-admin/schools/${id}/admins`);
}

/** Status actions on Nitish's routes: POST /super-admin/schools/{id}/{action}. */
export type SchoolAction = "activate" | "suspend" | "deactivate" | "provision";

/** POST /super-admin/schools (create) or PATCH /super-admin/schools/{id} (edit). */
export function saveSchool(body: Record<string, unknown>, id?: string | number) {
  return api<SchoolRecord>(id ? `/super-admin/schools/${id}` : "/super-admin/schools", { method: id ? "PATCH" : "POST", body: JSON.stringify(body) });
}

export function setSchoolStatus(id: string | number, action: SchoolAction) {
  return api<SchoolRecord>(`/super-admin/schools/${id}/${action}`, { method: "POST" });
}

export function deleteSchool(id: string | number) {
  return api(`/super-admin/schools/${id}`, { method: "DELETE" });
}

export type NewSchoolAdmin = { email: string; password: string; first_name: string; last_name: string; mobile: string };

/** POST /super-admin/schools/{id}/admins: the school's first admin, created with the school. */
export function addSchoolAdmin(id: string | number, admin: NewSchoolAdmin) {
  return api(`/super-admin/schools/${id}/admins`, { method: "POST", body: JSON.stringify(admin) });
}
