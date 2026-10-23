"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { PeoplePage } from "@/components/people/PeoplePage";
import { StatusAction } from "@/components/people/StatusAction";
import { peopleService, type Parent } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = peopleService("parents");

export default function ParentsPage() {
  return (
    <PeoplePage
      module="parents"
      title="Parents and guardians"
      description="Parent accounts and the students each one is linked to."
      icon={<IconUsers width={18} height={18} />}
      actions={
        <Link className="btn-pill btn-pill-green" href="/school/parents/new">
          Add parent
        </Link>
      }
    >
      <ParentList />
    </PeoplePage>
  );
}

function ParentList() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [page, setPage] = useState(1);
  const loader = useCallback(() => service.listParents({ page, pageSize: PAGE_SIZE, q: search, status }), [page, search, status]);
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status);

  const columns = useMemo<Column<Parent>[]>(
    () => [
      { key: "name", label: "Name", render: (row) => <Link href={`/school/parents/${row.id}`}><strong>{row.name}</strong></Link> },
      { key: "email", label: "Email", render: (row) => row.email },
      { key: "mobile", label: "Phone", render: (row) => (row.mobile ? <a href={`tel:${row.mobile}`}>{row.mobile}</a> : "—") },
      {
        key: "children",
        label: "Linked students",
        render: (row) =>
          row.children.length ? (
            <ul className="acad-chips">
              {row.children.map((child) => (
                <li key={child.student_id}>
                  {child.name} · {child.class_name} {child.section_name}
                </li>
              ))}
            </ul>
          ) : (
            <span className="muted">None</span>
          ),
      },
      { key: "relationship", label: "Relationship", render: (row) => [...new Set(row.children.map((child) => child.relationship))].join(", ") || "—" },
      { key: "status", label: "Status", render: (row) => <StatusBadge active={row.status === 1} /> },
    ],
    [],
  );

  return (
    <>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search parents"
          placeholder="Search by name, email or phone"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as "" | "0" | "1");
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
      </div>

      <ErrorAlert error={error} onRetry={() => void reload()} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            emptyText={filtered ? "No parents match these filters." : "No parents yet. Parents are added during admission or with Add parent."}
            actions={(row) => (
              <>
                <Link className="link-btn" href={`/school/parents/${row.id}`}>
                  View<span className="acad-sr"> {row.name}</span>
                </Link>
                <Link className="link-btn" href={`/school/parents/${row.id}/edit`}>
                  Edit<span className="acad-sr"> {row.name}</span>
                </Link>
                <StatusAction
                  variant="link"
                  name={row.name}
                  noun="parent"
                  active={row.status === 1}
                  deactivateEffect={`${row.name} won't be able to sign in to the parent app. Their links to students are kept.`}
                  change={(next) => service.setParentStatus(row.id, next)}
                  onChanged={() => reload()}
                />
              </>
            )}
          />
          <Pagination page={data?.page ?? page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPage={setPage} />
        </div>
      ) : null}
    </>
  );
}
