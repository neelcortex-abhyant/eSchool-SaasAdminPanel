/** Transport checks shared by the sample client and the forms. */
import type { StopInput, VehicleInput } from "@/lib/ops/types";

export const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Seats left on a vehicle, or null when the route has no vehicle. */
export function seatsLeft(capacity: number | null, assigned: number): number | null {
  return capacity === null ? null : capacity - assigned;
}

/** The message shown when one more student would exceed the vehicle's seats, or "" if they fit. */
export function capacityProblem(capacity: number | null, assigned: number, adding = 1): string {
  if (capacity === null) return "";
  if (assigned + adding > capacity) return `The vehicle on this route has ${capacity} seats and ${assigned} are taken.`;
  return "";
}

export function vehicleProblems(input: VehicleInput, assignedStudents = 0): Record<string, string> {
  const errors: Record<string, string> = {};
  const reg = input.registration_no.trim();
  if (!reg) errors.registration_no = "Enter the registration number.";
  else if (!/^[A-Za-z0-9 -]{4,20}$/.test(reg)) errors.registration_no = "Use 4–20 letters, digits, spaces or hyphens.";
  if (!Number.isInteger(input.capacity) || input.capacity < 1 || input.capacity > 100) errors.capacity = "Capacity must be a whole number from 1 to 100.";
  else if (input.capacity < assignedStudents) errors.capacity = `${assignedStudents} students already ride this vehicle; capacity can't be lower than that.`;
  if (input.driver_id && input.helper_id && input.driver_id === input.helper_id) errors.helper_id = "The helper can't be the driver.";
  return errors;
}

export function stopProblems(input: StopInput, others: { id?: number; name: string; stop_order: number }[], selfId?: number): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!input.name.trim()) errors.name = "Enter the stop name.";
  else if (others.some((stop) => stop.id !== selfId && stop.name.trim().toLowerCase() === input.name.trim().toLowerCase())) errors.name = "This route already has a stop with that name.";
  if (!Number.isInteger(input.stop_order) || input.stop_order < 1) errors.stop_order = "Order must be 1 or more.";
  else if (others.some((stop) => stop.id !== selfId && stop.stop_order === input.stop_order)) errors.stop_order = `Stop ${input.stop_order} is already used on this route.`;
  if (input.pickup_time && !TIME.test(input.pickup_time)) errors.pickup_time = "Use 24-hour time, e.g. 07:15.";
  if (input.drop_time && !TIME.test(input.drop_time)) errors.drop_time = "Use 24-hour time, e.g. 14:40.";
  return errors;
}

/** Normalises "registration numbers" so KA 01 AB 1234 and ka01ab1234 count as the same. */
export function sameRegistration(a: string, b: string): boolean {
  return a.replace(/[\s-]/g, "").toUpperCase() === b.replace(/[\s-]/g, "").toUpperCase();
}
