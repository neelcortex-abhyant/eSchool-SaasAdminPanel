"use client";

import { useCallback, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import { DAY_LABEL, DeletePeriod, TIMETABLE_LIVE_NOTE, TIMETABLE_TABS, TimetableForm, type FormSeed } from "@/components/teaching/timetable";
import { timetableService } from "@/lib/teaching/timetable";
import { WEEK_DAYS, type TimetableEntry, type WeekDay } from "@/lib/teaching/types";
import { IconCalendar } from "@/lib/icons";

const PAGE_SIZE = 20;

export default function TimetableListPage() {
  const [form, setForm] = useState<FormSeed | null>(null);
  return (
    <TeachingPage
      module="timetable"
      title="Class timetable"
      description="Every period, filtered by session, class, section and day."
      icon={<IconCalendar width={18} height={18} />}
      tabs={TIMETABLE_TABS}
      liveNote={TIMETABLE_LIVE_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setForm({})}>
          Add period
        </button>
      }
    >
      <ListBody form={form} setForm={setForm} />
    </TeachingPage>
  );
}

function ListBody({ form, setForm }: { form: FormSeed | null; setForm: (seed: FormSeed | null) => void }) {
  const toast = useToast();
  const [filter, setFilter] = usePlacementFilter();
  const [day, setDay] = useState<WeekDay | "">("");
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<TimetableEntry | null>(null);

  const loader = useCallback(
    () =>
      timetableService().list({
        page,
        pageSize: PAGE_SIZE,
        sessionYearId: filter.sessionId,
        classId: filter.classId,
        classSectionId: filter.sectionId,
        day,
      }),
    [page, filter.sessionId, filter.classId, filter.sectionId, day],
  );
  const list = usePagedList(loader);

  const columns: Column<TimetableEntry>[] = [
    { key: "day", label: "Day", render: (row) => DAY_LABEL[row.day] },
    { key: "time", label: "Time", render: (row) => `${row.start_time}–${row.end_time}` },
    { key: "class", label: "Class", render: (row) => `${row.class_name} ${row.section_name}`.trim() },
    { key: "subject", label: "Subject", render: (row) => row.subject_name },
    { key: "teacher", label: "Teacher", render: (row) => row.teacher_name },
    { key: "room", label: "Classroom", render: (row: TimetableEntry) => row.room ?? "—" },
  ];

  return (
    <>
      <div className="school-filters">
        <PlacementFilters
          sessionId={filter.sessionId}
          classId={filter.classId}
          sectionId={filter.sectionId}
          onChange={(next) => {
            setFilter(next);
            setPage(1);
          }}
        />
        <select
          aria-label="Filter by day"
          value={day}
          onChange={(event) => {
            setDay(event.target.value as WeekDay | "");
            setPage(1);
          }}
        >
          <option value="">All days</option>
          {WEEK_DAYS.map((item) => (
            <option key={item} value={item}>
              {DAY_LABEL[item]}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "The periods couldn't be loaded." : "No periods match these filters."}
          actions={(row) => (
            <>
              <button className="link-btn" type="button" onClick={() => setForm({ entry: row })}>
                Edit
              </button>
              <button className="link-btn danger" type="button" onClick={() => setDeleting(row)}>
                Delete
              </button>
            </>
          )}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {form ? (
        <TimetableForm
          seed={form}
          onClose={() => setForm(null)}
          onSaved={(_, created) => {
            setForm(null);
            toast("success", created ? "Period added." : "Period updated.");
            void list.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <DeletePeriod
          entry={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            setDeleting(null);
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}
