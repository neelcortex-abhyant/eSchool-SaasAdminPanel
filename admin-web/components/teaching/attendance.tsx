"use client";

import { Chip, type ChipTone } from "@/components/teaching/Frame";
import { STATUS_LABEL } from "@/lib/teaching/attendance";
import type { AttendanceStatus } from "@/lib/teaching/types";

export const ATTENDANCE_TABS = [
  { href: "/school/attendance", label: "Dashboard" },
  { href: "/school/attendance/mark", label: "Mark attendance" },
  { href: "/school/attendance/history", label: "Student history" },
  { href: "/school/attendance/reports", label: "Monthly report" },
];

export const ATTENDANCE_LIVE_NOTE =
  "Connected to the school's server. It records Present, Absent and Late; Leave, corrections to saved attendance and locking a day aren't available on the server yet.";

export const STATUS_TONE: Record<AttendanceStatus, ChipTone> = { present: "green", absent: "red", late: "amber", leave: "blue" };

export const STATUS_SHORT: Record<AttendanceStatus, string> = { present: "P", absent: "A", late: "L", leave: "LV" };

export function AttendanceChip({ status }: { status: AttendanceStatus }) {
  return <Chip tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Chip>;
}

/** Today's date in the viewer's time zone, as YYYY-MM-DD. */
export function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

export function percentText(value: number, marked: number): string {
  return marked ? `${value}%` : "—";
}
