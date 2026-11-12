/**
 * Public "Request a demo" form.
 * Sent to POST /api/v1/public/demo-requests. The backend doesn't have this route yet (it has only
 * per-school contact inquiries), so until Nitish adds it the form reports that online requests
 * aren't available and offers email instead. It never claims a request was sent when it wasn't.
 */
import { api, apiErrorMessage } from "@/lib/api";

export type DemoRequest = { name: string; school_name: string; email: string; phone: string; city: string; students: string; message: string };

export const EMPTY_DEMO_REQUEST: DemoRequest = { name: "", school_name: "", email: "", phone: "", city: "", students: "", message: "" };

export function demoRequestProblems(input: DemoRequest): Partial<Record<keyof DemoRequest, string>> {
  const errors: Partial<Record<keyof DemoRequest, string>> = {};
  if (input.name.trim().length < 2) errors.name = "Enter your name.";
  if (input.school_name.trim().length < 2) errors.school_name = "Enter your school's name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.email.trim())) errors.email = "Enter a valid email address.";
  const digits = input.phone.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15) errors.phone = "Enter a phone number we can call.";
  if (input.students.trim() && !/^\d{1,6}$/.test(input.students.trim())) errors.students = "Enter a number, or leave it empty.";
  if (input.message.trim().length > 1000) errors.message = "Keep it under 1,000 characters.";
  return errors;
}

export type DemoOutcome = { state: "sent" } | { state: "unavailable" } | { state: "failed"; message: string };

export async function submitDemoRequest(input: DemoRequest): Promise<DemoOutcome> {
  const result = await api("/public/demo-requests", {
    method: "POST",
    body: JSON.stringify({
      name: input.name.trim(),
      school_name: input.school_name.trim(),
      email: input.email.trim(),
      phone: input.phone.trim(),
      city: input.city.trim() || null,
      students: input.students.trim() ? Number(input.students.trim()) : null,
      message: input.message.trim() || null,
    }),
  });
  if (result.ok) return { state: "sent" };
  // 404/405: the route isn't on the server yet.
  if (result.status === 404 || result.status === 405) return { state: "unavailable" };
  return { state: "failed", message: apiErrorMessage(result.data, "Your request couldn't be sent. Please try again.") };
}

/** A pre-filled email with the same details, for when online requests aren't available. */
export function demoMailto(to: string, input: DemoRequest): string {
  const body = [
    `Name: ${input.name}`,
    `School: ${input.school_name}`,
    `Email: ${input.email}`,
    `Phone: ${input.phone}`,
    input.city ? `City: ${input.city}` : "",
    input.students ? `Students: ${input.students}` : "",
    input.message ? `\n${input.message}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return `mailto:${to}?subject=${encodeURIComponent(`Demo request: ${input.school_name || "SchoolSarthi"}`)}&body=${encodeURIComponent(body)}`;
}
