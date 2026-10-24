import { api, apiUrl, getAccessToken, type ApiResult } from "@/lib/api";
import { money } from "@/lib/billing";

export type PaymentStatus = "successful" | "pending" | "failed" | "refunded";

export type PaymentInvoice = {
  /** Server invoice id, used for the PDF download (absent on sample rows). */
  id?: number;
  number: string;
  date: string;
};

export type PaymentTransaction = {
  id: string;
  school_id: number;
  school_name: string;
  school_code: string | null;
  plan_name: string;
  amount: number;
  currency: string;
  gateway: string;
  gateway_reference: string | null;
  status: PaymentStatus;
  created_at: string;
  paid_at: string | null;
  invoice: PaymentInvoice | null;
};

export type PaymentList = {
  items: PaymentTransaction[];
  total: number;
  page: number;
  page_size: number;
  source: "api" | "sample";
};

export type PaymentSummary = {
  successful_amount: number;
  currency: string;
  successful_count: number;
  pending_count: number;
  failed_count: number;
  source: "api" | "sample";
};

export type PaymentQuery = {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: "" | PaymentStatus;
  gateway?: string;
  from?: string;
  to?: string;
  sort?: "created_at" | "-created_at";
  schoolId?: number;
};

const SAMPLE: PaymentTransaction[] = [
  row("TXN-SAMPLE-1001", 9001, "North Ridge School", "NRD01", "Starter", 1200, "successful", "2026-09-02", "2026-09-02", "Sample checkout", "ref-sample-1001", "INV-SAMPLE-1001"),
  row("TXN-SAMPLE-1002", 9001, "North Ridge School", "NRD01", "Starter", 1200, "pending", "2026-10-01", null, "Sample checkout", null, null),
  row("TXN-SAMPLE-1003", 9002, "Harbour View School", "HBR02", "Growth", 4800, "successful", "2026-08-14", "2026-08-14", "Sample transfer", "ref-sample-1003", "INV-SAMPLE-1003"),
  row("TXN-SAMPLE-1004", 9002, "Harbour View School", "HBR02", "Growth", 4800, "failed", "2026-09-18", null, "Sample transfer", "ref-sample-1004", null),
  row("TXN-SAMPLE-1005", 9003, "Maple Lane School", "MPL03", "Starter", 1200, "successful", "2026-07-09", "2026-07-09", "Sample checkout", "ref-sample-1005", null),
  row("TXN-SAMPLE-1006", 9003, "Maple Lane School", "MPL03", "Campus", 9600, "pending", "2026-10-11", null, "Sample checkout", null, null),
  row("TXN-SAMPLE-1007", 9004, "Riverbend School", "RVB04", "Growth", 4800, "successful", "2026-06-21", "2026-06-22", "Sample transfer", "ref-sample-1007", "INV-SAMPLE-1007"),
  row("TXN-SAMPLE-1008", 9004, "Riverbend School", "RVB04", "Growth", 4800, "failed", "2026-10-04", null, "Sample checkout", "ref-sample-1008", null),
  row("TXN-SAMPLE-1009", 9005, "Cedar Park School", "CDR05", "Campus", 9600, "successful", "2026-05-03", "2026-05-03", "Sample checkout", "ref-sample-1009", "INV-SAMPLE-1009"),
  row("TXN-SAMPLE-1010", 9005, "Cedar Park School", "CDR05", "Campus", 9600, "pending", "2026-09-28", null, "Sample transfer", null, null),
  row("TXN-SAMPLE-1011", 9006, "Lakeside School", "LKS06", "Starter", 1200, "successful", "2026-04-16", "2026-04-16", "Sample transfer", "ref-sample-1011", "INV-SAMPLE-1011"),
  row("TXN-SAMPLE-1012", 9006, "Lakeside School", "LKS06", "Starter", 1200, "failed", "2026-08-30", null, "Sample checkout", "ref-sample-1012", null),
  row("TXN-SAMPLE-1013", 9007, "Hillcrest School", "HLC07", "Growth", 4800, "successful", "2026-03-12", "2026-03-12", "Sample checkout", "ref-sample-1013", null),
  row("TXN-SAMPLE-1014", 9007, "Hillcrest School", "HLC07", "Growth", 4800, "pending", "2026-10-15", null, "Sample transfer", null, null),
  row("TXN-SAMPLE-1015", 9008, "Westfield School", "WST08", "Campus", 9600, "successful", "2026-02-08", "2026-02-09", "Sample transfer", "ref-sample-1015", "INV-SAMPLE-1015"),
  row("TXN-SAMPLE-1016", 9008, "Westfield School", "WST08", "Campus", 9600, "failed", "2026-07-19", null, "Sample checkout", "ref-sample-1016", null),
  row("TXN-SAMPLE-1017", 9009, "Oakmont School", "OKM09", "Starter", 1200, "successful", "2026-01-25", "2026-01-25", "Sample checkout", "ref-sample-1017", "INV-SAMPLE-1017"),
  row("TXN-SAMPLE-1018", 9009, "Oakmont School", "OKM09", "Starter", 1200, "pending", "2026-09-07", null, "Sample checkout", null, null),
  row("TXN-SAMPLE-1019", 9010, "Brightpath School", "BRT10", "Growth", 4800, "successful", "2026-10-08", "2026-10-08", "Sample transfer", "ref-sample-1019", "INV-SAMPLE-1019"),
  row("TXN-SAMPLE-1020", 9010, "Brightpath School", "BRT10", "Growth", 4800, "failed", "2026-06-02", null, "Sample transfer", "ref-sample-1020", null),
  row("TXN-SAMPLE-1021", 9001, "North Ridge School", "NRD01", "Campus", 9600, "successful", "2026-11-02", null, "Sample checkout", null, null),
  row("TXN-SAMPLE-1022", 9003, "Maple Lane School", "MPL03", "Growth", 4800, "successful", "2026-12-01", "2026-12-01", "Sample checkout", "ref-sample-1022", "INV-SAMPLE-1022"),
];

