"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { DataTable, Pagination, type Column, type SortState } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { StatusBadge } from "@/components/academics/StatusBadge";
import { useDebounced, usePagedList } from "@/components/academics/hooks";
import { classLabel, sectionLabel, sessionLabel, useClassesFor, useSectionsFor, useSessions } from "@/components/people/academicOptions";
import { PeoplePage } from "@/components/people/PeoplePage";
import { Avatar } from "@/components/people/Profile";
import { StatusAction } from "@/components/people/StatusAction";
import { formatDate, peopleService, toId, type StudentRow, type StudentSort } from "@/lib/people";
import { IconUsers } from "@/lib/icons";

const PAGE_SIZE = 10;
const service = peopleService("students");

export default function StudentsPage() {
  return (
    <PeoplePage
      module="students"
      title="Students"
      description="Search, filter and manage every student admitted to your school."
      icon={<IconUsers width={18} height={18} />}
      actions={
        <Link className="btn-pill btn-pill-green" href="/school/students/new">
          Admit student
        </Link>
      }
    >
      <StudentList />
    </PeoplePage>
  );
}

function StudentList() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput.trim());
  const [sessionYearId, setSessionYearId] = useState<number | "">("");
  const [classId, setClassId] = useState<number | "">("");
  const [classSectionId, setClassSectionId] = useState<number | "">("");
  const [status, setStatus] = useState<"" | "0" | "1">("");
  const [sort, setSort] = useState<SortState>({ key: "name", order: "asc" });
  const [page, setPage] = useState(1);

  const sessions = useSessions();
  const classes = useClassesFor(sessionYearId);
  const sections = useSectionsFor(classId);

  const loader = useCallback(
    () =>
      service.listStudents({
        page,
        pageSize: PAGE_SIZE,
        q: search,
        status,
        sessionYearId,
        classId,
        classSectionId,
        sort: sort.key as StudentSort,
        order: sort.order,
      }),
    [page, search, status, sessionYearId, classId, classSectionId, sort],
  );
  const { data, loading, error, reload } = usePagedList(loader);
  const filtered = Boolean(search || status || sessionYearId || classId || classSectionId);

  function onSort(key: string) {
    setSort((current) => ({ key, order: current.key === key && current.order === "asc" ? "desc" : "asc" }));
    setPage(1);
  }

  const columns = useMemo<Column<StudentRow>[]>(
    () => [
      { key: "admission_no", label: "Admission no", sortKey: "admission_no", render: (row) => <code className="people-code">{row.admission_no}</code> },
      {
        key: "name",
        label: "Student",
        sortKey: "name",
        render: (row) => (
          <Link className="people-name-cell" href={`/school/students/${row.id}`}>
            <Avatar name={row.name} photoUrl={row.photo_url} size={32} />
            <span>{row.name}</span>
          </Link>
        ),
      },
      { key: "class", label: "Class", sortKey: "class", render: (row) => `${row.class_name} ${row.section_name}` },
      { key: "guardian", label: "Parent/guardian", render: (row) => row.guardian_name ?? "—" },
      { key: "contact", label: "Contact", render: (row) => (row.guardian_mobile ? <a href={`tel:${row.guardian_mobile}`}>{row.guardian_mobile}</a> : "—") },
      { key: "admission_date", label: "Admitted", sortKey: "admission_date", render: (row) => formatDate(row.admission_date) },
      { key: "status", label: "Status", render: (row) => <StatusBadge active={row.status === 1} /> },
    ],
    [],
  );

  return (
    <>
      <div className="school-filters">
        <input
          type="search"
          aria-label="Search students"
          placeholder="Search by name or admission number"
          value={searchInput}
          onChange={(event) => {
            setSearchInput(event.target.value);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by session"
          value={sessionYearId}
          onChange={(event) => {
            setSessionYearId(toId(event.target.value));
            setClassId("");
            setClassSectionId("");
            setPage(1);
          }}
        >
          <option value="">{sessions.loading ? "Loading sessions…" : "All sessions"}</option>
          {sessions.options.map((row) => (
            <option key={row.id} value={row.id}>
              {sessionLabel(row)}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by class"
          value={classId}
          onChange={(event) => {
            setClassId(toId(event.target.value));
            setClassSectionId("");
            setPage(1);
          }}
        >
          <option value="">{classes.loading ? "Loading classes…" : "All classes"}</option>
          {classes.options.map((row) => (
            <option key={row.id} value={row.id}>
              {classLabel(row)}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by section"
          value={classSectionId}
          disabled={!classId}
          onChange={(event) => {
            setClassSectionId(toId(event.target.value));
            setPage(1);
          }}
        >
          <option value="">{!classId ? "Choose a class first" : sections.loading ? "Loading sections…" : "All sections"}</option>
          {sections.options.map((row) => (
            <option key={row.id} value={row.id}>
              {sectionLabel(row)}
            </option>
          ))}
        </select>
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
        {/* Column headers sort on wide screens; this keeps sorting available when rows become cards. */}
        <select
          className="people-sort-select"
          aria-label="Sort students"
          value={`${sort.key}:${sort.order}`}
          onChange={(event) => {
            const [key, order] = event.target.value.split(":");
            setSort({ key, order: order as "asc" | "desc" });
            setPage(1);
          }}
        >
          <option value="name:asc">Name A–Z</option>
          <option value="name:desc">Name Z–A</option>
          <option value="admission_no:asc">Admission no, lowest first</option>
          <option value="admission_no:desc">Admission no, highest first</option>
          <option value="admission_date:desc">Newest admissions</option>
          <option value="admission_date:asc">Oldest admissions</option>
          <option value="class:asc">Class</option>
        </select>
      </div>

      <ErrorAlert error={error ?? sessions.error ?? classes.error} onRetry={() => { void reload(); void sessions.reload(); void classes.reload(); }} />

      {!error ? (
        <div className="resource-card">
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={loading}
            sort={sort}
            onSort={onSort}
            emptyText={filtered ? "No students match these filters." : "No students yet. Use Admit student to add the first one."}
            actions={(row) => (
              <>
                <Link className="link-btn" href={`/school/students/${row.id}`}>
                  View<span className="acad-sr"> {row.name}</span>
                </Link>
                <Link className="link-btn" href={`/school/students/${row.id}/edit`}>
                  Edit<span className="acad-sr"> {row.name}</span>
                </Link>
                <StatusAction
                  variant="link"
                  name={row.name}
                  noun="student"
                  active={row.status === 1}
                  deactivateEffect={`${row.name} stays in your records but is hidden from attendance, exams and fee lists, and their parents can't see them in the app.`}
                  change={(next) => service.setStudentStatus(row.id, next)}
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
