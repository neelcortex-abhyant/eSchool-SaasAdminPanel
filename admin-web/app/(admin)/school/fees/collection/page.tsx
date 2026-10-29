"use client";

import { useCallback, useState } from "react";
import { DataTable, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { FEE_TABS, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { Stat, TeachingPage } from "@/components/teaching/Frame";
import { listAll, academicsService } from "@/lib/academics";
import { downloadText, toCsv } from "@/lib/operations/export";
import { feeService } from "@/lib/ops/fees";
import { PAYMENT_METHODS, type CollectionReport } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

export default function CollectionReportPage() {
  return (
    <TeachingPage module="fees" title="Fee collection report" description="What was collected in a period, by payment method and class." icon={<IconFees width={18} height={18} />} tabs={FEE_TABS} liveNote={OPS_LIVE_NOTE.fees}>
      <ReportBody />
    </TeachingPage>
  );
}

function monthStart() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function today() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

type Row = CollectionReport["items"][number];

function ReportBody() {
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const [classId, setClassId] = useState("");
  const classes = useOptions(useCallback(() => listAll((page) => academicsService("classes").listClasses({ page, pageSize: 50 })), []));
  const report = useOptions(useCallback(() => feeService().collectionReport(from, to, classId ? Number(classId) : "").then((row) => [row]), [from, to, classId]));
  const data = report.options[0];
  const method = (value: string) => PAYMENT_METHODS.find((item) => item.value === value)?.label ?? value;
  const columns: Column<Row>[] = [
    { key: "date", label: "Paid on", render: (row) => row.paid_on },
    { key: "receipt", label: "Receipt", render: (row) => row.receipt_no ?? "—" },
    { key: "student", label: "Student", render: (row) => row.student_name },
    { key: "method", label: "Method", render: (row) => method(row.method) },
    { key: "amount", label: "Amount", render: (row) => <strong>{rupees(row.amount)}</strong> },
  ];
  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">From <input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></label>
        <label className="ops-filter-label">To <input type="date" value={to} min={from} onChange={(event) => setTo(event.target.value)} /></label>
        <select aria-label="Class" value={classId} onChange={(event) => setClassId(event.target.value)}>
          <option value="">All classes</option>
          {classes.options.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
        <button
          className="btn-pill btn-pill-green-soft"
          type="button"
          disabled={!data?.items.length}
          onClick={() =>
            data &&
            downloadText(`fee-collection-${from}-to-${to}.csv`, toCsv(data.items, [
              { label: "Paid on", value: (row) => row.paid_on },
              { label: "Receipt", value: (row) => row.receipt_no },
              { label: "Student", value: (row) => row.student_name },
              { label: "Method", value: (row) => method(row.method) },
              { label: "Amount", value: (row) => row.amount },
            ]))
          }
        >
          Export CSV
        </button>
      </div>
      {data ? (
        <div className="teach-stats">
          <Stat label={`Collected · ${data.payment_count} payments`} value={rupees(data.total_collected)} tone="green" />
          {Object.entries(data.by_method).map(([key, value]) => <Stat key={key} label={method(key)} value={rupees(value)} tone="blue" />)}
        </div>
      ) : null}
      <ErrorAlert error={report.error} onRetry={() => void report.reload()} />
      <div className="resource-card">
        <DataTable columns={columns} rows={data?.items ?? []} loading={report.loading} emptyText="No payments in this period." />
      </div>
    </>
  );
}