function row(
  id: string,
  schoolId: number,
  schoolName: string,
  schoolCode: string,
  planName: string,
  amount: number,
  status: PaymentStatus,
  created: string,
  paid: string | null,
  gateway: string,
  reference: string | null,
  invoiceNumber: string | null,
): PaymentTransaction {
  return {
    id,
    school_id: schoolId,
    school_name: schoolName,
    school_code: schoolCode,
    plan_name: planName,
    amount,
    currency: "INR",
    gateway,
    gateway_reference: reference,
    status,
    created_at: created,
    paid_at: paid,
    invoice: invoiceNumber ? { number: invoiceNumber, date: paid || created } : null,
  };
}

export function paymentStatusLabel(status: PaymentStatus): string {
  if (status === "successful") return "Successful";
  if (status === "pending") return "Pending";
  if (status === "refunded") return "Refunded";
  return "Failed";
}

export function paymentDate(payment: PaymentTransaction): string {
  return payment.paid_at || payment.created_at;
}

export function sampleGateways(): string[] {
  return Array.from(new Set(SAMPLE.map((item) => item.gateway))).sort();
}

export function summarize(items: PaymentTransaction[], source: PaymentSummary["source"]): PaymentSummary {
  const successful = items.filter((item) => item.status === "successful");
  return {
    successful_amount: successful.reduce((sum, item) => sum + item.amount, 0),
    currency: items[0]?.currency || "INR",
    successful_count: successful.length,
    pending_count: items.filter((item) => item.status === "pending").length,
    failed_count: items.filter((item) => item.status === "failed").length,
    source,
  };
}

export function queryPayments(items: PaymentTransaction[], query: PaymentQuery): PaymentList {
  const page = query.page ?? 1;
  const pageSize = query.pageSize ?? 20;
  const q = query.q?.trim().toLowerCase() || "";
  let rows = items.filter((item) => {
    if (query.schoolId && item.school_id !== query.schoolId) return false;
    if (q && !item.id.toLowerCase().includes(q) && !item.school_name.toLowerCase().includes(q)) return false;
    if (query.status && item.status !== query.status) return false;
    if (query.gateway && item.gateway !== query.gateway) return false;
    const day = item.created_at.slice(0, 10);
    if (query.from && day < query.from) return false;
    if (query.to && day > query.to) return false;
    return true;
  });
  const direction = query.sort === "created_at" ? 1 : -1;
  rows = [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at) * direction);
  const start = (page - 1) * pageSize;
  return {
    items: rows.slice(start, start + pageSize),
    total: rows.length,
    page,
    page_size: pageSize,
    source: "sample",
  };
}

