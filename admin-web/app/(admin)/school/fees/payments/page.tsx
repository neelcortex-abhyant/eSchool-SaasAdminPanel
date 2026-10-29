"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextAreaField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useDebounced, useFormErrors, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { useSubmitOnce } from "@/lib/ops/submit";
import { FEE_TABS, PAYMENT_STATUS, PaymentChip, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { feeService } from "@/lib/ops/fees";
import { PAYMENT_METHODS, type FeePayment, type PaymentMethod, type PaymentStatus } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

const PAGE_SIZE = 20;

export default function FeePaymentsPage() {
  return (
    <TeachingPage
      module="fees"
      title="Fee payments"
      description="Every fee payment, with its receipt. Online payments show as pending until the gateway confirms them."
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
    >
      <Suspense fallback={<div className="skeleton" style={{ height: 200 }} />}>
        <PaymentsBody />
      </Suspense>
    </TeachingPage>
  );
}

function PaymentsBody() {
  const toast = useToast();
  const [cancelling, setCancelling] = useState<FeePayment | null>(null);
  const params = useSearchParams();
  const studentId = Number(params.get("student")) || "";
  const [filter, setFilter] = usePlacementFilter();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [method, setMethod] = useState<PaymentMethod | "">("");
  const [status, setStatus] = useState<PaymentStatus | "">("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const loader = useCallback(
    () => feeService().payments({ page, pageSize: PAGE_SIZE, q: search, studentId, classSectionId: filter.sectionId, method, status, from, to }),
    [page, search, studentId, filter.sectionId, method, status, from, to],
  );
  const list = usePagedList(loader);
  const columns: Column<FeePayment>[] = [
    { key: "date", label: "Date", render: (row) => new Date(row.paid_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) },
    { key: "receipt", label: "Receipt", render: (row) => row.receipt_no ?? "—" },
    { key: "student", label: "Student", render: (row) => <div><strong>{row.student_name}</strong><div className="muted">{row.admission_no} · {row.class_name} {row.section_name}</div></div> },
    { key: "fees", label: "Fees", render: (row) => <span className="muted">{row.allocations.map((item) => item.installment_name).join(", ")}</span> },
    { key: "amount", label: "Amount", render: (row) => <strong>{rupees(row.amount)}</strong> },
    { key: "method", label: "Method", render: (row) => PAYMENT_METHODS.find((item) => item.value === row.method)?.label ?? row.method },
    { key: "reference", label: "Reference", render: (row) => row.reference ?? "—" },
    { key: "status", label: "Status", render: (row) => <PaymentChip status={row.status} /> },
  ];
  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search payments" placeholder="Student, admission no., receipt or reference" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPage(1); }} />
        <select aria-label="Filter by method" value={method} onChange={(event) => { setMethod(event.target.value as PaymentMethod | ""); setPage(1); }}>
          <option value="">All methods</option>
          {PAYMENT_METHODS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as PaymentStatus | ""); setPage(1); }}>
          <option value="">All statuses</option>
          {(Object.keys(PAYMENT_STATUS) as PaymentStatus[]).map((value) => (
            <option key={value} value={value}>
              {PAYMENT_STATUS[value].label}
            </option>
          ))}
        </select>
        <input type="date" aria-label="From date" value={from} max={to || undefined} onChange={(event) => { setFrom(event.target.value); setPage(1); }} />
        <input type="date" aria-label="To date" value={to} min={from || undefined} onChange={(event) => { setTo(event.target.value); setPage(1); }} />
      </div>
      {studentId ? (
        <p className="muted">
          Showing one student's payments. <Link className="link-btn" href="/school/fees/payments">Show everyone</Link>
        </p>
      ) : null}
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "Payments couldn't be loaded." : "No payments match these filters."}
          actions={(row) =>
            row.status === "success" ? (
              <>
                <Link className="link-btn" href={`/school/fees/receipts/${row.id}`}>
                  Receipt
                </Link>
                <button className="link-btn danger" type="button" onClick={() => setCancelling(row)}>
                  Cancel
                </button>
              </>
            ) : row.status === "cancelled" ? (
              <span className="muted">Cancelled{row.cancel_reason ? `: ${row.cancel_reason}` : ""}</span>
            ) : (
              <span className="muted">No receipt yet</span>
            )
          }
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {cancelling ? (
        <CancelPayment
          payment={cancelling}
          onClose={() => setCancelling(null)}
          onDone={() => {
            setCancelling(null);
            toast("success", "Payment cancelled. The amount is owed again.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}

function CancelPayment({ payment, onClose, onDone }: { payment: FeePayment; onClose: () => void; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const submit = useSubmitOnce();
  const errors = useFormErrors();
  return (
    <FormModal
      title="Cancel this payment?"
      description={`${payment.receipt_no ?? "Payment"} · ${payment.student_name} · ${rupees(payment.amount)}. The receipt stays on record marked cancelled, and the amount is owed again.`}
      error={errors.formError}
      saving={submit.busy}
      submitLabel="Cancel payment"
      onSubmit={() =>
        void submit.run(async () => {
          if (!reason.trim()) {
            errors.setFieldErrors({ reason: "Say why the payment is being cancelled." });
            return;
          }
          errors.clear();
          try {
            await feeService().cancelPayment(payment.id, reason);
            onDone();
          } catch (caught) {
            errors.fromError(caught, "Unable to cancel the payment.");
          }
        })
      }
      onClose={onClose}
    >
      <TextAreaField id="cp-reason" label="Reason" required maxLength={512} value={reason} onChange={setReason} error={errors.fieldErrors.reason} hint="For example “Cheque bounced” or “Recorded twice”." span />
    </FormModal>
  );
}
