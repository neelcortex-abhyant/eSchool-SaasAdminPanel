/**
 * The signed-in school's own subscription payments and invoices.
 * Live only: /school-admin/school (the school's id), /schools/{id}/payments, /schools/{id}/invoices
 * and /schools/{id}/invoices/{invoice}/pdf. The server needs the settings permission for these.
 * Amounts arrive in paise.
 */
import { apiBlobUrl } from "@/lib/api";
import { allPages, get, num, optStr, str, type Raw } from "@/lib/teaching/client";

export type SchoolPayment = {
  id: number;
  amount: number;
  currency: string;
  gateway: string;
  reference: string | null;
  status: "successful" | "pending" | "failed" | "refunded";
  created_at: string | null;
  invoice_id: number | null;
};

export type SchoolInvoice = {
  id: number;
  invoice_number: string;
  issued_at: string;
  plan_name: string;
  cycle: string;
  period_start: string;
  period_end: string;
  total_amount: number;
  tax_amount: number | null;
  currency: string;
};

function statusOf(value: string): SchoolPayment["status"] {
  if (value === "captured") return "successful";
  if (value === "failed") return "failed";
  if (value === "refunded") return "refunded";
  return "pending";
}

export async function ownSchoolId(): Promise<number> {
  return num((await get("/school-admin/school", {}, "Unable to load your school.")).id);
}

export async function loadSchoolBilling(schoolId: number): Promise<{ payments: SchoolPayment[]; invoices: SchoolInvoice[] }> {
  const [payments, invoices] = await Promise.all([
    allPages(`/schools/${schoolId}/payments`, {}, "Unable to load payments."),
    allPages(`/schools/${schoolId}/invoices`, {}, "Unable to load invoices."),
  ]);
  return {
    payments: payments
      .map((row: Raw) => ({
        id: num(row.id),
        amount: num(row.amount) / 100,
        currency: str(row.currency, "INR"),
        gateway: str(row.gateway),
        reference: optStr(row.payment_id) ?? optStr(row.order_id),
        status: statusOf(str(row.status)),
        created_at: optStr(row.created_at),
        invoice_id: row.invoice_id === null || row.invoice_id === undefined ? null : num(row.invoice_id),
      }))
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")),
    invoices: invoices
      .map((row: Raw) => ({
        id: num(row.id),
        invoice_number: str(row.invoice_number),
        issued_at: str(row.issued_at),
        plan_name: str(row.plan_name),
        cycle: str(row.cycle),
        period_start: str(row.period_start).slice(0, 10),
        period_end: str(row.period_end).slice(0, 10),
        total_amount: num(row.total_amount) / 100,
        tax_amount: row.tax_amount === null || row.tax_amount === undefined ? null : num(row.tax_amount) / 100,
        currency: str(row.currency, "INR"),
      }))
      .sort((a, b) => b.issued_at.localeCompare(a.issued_at)),
  };
}

/** Downloads one invoice PDF with the sign-in token. */
export async function downloadSchoolInvoice(schoolId: number, invoice: SchoolInvoice): Promise<void> {
  const url = await apiBlobUrl(`/schools/${schoolId}/invoices/${invoice.id}/pdf`);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${invoice.invoice_number || `invoice-${invoice.id}`}.pdf`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
