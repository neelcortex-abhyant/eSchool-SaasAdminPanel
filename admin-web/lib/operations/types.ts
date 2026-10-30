/** Shapes for the operations modules, matching backend/docs/OPERATIONS_MODULES_API_CONTRACT.md. */
import type { Page } from "@/lib/academics/types";

export type { Page };

// ---------- Bus tracking and transport attendance ----------

export type TripStatus = "scheduled" | "active" | "completed" | "cancelled";
export type TripDirection = "pickup" | "drop";

export type VehicleLocation = {
  vehicle_id: number;
  registration_no: string;
  route_id: number | null;
  route_name: string | null;
  driver_name: string | null;
  trip_id: number | null;
  trip_status: TripStatus | null;
  latitude: number;
  longitude: number;
  speed_kmph: number | null;
  heading: number | null;
  /** ISO time of the last GPS fix. */
  recorded_at: string;
};

export type Trip = {
  id: number;
  route_id: number;
  route_name: string;
  vehicle_id: number;
  registration_no: string;
  driver_name: string | null;
  helper_name: string | null;
  /** Pickup or drop; null when the server doesn't say. */
  direction: TripDirection | null;
  status: TripStatus;
  /** YYYY-MM-DD */
  trip_date: string;
  scheduled_start: string;
  started_at: string | null;
  ended_at: string | null;
  boarded: number;
  expected: number;
};

export type TripQuery = { page?: number; pageSize?: number; status?: TripStatus | ""; routeId?: number | ""; vehicleId?: number | ""; from?: string; to?: string };

export type BoardingStatus = "boarded" | "dropped" | "absent" | "pending";

export type TransportAttendance = {
  id: number;
  trip_id: number;
  trip_date: string;
  direction: TripDirection | null;
  route_id: number;
  route_name: string;
  student_id: number;
  student_name: string;
  admission_no: string;
  stop_name: string | null;
  status: BoardingStatus;
  boarded_at: string | null;
  dropped_at: string | null;
  /** Set when an admin changed the record. */
  corrected_by: string | null;
  note: string | null;
};

export type TransportAttendanceQuery = { page?: number; pageSize?: number; tripId?: number | ""; routeId?: number | ""; studentId?: number | ""; date?: string; status?: BoardingStatus | "" };

export type RouteAttendanceSummary = { route_id: number; route_name: string; trips: number; expected: number; boarded: number; absent: number; rate: number };

// ---------- Leave ----------

export type LeaveType = { key: string; name: string; days_per_year: number; applies_to: "staff" | "student" | "all"; /** Server id (GET /leave-types). */ id?: number };

export type LeaveStatus = 0 | 1 | 2;

export type LeaveRequest = {
  id: number;
  user_id: number;
  person_name: string;
  kind: "staff" | "teacher" | "student" | "unknown";
  leave_type: string | null;
  reason: string;
  from_date: string;
  to_date: string;
  days: number;
  status: LeaveStatus;
};

// ---------- Payroll ----------

export type SalaryLine = { name: string; amount: number };

export type SalaryStructure = {
  id: number;
  name: string;
  basic: number;
  allowances: SalaryLine[];
  deductions: SalaryLine[];
  /** Sum of basic and allowances. */
  gross: number;
  net: number;
  assigned: number;
};

export type SalaryStructureInput = { name: string; basic: number; allowances: SalaryLine[]; deductions: SalaryLine[] };

export type SalaryAssignment = { staff_id: number; structure_id: number; structure_name: string; effective_from: string };

export type PayrollStatus = "processed" | "pending" | "failed";

export type PayrollPreviewLine = {
  staff_id: number;
  name: string;
  department: string;
  structure_name: string | null;
  basic: number;
  allowances: number;
  deductions: number;
  /** Deduction for unpaid leave/absence, worked out by the server. */
  attendance_adjustment: number;
  working_days: number;
  paid_days: number;
  net: number;
  eligible: boolean;
  /** Why someone isn't eligible, e.g. no salary structure. */
  problem: string | null;
};

export type PayrollPreview = { month: string; lines: PayrollPreviewLine[]; total_net: number; already_processed: boolean };

export type Payslip = {
  id: number;
  month: string;
  staff_id: number;
  name: string;
  employee_code: string;
  department: string;
  designation: string;
  basic: number;
  allowances: SalaryLine[];
  deductions: SalaryLine[];
  attendance_adjustment: number;
  working_days: number;
  paid_days: number;
  gross: number;
  net: number;
  status: PayrollStatus;
  processed_at: string | null;
  failure_reason: string | null;
};

export type PayslipQuery = { page?: number; pageSize?: number; month?: string; staffId?: number | ""; status?: PayrollStatus | ""; department?: string };

// ---------- Announcements and notifications ----------

export type Audience = "all" | "students" | "parents" | "teachers" | "staff";

export const AUDIENCES: { value: Audience; label: string }[] = [
  { value: "all", label: "Everyone" },
  { value: "students", label: "Students" },
  { value: "parents", label: "Parents" },
  { value: "teachers", label: "Teachers" },
  { value: "staff", label: "Staff" },
];

export type NoticeStatus = "draft" | "scheduled" | "published";

export type Announcement = {
  /** Server id once published; drafts kept in this browser have a negative id. */
  id: number;
  title: string;
  description: string;
  session_year_id: number | null;
  audience: Audience[];
  publish_at: string | null;
  status: NoticeStatus;
  created_at: string | null;
};

export type AnnouncementInput = { title: string; description: string; session_year_id: number; audience: Audience[]; publish_at: string | null; draft: boolean };

export type DeliveryStatus = "queued" | "sent" | "partial" | "failed";

export type NotificationRecord = {
  id: number;
  title: string;
  body: string;
  audience: Audience[];
  created_at: string | null;
  delivery: DeliveryStatus;
  recipients: number;
  delivered: number;
  failed: number;
  failure_reason: string | null;
};

// ---------- Teacher–parent messages ----------

export type Participant = { user_id: number; name: string; role: "teacher" | "parent" | "school_admin" };

export type Attachment = { name: string; url: string; size: number | null; content_type: string | null };

export type Message = {
  id: number;
  conversation_id: number;
  sender: Participant;
  body: string;
  attachments: Attachment[];
  sent_at: string;
  /** Hidden by a moderator; the text is kept from everyone but moderators. */
  hidden: boolean;
};

export type Conversation = {
  id: number;
  subject: string;
  student_id: number;
  student_name: string;
  class_name: string;
  teacher: Participant;
  parent: Participant;
  last_message: string;
  last_message_at: string;
  unread: number;
  flagged: boolean;
};

export type ConversationQuery = { q?: string; unreadOnly?: boolean; flaggedOnly?: boolean };

/** What the signed-in admin may do with conversations, as the server says. */
export type MessagingPolicy = { can_view: boolean; can_send: boolean; can_moderate: boolean; poll_seconds: number };
