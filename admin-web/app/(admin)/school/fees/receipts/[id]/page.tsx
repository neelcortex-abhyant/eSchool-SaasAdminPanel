"use client";

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { PaymentChip, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { TeachingPage } from "@/components/teaching/Frame";
import { feeService } from "@/lib/ops/fees";
import { PAYMENT_METHODS } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";
import { apiBlobUrl } from "@/lib/api";

export default function ReceiptPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  return (
    <TeachingPage module="fees" title="Fee receipt" icon={<IconFees width={18} height={18} />} liveNote={OPS_LIVE_NOTE.fees} back={{ href: "/school/fees/payments", label: "Fee payments" }}>
      {Number.isInteger(id) && id > 0 ? <ReceiptBody id={id} /> : <div className="alert alert-danger">This receipt link isn't valid.</div>}
    </TeachingPage>
  );
}

function ReceiptBody({ id }: { id: number }) {
  const state = useOptions(useCallback(() => feeService().receipt(id).then((row) => [row]), [id]));
  const receipt = state.options[0] ?? null;
  if (state.error) return <ErrorAlert error={state.error} onRetry={() => void state.reload()} />;
  if (!receipt) return <div className="resource-card"><div className="skeleton" style={{ height: 300 }} /></div>;
  const { payment } = receipt;
  return (
    <>
      <div className="school-filters ops-no-print">
        <button className="btn-pill btn-pill-green" type="button" onClick={() => window.print()}>
          Print
        </button>
        {receipt.pdf_path ? <ReceiptPdfButton path={receipt.pdf_path} name={payment.receipt_no ?? `receipt-${payment.id}`} /> : null}
      </div>
      {payment.status === "cancelled" ? <div className="alert alert-danger">This payment was cancelled{payment.cancel_reason ? `: ${payment.cancel_reason}` : ""}. The amount is owed again.</div> : null}
      <article className="resource-card ops-report ops-receipt" aria-labelledby="receipt-title">
        <header className="ops-report-head">
          <div>
            <h2 id="receipt-title">{receipt.school_name}</h2>
            <p className="muted">Fee receipt · {receipt.session_name}</p>
          </div>
          <div className="ops-report-overall">
            <span className="ops-report-grade">{payment.receipt_no}</span>
            <PaymentChip status={payment.status} />
          </div>
        </header>
        <dl className="teach-facts">
          <div><dt>Student</dt><dd>{payment.student_name}</dd></div>
          <div><dt>Admission no.</dt><dd>{payment.admission_no}</dd></div>
          <div><dt>Class</dt><dd>{payment.class_name} {payment.section_name}</dd></div>
          <div><dt>Paid on</dt><dd>{new Date(payment.paid_at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}</dd></div>
          <div><dt>Method</dt><dd>{PAYMENT_METHODS.find((item) => item.value === payment.method)?.label ?? payment.method}</dd></div>
          <div><dt>Reference</dt><dd>{payment.reference ?? "—"}</dd></div>
        </dl>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Towards</th>
                <th scope="col">Amount</th>
              </tr>
            </thead>
            <tbody>
              {payment.allocations.map((item) => (
                <tr key={`${item.structure_id}-${item.installment_id}`}>
                  <td>{item.installment_name}</td>
                  <td>{rupees(item.amount)}</td>
                </tr>
              ))}
              <tr className="ops-report-total">
                <th scope="row">Total paid</th>
                <td>{rupees(payment.amount)}</td>
              </tr>
              <tr>
                <th scope="row">Balance remaining after this payment</th>
                <td>{rupees(receipt.balance_after)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {payment.remarks ? <p className="muted">Remarks: {payment.remarks}</p> : null}
        <p className="muted ops-report-foot">{payment.collected_by ? `Received by ${payment.collected_by}. ` : ""}This is a computer-generated receipt.</p>
      </article>
    </>
  );
}

/** Downloads the server's PDF of the receipt (it needs the signed-in user's token, so it's fetched rather than linked). */
function ReceiptPdfButton({ path, name }: { path: string; name: string }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  return (
    <>
      <button
        className="btn-pill btn-pill-green-soft"
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setProblem("");
          try {
            const url = await apiBlobUrl(path);
            const link = document.createElement("a");
            link.href = url;
            link.download = `${name}.pdf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          } catch {
            setProblem("The PDF couldn't be downloaded. Try Print instead.");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Downloading…" : "Download PDF"}
      </button>
      {problem ? <span className="field-error">{problem}</span> : null}
    </>
  );
}
