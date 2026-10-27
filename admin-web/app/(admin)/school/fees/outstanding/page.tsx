"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, useOptions } from "@/components/academics/hooks";
import { FEE_TABS, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { isOpsLive } from "@/lib/ops/mode";
import { Chip, Stat, TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { feeService } from "@/lib/ops/fees";
import { paise } from "@/lib/ops/fees-math";
import type { StudentDues } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

const PAGE_SIZE = 20;

export default function OutstandingFeesPage() {
  return (
    <TeachingPage
      module="fees"
      title="Outstanding fees"
      description="What each student still owes, with overdue installments first."
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
    >
      <OutstandingBody />
    </TeachingPage>
  );
}

function OutstandingBody() {
  const [filter, setFilter] = usePlacementFilter();
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [dueBefore, setDueBefore] = useState("");
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const state = useOptions(
    useCallback(
      () => feeService().outstanding({ sessionYearId: filter.sessionId, classId: filter.classId, classSectionId: filter.sectionId, q: search, dueBefore: dueBefore || undefined, onlyOverdue }),
      [filter.sessionId, filter.classId, filter.sectionId, search, dueBefore, onlyOverdue],
    ),
  );
  const rows = state.options;
  const sums = useMemo(() => {
    const sum = (pick: (row: StudentDues) => number) => paise(rows.reduce((total, row) => total + pick(row), 0));
    return { total: sum((row) => row.total - row.concession), paid: sum((row) => row.paid), balance: sum((row) => row.balance), overdue: sum((row) => row.overdue), overdueCount: rows.filter((row) => row.overdue > 0).length };
  }, [rows]);
  const collectedPercent = sums.total ? Math.round((sums.paid / sums.total) * 1000) / 10 : 0;

  const columns: Column<StudentDues & { id: number }>[] = [
    { key: "student", label: "Student", render: (row) => <div><strong>{row.student_name}</strong><div className="muted">{row.admission_no}</div></div> },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}` },
    { key: "due", label: "Payable", render: (row) => rupees(row.total - row.concession) },
    { key: "paid", label: "Paid", render: (row) => rupees(row.paid) },
    { key: "balance", label: "Balance", render: (row) => (row.balance ? <strong>{rupees(row.balance)}</strong> : <Chip tone="green">Cleared</Chip>) },
    ...(isOpsLive("fees") ? [] : [{
      key: "overdue",
      label: "Overdue",
      render: (row: StudentDues) => {
        const lines = row.lines.filter((line) => line.overdue);
        return lines.length ? (
          <div>
            <Chip tone="red">{rupees(row.overdue)}</Chip>
            <div className="muted">{lines.map((line) => `${line.installment_name} (${line.due_date})`).join(", ")}</div>
          </div>
        ) : (
          "—"
        );
      },
    }]),
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search students" placeholder="Student name or admission no." value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={(next) => { setFilter(next); setPage(1); }} />
        {isOpsLive("fees") ? null : (
          <>
            <label className="ops-filter-label">
              Due by
              <input type="date" aria-label="Due on or before" value={dueBefore} onChange={(event) => { setDueBefore(event.target.value); setPage(1); }} />
            </label>
            <label className="acad-check">
              <input type="checkbox" checked={onlyOverdue} onChange={(event) => { setOnlyOverdue(event.target.checked); setPage(1); }} />
              <span>Overdue only</span>
            </label>
          </>
        )}
      </div>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      <div className="teach-stats">
        <Stat label="Payable" value={state.loading && !rows.length ? "…" : rupees(sums.total)} />
        <Stat label={`Collected (${collectedPercent}%)`} value={rupees(sums.paid)} tone="green" />
        <Stat label="Outstanding" value={rupees(sums.balance)} tone="amber" />
        {isOpsLive("fees") ? null : <Stat label={`Overdue · ${sums.overdueCount} students`} value={rupees(sums.overdue)} tone="red" />}
      </div>
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((row) => ({ ...row, id: row.student_id }))}
          loading={state.loading}
          emptyText={state.error ? "Outstanding fees couldn't be loaded." : onlyOverdue ? "No overdue fees for these filters." : "No fees charged for these filters."}
          actions={(row) =>
            row.balance > 0 ? (
              <Link className="link-btn" href={`/school/fees/collect?student=${row.student_id}`}>
                Collect
              </Link>
            ) : null
          }
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
      </div>
    </>
  );
}
