"use client";

import { useCallback, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { TeachingPage } from "@/components/teaching/Frame";
import { PlacementFilters, usePlacementFilter } from "@/components/teaching/Pickers";
import {
  DAY_LABEL,
  DeletePeriod,
  PeriodDialog,
  TIMETABLE_LIVE_NOTE,
  TIMETABLE_TABS,
  TimetableForm,
  WeekGridView,
  todayWeekDay,
  type FormSeed,
} from "@/components/teaching/timetable";
import { timetableService } from "@/lib/teaching/timetable";
import { WEEK_DAYS, type TimetableEntry, type WeekDay } from "@/lib/teaching/types";
import { IconCalendar } from "@/lib/icons";

export default function TimetablePage() {
  const [form, setForm] = useState<FormSeed | null>(null);
  return (
    <TeachingPage
      module="timetable"
      title="Class timetable"
      description="Plan each section's week. A section or teacher can't be booked for two periods at once."
      icon={<IconCalendar width={18} height={18} />}
      tabs={TIMETABLE_TABS}
      liveNote={TIMETABLE_LIVE_NOTE}
      actions={
        <button className="btn-pill btn-pill-green" type="button" onClick={() => setForm({})}>
          Add period
        </button>
      }
    >
      <WeeklyBody form={form} setForm={setForm} />
    </TeachingPage>
  );
}

function WeeklyBody({ form, setForm }: { form: FormSeed | null; setForm: (seed: FormSeed | null) => void }) {
  const toast = useToast();
  const [filter, setFilter] = usePlacementFilter();
  const [view, setView] = useState<"week" | WeekDay>("week");
  const [open, setOpen] = useState<TimetableEntry | null>(null);
  const [deleting, setDeleting] = useState<TimetableEntry | null>(null);
  const ready = Boolean(filter.sessionId && filter.sectionId);

  const loader = useCallback(
    () => timetableService().weekly(Number(filter.sessionId), Number(filter.sectionId)).then((grid) => [grid]),
    [filter.sessionId, filter.sectionId],
  );
  const week = useOptions(ready ? loader : null);
  const grid = week.options[0] ?? null;

  const placementSeed = ready
    ? { session_year_id: String(filter.sessionId), class_id: String(filter.classId), class_section_id: String(filter.sectionId) }
    : undefined;

  return (
    <>
      <div className="school-filters">
        <PlacementFilters sessionId={filter.sessionId} classId={filter.classId} sectionId={filter.sectionId} onChange={setFilter} />
        <select aria-label="View" value={view} onChange={(event) => setView(event.target.value as "week" | WeekDay)}>
          <option value="week">Whole week</option>
          {WEEK_DAYS.map((day) => (
            <option key={day} value={day}>
              {DAY_LABEL[day]}
              {day === todayWeekDay() ? " (today)" : ""}
            </option>
          ))}
        </select>
      </div>
      <ErrorAlert error={week.error} onRetry={() => void week.reload()} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">Choose a session, class and section to see its timetable.</div>
        </div>
      ) : week.error ? null : (
        <WeekGridView
          grid={grid}
          loading={week.loading}
          show="class"
          days={view === "week" ? undefined : [view]}
          emptyText="No periods yet for this section. Use Add period or the + Add link on a day."
          onOpen={setOpen}
          onAdd={(day) => setForm({ placement: placementSeed, day })}
        />
      )}
      {open ? (
        <PeriodDialog
          entry={open}
          onClose={() => setOpen(null)}
          onEdit={() => {
            setForm({ entry: open });
            setOpen(null);
          }}
          onDelete={() => {
            setDeleting(open);
            setOpen(null);
          }}
        />
      ) : null}
      {form ? (
        <TimetableForm
          seed={form.entry || form.placement ? form : { ...form, placement: placementSeed }}
          onClose={() => setForm(null)}
          onSaved={(_, created) => {
            setForm(null);
            toast("success", created ? "Period added." : "Period updated.");
            void week.reload();
          }}
        />
      ) : null}
      {deleting ? (
        <DeletePeriod
          entry={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            setDeleting(null);
            void week.reload();
          }}
        />
      ) : null}
    </>
  );
}
