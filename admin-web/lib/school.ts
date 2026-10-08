import { adminApi } from "@/lib/adminApi";

export type SchoolAdmin = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string | null;
};

export type SchoolCounts = {
  students: number;
  classes: number;
  subjects: number;
  exams: number;
  fees: number;
  announcements: number;
};

export type SchoolRecord = {
  id: number;
  name: string | null;
  code: string | null;
  status: number | null;
  address: string | null;
  support_email: string | null;
  support_phone: string | null;
  tagline: string | null;
  domain: string | null;
  installed: number | null;
  admin_id: number | null;
  database_name: string | null;
  created_at: string | null;
  updated_at: string | null;
  admin?: SchoolAdmin | null;
  counts?: SchoolCounts;
};

export function schoolStatusLabel(status: number | null | undefined): string {
  return status === 1 ? "Active" : "Inactive";
}

export async function loadSchool(id: string) {
  return adminApi<{ data?: SchoolRecord; detail?: string }>(`/schools/${id}`);
}
