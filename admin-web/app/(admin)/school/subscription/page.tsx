"use client";

import { useCallback, useState } from "react";
import { AccessGate, useSchoolAdminAccess } from "@/components/academics/AcademicPage";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { ToastProvider, useToast } from "@/components/academics/Toasts";
import { Chip, formatDateTime, Stat, type ChipTone } from "@/components/teaching/Frame";
import { money } from "@/lib/billing";
import { downloadSchoolInvoice, loadSchoolBilling, ownSchoolId, type SchoolInvoice, type SchoolPayment } from "@/lib/schoolBilling";
import { IconFees } from "@/lib/icons";

const STATUS: Record<SchoolPayment["status"], { label: string; tone: ChipTone }> = {
  successful: { label: "Successful", tone: "green" },
  pending: { label: "Pending", tone: "amber" },
  failed: { label: "Failed", tone: "red" },
  refunded: { label: "Refunded", tone: "grey" },
};

export default function SchoolSubscriptionPage() {
  const access = useSchoolAdminAccess();
  return (
    <ToastProvider>
      <div className="acad-page teach-page">
        <header className="acad-header">
          <div className="school-dash-title">
            <span className="school-dash-title-icon" aria-hidden>
              <IconFees width={18} height={18} />
            </span>
            <div>
              <h1>Subscription & billing</h1>
              <p className="muted acad-subtitle">Your school's subscription payments and invoices.</p>
            </div>
          </div>
        </header>
        <div className="alert alert-info acad-mock-note">Connected to the school's server. Plans are changed by the platform team; contact support to upgrade.</div>
        <AccessGate access={access}>
          <BillingBody />
        </AccessGate>
      </div>
    </ToastProvider>
  );
}

function BillingBody() {
  const toast = useToast();
  const [downloading, setDownloading] = useState<number | null>(null);
  const state = useOptions(
    useCallback(async () => {
      const schoolId = await ownSchoolId();
      return [{ schoolId, ...(await loadSchoolBilling(schoolId)) }];
    }, []),
  );
  const data = state.options[0] ?? null;
  const paid = (data?.payments ?? []).filter((row) => row.status === "successful");

  async function download(invoice: SchoolInvoice) {
    if (!data) return;
    setDownloading(invoice.id);
    try {
      await downloadSchoolInvoice(data.schoolId, invoice);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "";
      toast("error", message.includes("(403)") ? "Your account can't download invoices." : message.includes("(404)") ? "This invoice is no longer on the server." : "The invoice couldn't be downloaded. Try again.");
    } finally {
      setDownloading(null);
    }
  }

  const invoiceColumns: Column<SchoolInvoice>[] = [
    { key: "number", label: "Invoice", render: (row) => <strong>{row.invoice_number}</strong> },
    { key: "date", label: "Issued", render: (row) => formatDateTime(row.issued_at) },
    { key: "plan", label: "Plan", render: (row) => `${row.plan_name}${row.cycle ? ` · ${row.cycle}` : ""}` },
    { key: "period", label: "Period", render: (row) => `${row.period_start} → ${row.period_end}` },
    { key: "amount", label: "Total", render: (row) => money(row.total_amount, row.currency) },
  ];

  const paymentColumns: Column<SchoolPayment>[] = [
    { key: "date", label: "Date", render: (row) => formatDateTime(row.created_at) },
    { key: "amount", label: "Amount", render: (row) => money(row.amount, row.currency) },
    { key: "gateway", label: "Gateway", render: (row) => row.gateway || "—" },
    { key: "reference", label: "Reference", render: (row) => row.reference ?? "—" },
    { key: "status", label: "Status", render: (row) => <Chip tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Chip> },
  ];

  return (
    <>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="teach-stats">
        <Stat label="Payments" value={state.loading && !data ? "…" : data?.payments.length ?? 0} />
        <Stat label="Paid" value={paid.length ? money(paid.reduce((sum, row) => sum + row.amount, 0), paid[0].currency) : "—"} tone="green" />
        <Stat label="Invoices" value={data?.invoices.length ?? 0} tone="blue" />
      </div>
      <section className="resource-card" aria-labelledby="invoices-title">
        <h2 id="invoices-title" className="teach-section-title">Invoices</h2>
        <DataTable
          columns={invoiceColumns}
          rows={data?.invoices ?? []}
          loading={state.loading}
          emptyText={state.error ? "Invoices couldn't be loaded." : "No invoices yet. An invoice is issued after each successful payment."}
          actions={(row) => (
            <button className="link-btn" type="button" disabled={downloading === row.id} onClick={() => void download(row)}>
              {downloading === row.id ? "Downloading…" : "Download PDF"}
            </button>
          )}
        />
      </section>
      <section className="resource-card" aria-labelledby="payments-title">
        <h2 id="payments-title" className="teach-section-title">Payments</h2>
        <DataTable columns={paymentColumns} rows={data?.payments ?? []} loading={state.loading} emptyText={state.error ? "Payments couldn't be loaded." : "No payments yet."} />
      </section>
    </>
  );
}
