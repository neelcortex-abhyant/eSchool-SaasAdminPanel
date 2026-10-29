/**
 * Shapes for grading and report cards, student fees, and transport. The live routes are
 * proposed in backend/docs/FEES_TRANSPORT_GRADING_API_CONTRACT.md; the sample clients
 * follow the same shapes. The server takes the school from the session, so no record
 * carries a school_id.
 */
import type { Page } from "@/lib/academics/types";

export type { Page };

export type RecordStatus = 0 | 1;

// ---------- Grading ----------

export type GradeRange = {
  id?: number;
  grade: string;
  /** Inclusive lower and upper bounds, 0–100. */
  min_percent: number;
  max_percent: number;
  grade_point: number | null;
  remark: string | null;
  /** A student with this grade passes. */
  is_pass: boolean;
};

export type GradingScale = {
  id: number;
  name: string;
  description: string | null;
  /** Used for report cards and result grades when no other scale is chosen. */
  is_default: boolean;
  status: RecordStatus;
  ranges: GradeRange[];
};

export type GradingScaleInput = Omit<GradingScale, "id">;

// ---------- Report cards ----------

export type ReportSubject = {
  subject_name: string;
  marks_obtained: number | null;
  max_marks: number;
  status: "present" | "absent" | "withheld";
  grade: string | null;
  passed: boolean | null;
};

export type ReportExam = {
  exam_id: number;
  exam_name: string;
  exam_date: string | null;
  published: boolean;
  subjects: ReportSubject[];
  total_obtained: number;
  total_max: number;
  percentage: number;
  grade: string | null;
  passed: boolean;
  /** The report card the server stored for this exam, which has a PDF. */
  report_id?: number | null;
};

export type ReportCard = {
  student_id: number;
  student_name: string;
  admission_no: string;
  roll_number: number | null;
  class_name: string;
  section_name: string;
  session_year_id: number;
  session_name: string;
  guardian_name: string | null;
  exams: ReportExam[];
  overall: { total_obtained: number; total_max: number; percentage: number; grade: string | null; passed: boolean | null };
  /** "Promoted", "Not promoted" or null when the session's exams aren't all processed. */
  promotion: string | null;
  scale_name: string | null;
};

// ---------- Fees ----------

export type FeeCategory = "tuition" | "admission" | "examination" | "transport" | "other";

export const FEE_CATEGORIES: { value: FeeCategory; label: string }[] = [
  { value: "tuition", label: "Tuition" },
  { value: "admission", label: "Admission" },
  { value: "examination", label: "Examination" },
  { value: "transport", label: "Transport" },
  { value: "other", label: "Other" },
];

export type FeeType = {
  id: number;
  name: string;
  category: FeeCategory;
  description: string | null;
  status: RecordStatus;
};

export type FeeTypeInput = Omit<FeeType, "id">;

export type FeeItem = { fee_type_id: number; fee_type_name: string; category: FeeCategory; amount: number };

export type Installment = {
  id: number;
  name: string;
  /** YYYY-MM-DD */
  due_date: string;
  amount: number;
};

export type InstallmentInput = Omit<Installment, "id"> & { id?: number };

export type FeeStructure = {
  id: number;
  name: string;
  session_year_id: number;
  session_name: string;
  class_id: number;
  class_name: string;
  items: FeeItem[];
  installments: Installment[];
  /** Sum of the items; installments add up to this. */
  total: number;
  late_fee_per_day: number;
  status: RecordStatus;
};

export type FeeStructureInput = {
  name: string;
  session_year_id: number;
  class_id: number;
  items: { fee_type_id: number; amount: number }[];
  installments: InstallmentInput[];
  late_fee_per_day: number;
  status: RecordStatus;
};

export type FeeStructureQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  sessionYearId?: number | "";
  classId?: number | "";
  status?: "" | "0" | "1";
  sort?: "name" | "class" | "total";
  order?: "asc" | "desc";
};

/** A fee structure given to one student outside their class (e.g. transport). */
export type FeeAssignment = {
  id: number;
  structure_id: number;
  structure_name: string;
  student_id: number;
  student_name: string;
  admission_no: string;
};

export type ConcessionKind = "percent" | "amount";

/** A discount, concession or full exemption (100%) for one student on one structure. */
export type Concession = {
  id: number;
  student_id: number;
  student_name: string;
  structure_id: number;
  structure_name: string;
  kind: ConcessionKind;
  value: number;
  reason: string;
};

export type ConcessionInput = { student_id: number; structure_id: number; kind: ConcessionKind; value: number; reason: string };

export type PaymentMethod = "cash" | "cheque" | "bank_transfer" | "upi" | "card" | "online";

export const PAYMENT_METHODS: { value: PaymentMethod; label: string; manual: boolean }[] = [
  { value: "cash", label: "Cash", manual: true },
  { value: "cheque", label: "Cheque", manual: true },
  { value: "bank_transfer", label: "Bank transfer", manual: true },
  { value: "upi", label: "UPI (collected at the office)", manual: true },
  { value: "card", label: "Card (collected at the office)", manual: true },
  { value: "online", label: "Online payment link", manual: false },
];

