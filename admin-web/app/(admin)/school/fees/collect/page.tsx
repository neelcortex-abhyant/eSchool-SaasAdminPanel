"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextField } from "@/components/academics/Fields";
import { useFormErrors, useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { FEE_TABS, PaymentChip, StudentPicker, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { isOpsLive } from "@/lib/ops/mode";
import { Chip, Stat, TeachingPage } from "@/components/teaching/Frame";
import { peopleService, type StudentRow } from "@/lib/people";
import { feeService, paymentProblems } from "@/lib/ops/fees";
import { allocate } from "@/lib/ops/fees-math";
import { today } from "@/lib/ops/store";
import { newIdempotencyKey, useSubmitOnce } from "@/lib/ops/submit";
import { PAYMENT_METHODS, type DueLine, type FeePayment, type PaymentMethod, type StudentDues } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

export default function CollectFeesPage() {
  return (
    <TeachingPage
      module="fees"
      title="Collect fees"
      description="Find a student, see what they owe, and record a payment. Part payments are applied to the earliest installment first."
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
    >
      <Suspense fallback={<div className="skeleton" style={{ height: 200 }} />}>
        <CollectBody />
      </Suspense>
    </TeachingPage>
  );
}

function CollectBody() {
  const params = useSearchParams();
  const router = useRouter();
  const [student, setStudent] = useState<StudentRow | null>(null);
  const linked = Number(params.get("student")) || 0;

  useEffect(() => {
    if (!linked || student?.id === linked) return;
    let cancelled = false;
    peopleService("students")
      .getStudent(linked)
      .then((row) => !cancelled && setStudent(row))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [linked, student?.id]);

  const dues = useOptions(useCallback(() => (student ? feeService().dues(student.id).then((row) => [row]) : Promise.resolve([])), [student]));
  const history = useOptions(useCallback(() => (student ? feeService().payments({ studentId: student.id, pageSize: 10 }).then((page) => page.items) : Promise.resolve([])), [student]));
  const data = dues.options[0] ?? null;

  return (
    <>
      <section className="resource-card">
        <div className="resource-fields">
          <StudentPicker
            id="collect-student"
            value={student}
            onPick={(picked) => {
              setStudent(picked);
              router.replace(picked ? `/school/fees/collect?student=${picked.id}` : "/school/fees/collect");
            }}
          />
        </div>
      </section>
      {!student ? (
        <div className="resource-card">
          <div className="empty-state">Search for a student to see their fees.</div>
        </div>
      ) : (
        <>
          <ErrorAlert error={dues.error} onRetry={() => void dues.reload()} />
          {data ? <DuesSummary dues={data} /> : dues.loading ? <div className="skeleton" style={{ height: 120 }} /> : null}
          {data ? (
            <PaymentPanel
              dues={data}
              onRecorded={() => {
                void dues.reload();
                void history.reload();
              }}
            />
          ) : null}
          <section className="resource-card" aria-labelledby="recent-title">
            <div className="teach-detail-head">
              <h2 id="recent-title" className="teach-section-title">Recent payments</h2>
              <Link className="link-btn" href={`/school/fees/payments?student=${student.id}`}>
                All payments
              </Link>
            </div>
            <PaymentsMini rows={history.options} loading={history.loading} />
          </section>
        </>
      )}
    </>
  );
}

function DuesSummary({ dues }: { dues: StudentDues }) {
  const columns: Column<DueLine & { id: number }>[] = [
    { key: "fee", label: "Fee", render: (row) => <div><strong>{row.installment_name}</strong><div className="muted">{row.structure_name}</div></div> },
    ...(isOpsLive("fees") ? [] : [{ key: "due", label: "Due", render: (row: DueLine & { id: number }) => (row.overdue ? <span className="field-error">{row.due_date} · overdue</span> : row.due_date) }]),
    { key: "amount", label: "Amount", render: (row) => rupees(row.amount) },
    { key: "concession", label: "Concession", render: (row) => (row.concession ? `− ${rupees(row.concession)}` : "—") },
    { key: "paid", label: "Paid", render: (row) => (row.paid ? rupees(row.paid) : "—") },
    { key: "balance", label: "Balance", render: (row) => (row.balance ? <strong>{rupees(row.balance)}</strong> : <Chip tone="green">Paid</Chip>) },
  ];
  return (
    <>
      <div className="teach-stats">
        <Stat label="Total fees" value={rupees(dues.total)} />
        <Stat label="Concessions" value={rupees(dues.concession)} tone="blue" />
        <Stat label="Paid" value={rupees(dues.paid)} tone="green" />
        <Stat label="Balance" value={rupees(dues.balance)} tone={dues.balance ? "amber" : "green"} />
        {isOpsLive("fees") ? null : <Stat label="Overdue" value={rupees(dues.overdue)} tone={dues.overdue ? "red" : "grey"} />}
      </div>
      {dues.pending ? <div className="alert alert-info">{rupees(dues.pending)} in online payments is waiting for confirmation and isn't counted as paid yet.</div> : null}
      <section className="resource-card" aria-label="Installments">
        <DataTable
          columns={columns}
          rows={dues.lines.map((line) => ({ ...line, id: line.structure_id * 10000 + line.installment_id }))}
          loading={false}
          emptyText={isOpsLive("fees") ? "No fees are assigned to this student. Assign a fee structure to them first." : "No fee structure applies to this student. Add one for their class, or assign fees to them."}
        />
      </section>
    </>
  );
}

function PaymentPanel({ dues, onRecorded }: { dues: StudentDues; onRecorded: () => void }) {
  const toast = useToast();
  const nextDue = dues.lines.find((line) => line.balance > 0);
  const [amount, setAmount] = useState(nextDue ? String(dues.overdue || nextDue.balance) : "");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(today());
  const [remarks, setRemarks] = useState("");
  // One key per attempt: a retry of the same attempt can't be recorded twice.
  const [key, setKey] = useState(newIdempotencyKey);
  const [result, setResult] = useState<FeePayment | null>(null);
  const { busy, run } = useSubmitOnce();
  const errors = useFormErrors();
  const preview = useMemo(() => {
    try {
      return Number(amount) > 0 ? allocate(Number(amount), dues.lines) : [];
    } catch {
      return [];
    }
  }, [amount, dues.lines]);
  const online = !PAYMENT_METHODS.find((item) => item.value === method)?.manual;

  if (dues.balance <= 0 && !result) {
    return (
      <div className="alert alert-success" role="status">
        Nothing is due for {dues.student_name}.
      </div>
    );
  }

  async function submit() {
    const input = { student_id: dues.student_id, amount: Number(amount), method, reference: reference.trim() || null, remarks: remarks.trim() || null, paid_on: paidOn };
    const problems = paymentProblems(input, dues.balance);
    if (Object.keys(problems).length) {
      errors.setFieldErrors(problems);
      errors.setFormError("");
      return;
    }
    errors.clear();
    await run(async () => {
      try {
        const saved = await feeService().recordPayment({ ...input, idempotency_key: key });
        setResult(saved);
        setKey(newIdempotencyKey());
        setReference("");
        setRemarks("");
        toast("success", saved.status === "success" ? `Payment of ${rupees(saved.amount)} recorded.` : "Recorded as pending. It counts once the payment gateway confirms it.");
        onRecorded();
      } catch (caught) {
        // Keep the same key so a retry after a network error can't record the payment twice.
        errors.fromError(caught, "Unable to record the payment.");
      }
    });
  }

  return (
    <section className="resource-card" aria-labelledby="pay-title">
      <h2 id="pay-title" className="teach-section-title">Record a payment</h2>
      {result ? (
        <div className={`alert ${result.status === "success" ? "alert-success" : "alert-info"}`} role="status">
          {result.status === "success" ? (
            <>
              {rupees(result.amount)} recorded · receipt {result.receipt_no}.{" "}
              <Link className="link-btn" href={`/school/fees/receipts/${result.id}`}>
                View receipt
              </Link>
            </>
          ) : (
            <>
              {rupees(result.amount)} is <strong>pending confirmation</strong>. It isn't counted as paid and no receipt is issued until the payment gateway confirms it.
            </>
          )}
        </div>
      ) : null}
      {errors.formError ? <div className="alert alert-danger" role="alert">{errors.formError}</div> : null}
      <form
        className="resource-fields"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <TextField id="pay-amount" label={`Amount (₹, up to ${rupees(dues.balance)})`} type="number" min="0" required value={amount} onChange={setAmount} error={errors.fieldErrors.amount} hint={dues.overdue ? `Overdue now: ${rupees(dues.overdue)}` : nextDue && nextDue.due_date ? `Next due: ${rupees(nextDue.balance)} on ${nextDue.due_date}` : undefined} />
        <SelectField id="pay-method" label="Paid by" required value={method} onChange={(value) => setMethod(value as PaymentMethod)} options={PAYMENT_METHODS.filter((item) => item.manual || !isOpsLive("fees")).map((item) => ({ value: item.value, label: item.label }))} error={errors.fieldErrors.method} />
        <TextField id="pay-reference" label={method === "cheque" ? "Cheque number" : "Transaction reference"} required={["cheque", "bank_transfer", "upi"].includes(method)} maxLength={60} value={reference} onChange={setReference} error={errors.fieldErrors.reference} />
        <TextField id="pay-date" label="Paid on" type="date" required max={today()} value={paidOn} onChange={setPaidOn} error={errors.fieldErrors.paid_on} />
        <TextField id="pay-remarks" label="Remarks" span maxLength={255} value={remarks} onChange={setRemarks} />
        {preview.length ? (
          <div className="form-field field-span">
            <span className="field-label">This payment covers</span>
            <ul className="teach-list">
              {preview.map((item) => (
                <li key={`${item.structure_id}-${item.installment_id}`}>
                  {item.installment_name}: {rupees(item.amount)}
                </li>
              ))}
            </ul>
            <p className="muted">Balance after this payment: {rupees(Math.max(dues.balance - Number(amount || 0), 0))}</p>
          </div>
        ) : null}
        {online ? <p className="alert alert-info field-span">Online payments are only marked paid when the payment gateway confirms them; this records a pending payment.</p> : null}
        <div className="field-span">
          <button className="btn-pill btn-pill-green ops-inline-btn" type="submit" disabled={busy}>
            {busy ? "Recording…" : online ? "Record pending online payment" : "Record payment"}
          </button>
        </div>
      </form>
    </section>
  );
}

function PaymentsMini({ rows, loading }: { rows: FeePayment[]; loading: boolean }) {
  const columns: Column<FeePayment>[] = [
    { key: "date", label: "Date", render: (row) => row.paid_at.slice(0, 10) },
    { key: "amount", label: "Amount", render: (row) => rupees(row.amount) },
    { key: "method", label: "Method", render: (row) => PAYMENT_METHODS.find((item) => item.value === row.method)?.label ?? row.method },
    { key: "status", label: "Status", render: (row) => <PaymentChip status={row.status} /> },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="No payments yet."
      actions={(row) =>
        row.status === "success" ? (
          <Link className="link-btn" href={`/school/fees/receipts/${row.id}`}>
            Receipt
          </Link>
        ) : null
      }
    />
  );
}
