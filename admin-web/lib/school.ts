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

export function schoolStatusLabel(status: number | null | undefined): string {
  return status === 1 ? "Active" : "Inactive";
}

export function loadSchools() {
  return api<SchoolList>("/super-admin/schools?page=1&page_size=100");
}

export function loadSchool(id: string) {
  return api<SchoolRecord>(`/super-admin/schools/${id}`);
}

export function loadSchoolAdmins(id: string) {
  return api<{ items: SchoolAdmin[] }>(`/super-admin/schools/${id}/admins`);
}
