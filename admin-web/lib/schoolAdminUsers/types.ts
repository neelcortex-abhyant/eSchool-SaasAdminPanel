export type SchoolAdminRole = {
  key: string;
  label: string;
  description?: string;
  permission_keys: string[];
  editable: boolean;
};

export type SchoolAdminPermission = {
  key: string;
  module: string;
  action: string;
  label: string;
};

export type SchoolAdminUser = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string | null;
  school_id: number;
  school_name: string;
  role_key: string;
  role_label: string;
  status: 0 | 1;
  created_at: string;
  last_login_at?: string | null;
  permission_keys: string[];
  /** Super Admin may edit roles/permissions for this user. */
  can_edit_roles: boolean;
};

export type SchoolAdminListResponse = {
  items: SchoolAdminUser[];
  total: number;
  page: number;
  page_size: number;
};

export type SchoolAdminListQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  school_id?: number | "";
  role_key?: string;
  status?: "" | "0" | "1";
  sort?: "name" | "created_at";
  order?: "asc" | "desc";
};

export type SchoolAdminFormValues = {
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  school_id: string;
  role_key: string;
  status: "0" | "1";
  send_invitation: boolean;
};

export type SchoolAdminFieldErrors = Partial<Record<keyof SchoolAdminFormValues, string>>;

export const EMPTY_SCHOOL_ADMIN_FORM: SchoolAdminFormValues = {
  first_name: "",
  last_name: "",
  email: "",
  mobile: "",
  school_id: "",
  role_key: "school_admin",
  status: "1",
  send_invitation: true,
};
