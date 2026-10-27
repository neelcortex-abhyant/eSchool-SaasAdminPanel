"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { classLabel, sessionLabel, useClassesFor, useSessions } from "@/components/people/academicOptions";
import { FEE_TABS, StructureForm, rupees } from "@/components/ops/fees";
import { OPS_LIVE_NOTE } from "@/components/ops/notes";
import { isOpsLive } from "@/lib/ops/mode";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { useCurrentSessionId } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { feeService } from "@/lib/ops/fees";
import type { FeeStructure, FeeStructureQuery } from "@/lib/ops/types";
import { IconFees } from "@/lib/icons";

const PAGE_SIZE = 10;

export default function FeeStructuresPage() {
  const [editing, setEditing] = useState<FeeStructure | "new" | null>(null);
  return (
    <TeachingPage
      module="fees"
      title="Fee structures"
      description={isOpsLive("fees") ? "Fees per class and session. Assign a structure to each student who pays it." : "Fees per class and session, with installments. Students in the class are charged automatically."}
      icon={<IconFees width={18} height={18} />}
      tabs={FEE_TABS}
      liveNote={OPS_LIVE_NOTE.fees}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setEditing("new")}>
          Add fee structure
        </button>
      }
    >
      <StructuresBody editing={editing} setEditing={setEditing} />
    </TeachingPage>
  );
}

function StructuresBody({ editing, setEditing }: { editing: FeeStructure | "new" | null; setEditing: (value: FeeStructure | "new" | null) => void }) {
  const toast = useToast();
  const currentSessionId = useCurrentSessionId();
  const sessions = useSessions();
  const [chosenSession, setChosenSession] = useState<number | "" | null>(null);
  const sessionId = chosenSession ?? currentSessionId;
  const [classId, setClassId] = useState<number | "">("");
  const classes = useClassesFor(sessionId);
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [sort, setSort] = useState<NonNullable<FeeStructureQuery["sort"]>>("class");
  const [page, setPage] = useState(1);

  const loader = useCallback(
    () => feeService().structures({ page, pageSize: PAGE_SIZE, q: search, sessionYearId: sessionId, classId, status, sort, order: sort === "total" ? "desc" : "asc" }),
    [page, search, sessionId, classId, status, sort],
  );
  const list = usePagedList(loader);

  async function toggle(row: FeeStructure) {
    try {
      await feeService().setStructureStatus(row.id, row.status === 1 ? 0 : 1);
      toast("success", row.status === 1 ? `${row.name} is no longer charged.` : `${row.name} is charged again.`);
      void list.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the fee structure."));
    }
  }

  const columns: Column<FeeStructure>[] = [
    {
      key: "name",
      label: "Fee structure",
      render: (row) => (
        <div>
          <strong>{row.name}</strong>
          <div className="muted">{row.items.map((item) => item.fee_type_name).join(", ")}</div>
        </div>
      ),
    },
    { key: "class", label: "Class", render: (row) => row.class_name },
    { key: "session", label: "Session", render: (row) => row.session_name },
    { key: "amount", label: "Amount", render: (row) => <strong>{rupees(row.total)}</strong> },
    ...(isOpsLive("fees")
      ? []
      : [
          {
            key: "installments",
            label: "Installments",
            render: (row: FeeStructure) => (
              <span className="muted">
                {row.installments.length === 1 ? `One payment, due ${row.installments[0].due_date}` : `${row.installments.length} · first due ${row.installments[0]?.due_date ?? "—"}`}
              </span>
            ),
          },
        ]),
    { key: "status", label: "Status", render: (row) => (row.status === 1 ? <Chip tone="green">Active</Chip> : <Chip tone="grey">Inactive</Chip>) },
  ];

  return (
    <>
      <div className="school-filters">
        <input type="search" aria-label="Search fee structures" placeholder="Search by name or fee type" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
        <select aria-label="Filter by session" value={sessionId} onChange={(event) => { setChosenSession(event.target.value ? Number(event.target.value) : ""); setClassId(""); setPage(1); }}>
          <option value="">All sessions</option>
          {sessions.options.map((row) => (
            <option key={row.id} value={row.id}>
              {sessionLabel(row)}
            </option>
          ))}
        </select>
        <select aria-label="Filter by class" value={classId} onChange={(event) => { setClassId(event.target.value ? Number(event.target.value) : ""); setPage(1); }}>
          <option value="">{classes.loading ? "Loading classes…" : "All classes"}</option>
          {classes.options.map((row) => (
            <option key={row.id} value={row.id}>
              {classLabel(row)}
            </option>
          ))}
        </select>
        <select aria-label="Filter by status" value={status} onChange={(event) => { setStatus(event.target.value as "" | "0" | "1"); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
        <select aria-label="Sort by" value={sort} onChange={(event) => setSort(event.target.value as NonNullable<FeeStructureQuery["sort"]>)}>
          <option value="class">Class</option>
          <option value="name">Name</option>
          <option value="total">Highest amount</option>
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "Fee structures couldn't be loaded." : search || classId || status ? "No fee structures match these filters." : "No fee structures for this session yet."}
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setEditing(row)}>
                Edit
              </button>
              <Link className="link-btn" href={`/school/fees/assignments?structure=${row.id}`}>
                Assign
              </Link>
              <button className={`link-btn${row.status === 1 ? " danger" : ""}`} type="button" onClick={() => void toggle(row)}>
                {row.status === 1 ? "Deactivate" : "Activate"}
              </button>
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      <p className="muted">
        Fee amounts already saved on the school's server through the older form are still on{" "}
        <Link className="link-btn" href="/school/manage-fees">
          Fee amounts (server)
        </Link>
        .
      </p>
      {editing ? (
        <StructureForm
          structure={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(_, created) => {
            setEditing(null);
            toast("success", created ? "Fee structure added." : "Fee structure saved.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}