/** success: recorded and counted. pending: waiting for the gateway/back office to confirm. */
export type PaymentStatus = "success" | "pending" | "failed" | "cancelled";

export type Allocation = { structure_id: number; installment_id: number; installment_name: string; amount: number };

export type FeePayment = {
  id: number;
  receipt_no: string | null;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string;
  section_name: string;
  amount: number;
  method: PaymentMethod;
  reference: string | null;
  remarks: string | null;
  status: PaymentStatus;
  paid_at: string;
  allocations: Allocation[];
  collected_by: string | null;
  /** Why the payment was cancelled, when it was. */
  cancel_reason?: string | null;
};

export type PaymentInput = {
  student_id: number;
  amount: number;
  method: PaymentMethod;
  reference: string | null;
  remarks: string | null;
  /** YYYY-MM-DD */
  paid_on: string;
  /** Sent as Idempotency-Key so a retried request can't record the payment twice. */
  idempotency_key: string;
};

export type PaymentQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  studentId?: number | "";
  classSectionId?: number | "";
  method?: PaymentMethod | "";
  status?: PaymentStatus | "";
  from?: string;
  to?: string;
};

/** One installment as it stands for one student. */
export type DueLine = {
  structure_id: number;
  structure_name: string;
  installment_id: number;
  installment_name: string;
  due_date: string;
  amount: number;
  concession: number;
  paid: number;
  balance: number;
  overdue: boolean;
};

export type StudentDues = {
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string;
  section_name: string;
  class_section_id: number;
  lines: DueLine[];
  total: number;
  concession: number;
  paid: number;
  balance: number;
  overdue: number;
  /** Online payments waiting for confirmation; not counted as paid. */
  pending: number;
};

export type OutstandingQuery = {
  sessionYearId?: number | "";
  classId?: number | "";
  classSectionId?: number | "";
  q?: string;
  dueBefore?: string;
  onlyOverdue?: boolean;
};

export type Receipt = {
  payment: FeePayment;
  school_name: string;
  session_name: string;
  /** Balance left after this payment, across all the student's fees. */
  balance_after: number;
  /** The server's PDF of the receipt, when it makes one. */
  pdf_path?: string | null;
};

export type CollectionReport = {
  from: string;
  to: string;
  payment_count: number;
  total_collected: number;
  by_method: Record<string, number>;
  items: { id: number; receipt_no: string | null; student_id: number; student_name: string; amount: number; method: string; paid_on: string }[];
};

// ---------- Transport ----------

export type VehicleType = "bus" | "van" | "car" | "other";

export const VEHICLE_TYPES: { value: VehicleType; label: string }[] = [
  { value: "bus", label: "Bus" },
  { value: "van", label: "Van" },
  { value: "car", label: "Car" },
  { value: "other", label: "Other" },
];

export type Vehicle = {
  id: number;
  registration_no: string;
  vehicle_type: VehicleType;
  model: string | null;
  capacity: number;
  driver_id: number | null;
  driver_name: string | null;
  helper_id: number | null;
  helper_name: string | null;
  status: RecordStatus;
  /** Students riding routes that use this vehicle. */
  assigned_students: number;
};

export type VehicleInput = {
  registration_no: string;
  vehicle_type: VehicleType;
  model: string | null;
  capacity: number;
  driver_id: number | null;
  helper_id: number | null;
  status: RecordStatus;
};

export type Stop = {
  id: number;
  route_id: number;
  name: string;
  stop_order: number;
  /** "HH:MM" or null */
  pickup_time: string | null;
  drop_time: string | null;
  landmark: string | null;
};

export type StopInput = { name: string; stop_order: number; pickup_time: string | null; drop_time: string | null; landmark: string | null };

export type Route = {
  id: number;
  name: string;
  description: string | null;
  vehicle_id: number | null;
  vehicle_label: string | null;
  capacity: number | null;
  assigned_students: number;
  status: RecordStatus;
  stops: Stop[];
};

export type RouteInput = { name: string; description: string | null; vehicle_id: number | null; status: RecordStatus };

export type TransportDirection = "both" | "pickup" | "drop";

export type TransportAssignment = {
  id: number;
  student_id: number;
  student_name: string;
  admission_no: string;
  class_name: string;
  section_name: string;
  route_id: number;
  route_name: string;
  stop_id: number;
  stop_name: string;
  direction: TransportDirection;
  /** YYYY-MM-DD */
  start_date: string;
  status: RecordStatus;
};

export type AssignmentInput = { student_id: number; route_id: number; stop_id: number; direction: TransportDirection; start_date: string; status: RecordStatus };

export type AssignmentQuery = { page?: number; pageSize?: number; q?: string; routeId?: number | ""; classSectionId?: number | "" };
