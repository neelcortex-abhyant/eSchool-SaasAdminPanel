/**
 * Sample-data store for grading, fees and transport, kept in this browser's localStorage like
 * the other sample modules. Student, class, section and staff ids match the people and
 * academics samples, so names line up across pages.
 */
import seed from "@/lib/ops/mock-data.json";
import { AcademicApiError } from "@/lib/academics/errors";
import type { ConcessionKind, FeePayment, GradingScale, PaymentMethod, PaymentStatus, RecordStatus, TransportDirection, VehicleType } from "@/lib/ops/types";

const STORAGE_KEY = "ops-mock-db-v1";

/** Who a record is about, stored with it so sample records keep their names whatever data source is used. */
export type StudentRef = { student_id: number; student_name: string; admission_no: string; class_section_id: number; class_name: string; section_name: string };

export type StructureRow = {
  id: number;
  name: string;
  session_year_id: number;
  session_name: string;
  class_id: number;
  class_name: string;
  items: { fee_type_id: number; amount: number }[];
  installments: { id: number; name: string; due_date: string; amount: number }[];
  late_fee_per_day: number;
  status: RecordStatus;
};

export type PaymentRow = FeePayment & { class_section_id: number; idempotency_key: string; status: PaymentStatus; method: PaymentMethod };

type Db = {
  scales: GradingScale[];
  feeTypes: { id: number; name: string; category: string; description: string | null; status: RecordStatus }[];
  structures: StructureRow[];
  feeAssignments: ({ id: number; structure_id: number } & StudentRef)[];
  concessions: ({ id: number; structure_id: number; kind: ConcessionKind; value: number; reason: string } & StudentRef)[];
  payments: PaymentRow[];
  vehicles: { id: number; registration_no: string; vehicle_type: VehicleType; model: string | null; capacity: number; driver_id: number | null; driver_name: string | null; helper_id: number | null; helper_name: string | null; status: RecordStatus }[];
  routes: { id: number; name: string; description: string | null; vehicle_id: number | null; status: RecordStatus }[];
  stops: { id: number; route_id: number; name: string; stop_order: number; pickup_time: string | null; drop_time: string | null; landmark: string | null }[];
  transportAssignments: ({ id: number; route_id: number; stop_id: number; direction: TransportDirection; start_date: string; status: RecordStatus } & StudentRef)[];
};

const SEED = seed as unknown as Db;
let memory: Db | null = null;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function opsDb(): Db {
  if (memory) return memory;
  try {
    const saved = typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY);
    if (saved) memory = JSON.parse(saved) as Db;
  } catch {
    memory = null;
  }
  memory ??= clone(SEED);
  for (const key of Object.keys(SEED) as (keyof Db)[]) if (!memory[key]) (memory as Record<string, unknown>)[key] = clone(SEED[key]);
  return memory;
}

export function opsSave(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
  } catch {
    // Storage can be full or unavailable; the in-memory copy still works for this tab.
  }
}

/** Restores mock-data.json (used by tests and the "reset sample data" action). */
export function resetOpsMock(): void {
  memory = clone(SEED);
  opsSave();
}

export function later<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(clone(value)), 0));
}

export function nextId(rows: { id: number }[]): number {
  return rows.reduce((max, row) => Math.max(max, row.id), 0) + 1;
}

export function invalid(errors: Record<string, string>): never {
  throw new AcademicApiError(422, "Check the highlighted fields.", errors);
}

export function conflict(message: string, field?: string): never {
  throw new AcademicApiError(409, message, field ? { [field]: message } : {});
}

export function missing(label: string): never {
  throw new AcademicApiError(404, `${label} not found`);
}

export function today(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}