// ---------- live: /api/v1/super-admin/payments, /payments/summary and /invoices ----------
//
// The server returns amounts in paise, numeric-free status names (created, authorized,
// captured, failed, refunded) and ids only, so rows are joined here with the schools list and
// the invoices list. It filters by school, status and date; search, gateway and sort run on the
// page over every row (up to 2,000 payments).

type ApiPayment = {
  id: number;
  school_id: number;
  bill_id: number;
  gateway: string;
  order_id: string;
  payment_id: string | null;
  amount: number;
  currency: string;
  status: string;
  invoice_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

type ApiInvoice = {
  id: number;
  invoice_number: string;
  issued_at: string;
  payment_transaction_id: number;
  plan_name: string;
  school_name: string;
};

type ApiPage<T> = { items?: T[]; total?: number };

/** Server status values for each filter option (status may repeat in the query). */
const STATUS_CODES: Record<PaymentStatus, number[]> = { successful: [2], pending: [0, 1], failed: [3], refunded: [4] };

function statusOf(value: string): PaymentStatus {
  if (value === "captured") return "successful";
  if (value === "failed") return "failed";
  if (value === "refunded") return "refunded";
  return "pending";
}

async function allApiPages<T>(path: string, params: URLSearchParams): Promise<ApiResult<T[]>> {
  const rows: T[] = [];
  for (let page = 1; page <= 20; page += 1) {
    params.set("page", String(page));
    params.set("page_size", "100");
    const result = await api<ApiPage<T>>(`${path}?${params.toString()}`);
    if (!result.ok) return result as unknown as ApiResult<T[]>;
    const items = Array.isArray(result.data.items) ? result.data.items : [];
    rows.push(...items);
    if (items.length === 0 || rows.length >= Number(result.data.total ?? rows.length)) break;
  }
  return { ok: true, status: 200, data: rows };
}

type SchoolName = { id: number; name: string; code?: string | null };

async function lookups(schoolId?: number) {
  const invoiceParams = new URLSearchParams();
  if (schoolId) invoiceParams.set("school_id", String(schoolId));
  const [schools, invoices] = await Promise.all([
    allApiPages<SchoolName>("/super-admin/schools", new URLSearchParams()),
    allApiPages<ApiInvoice>("/super-admin/invoices", invoiceParams),
  ]);
  return {
    schools: new Map((schools.ok ? schools.data : []).map((school) => [school.id, school])),
    invoices: new Map((invoices.ok ? invoices.data : []).map((invoice) => [invoice.payment_transaction_id, invoice])),
  };
}

function fromApi(row: ApiPayment, refs: Awaited<ReturnType<typeof lookups>>): PaymentTransaction {
  const school = refs.schools.get(row.school_id);
  const invoice = refs.invoices.get(row.id);
  const status = statusOf(row.status);
  const created = row.created_at || "";
  return {
    id: String(row.id),
    school_id: row.school_id,
    school_name: school?.name || invoice?.school_name || `School #${row.school_id}`,
    school_code: school?.code ?? null,
    plan_name: invoice?.plan_name || "—",
    amount: row.amount / 100,
    currency: row.currency || "INR",
    gateway: row.gateway,
    gateway_reference: row.payment_id || row.order_id || null,
    status,
    created_at: created,
    paid_at: status === "successful" ? row.updated_at || created : null,
    invoice: invoice
      ? { id: invoice.id, number: invoice.invoice_number, date: invoice.issued_at }
      : row.invoice_id
        ? { id: row.invoice_id, number: `Invoice #${row.invoice_id}`, date: row.updated_at || created }
        : null,
  };
}

async function loadLive(query: PaymentQuery): Promise<ApiResult<PaymentList>> {
  const params = new URLSearchParams();
  if (query.schoolId) params.set("school_id", String(query.schoolId));
  if (query.status) STATUS_CODES[query.status].forEach((code) => params.append("status", String(code)));
  if (query.from) params.set("from_date", query.from);
  if (query.to) params.set("to_date", query.to);
  const [rows, refs] = await Promise.all([allApiPages<ApiPayment>("/super-admin/payments", params), lookups(query.schoolId)]);
  if (!rows.ok) return rows as unknown as ApiResult<PaymentList>;
  const list = queryPayments(rows.data.map((row) => fromApi(row, refs)), { ...query, status: "", from: "", to: "" });
  return { ok: true, status: 200, data: { ...list, source: "api" } };
}

function failure<T>(err: unknown): ApiResult<T> {
  const message = err instanceof Error ? err.message : "Network error.";
  return { ok: false, status: 0, data: { detail: message } as unknown as T };
}

export async function loadPayments(query: PaymentQuery = {}): Promise<ApiResult<PaymentList>> {
  try {
    return await loadLive(query);
  } catch (err) {
    return failure(err);
  }
}

export async function loadSchoolPayments(schoolId: number, query: PaymentQuery = {}): Promise<ApiResult<PaymentList>> {
  try {
    return await loadLive({ ...query, schoolId });
  } catch (err) {
    return failure(err);
  }
}

export async function loadPayment(id: string): Promise<ApiResult<PaymentTransaction & { source: "api" | "sample" }>> {
  const sample = SAMPLE.find((item) => item.id === id);
  if (sample) return { ok: true, status: 200, data: { ...sample, source: "sample" } };
  if (!/^\d+$/.test(id)) return { ok: false, status: 404, data: { detail: "Transaction not found." } as unknown as PaymentTransaction & { source: "api" } };
  try {
    const result = await api<ApiPayment>(`/super-admin/payments/${id}`);
    if (!result.ok) return result as unknown as ApiResult<PaymentTransaction & { source: "api" }>;
    const refs = await lookups(result.data.school_id);
    return { ok: true, status: 200, data: { ...fromApi(result.data, refs), source: "api" } };
  } catch (err) {
    return failure(err);
  }
}

export async function loadPaymentSummary(): Promise<ApiResult<PaymentSummary>> {
  try {
    const result = await api<{ currency: string; successful_amount: number; successful_count: number; pending_count: number; failed_count: number }>("/super-admin/payments/summary");
    if (!result.ok) return result as unknown as ApiResult<PaymentSummary>;
    const data = result.data;
    return {
      ok: true,
      status: 200,
      data: {
        successful_amount: Number(data.successful_amount || 0),
        currency: data.currency || "INR",
        successful_count: Number(data.successful_count || 0),
        pending_count: Number(data.pending_count || 0),
        failed_count: Number(data.failed_count || 0),
        source: "api",
      },
    };
  } catch (err) {
    return failure(err);
  }
}

/** Downloads the invoice PDF from /super-admin/invoices/{id}/pdf (sample rows get a text file). */
export async function downloadInvoice(payment: PaymentTransaction): Promise<{ ok: true } | { ok: false; message: string }> {
  if (!payment.invoice) return { ok: false, message: "No invoice has been generated for this transaction." };
  const sample = SAMPLE.find((item) => item.id === payment.id);
  if (sample?.invoice) {
    const text = [
      "SAMPLE INVOICE",
      "This file is sample data. It is not a collected payment and not a tax invoice.",
      "",
      `Invoice: ${sample.invoice.number}`,
      `Invoice date: ${sample.invoice.date}`,
      `Transaction: ${sample.id}`,
      `School: ${sample.school_name}`,
      `Plan: ${sample.plan_name}`,
      `Amount: ${money(sample.amount, sample.currency)}`,
      `Status: ${paymentStatusLabel(sample.status)}`,
    ].join("\n");
    saveBlob(new Blob([text], { type: "text/plain" }), `${sample.invoice.number}.txt`);
    return { ok: true };
  }
  if (!payment.invoice.id) return { ok: false, message: "No invoice has been generated for this transaction." };
  try {
    const token = getAccessToken();
    const response = await fetch(apiUrl(`/super-admin/invoices/${payment.invoice.id}/pdf`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (response.status === 401) return { ok: false, message: "Sign in again to download this invoice." };
    if (response.status === 403) return { ok: false, message: "This account cannot download invoices." };
    if (response.status === 404) return { ok: false, message: "This invoice is no longer on the server." };
    if (!response.ok) {
      const data = (await response.json().catch(() => ({}))) as { detail?: string };
      return { ok: false, message: typeof data.detail === "string" ? data.detail : "Unable to download this invoice." };
    }
    saveBlob(await response.blob(), fileName(response, payment.invoice.number));
    return { ok: true };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error.";
    return { ok: false, message: `Unable to download this invoice. (${message})` };
  }
}

function fileName(response: Response, invoiceNumber: string): string {
  const header = response.headers.get("content-disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(header);
  return match?.[1] || `${invoiceNumber}.pdf`;
}

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
