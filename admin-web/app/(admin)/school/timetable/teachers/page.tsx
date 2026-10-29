"use client";

import { useCallback, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { TextField } from "@/components/academics/Fields";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { sessionLabel, useSessions } from "@/components/people/academicOptions";
import { Chip, TeachingPage } from "@/components/teaching/Frame";
import { useCurrentSessionId, useTeachers } from "@/components/teaching/Pickers";
import {
  DAY_LABEL,
  DeletePeriod,
  PeriodDialog,
  TIMETABLE_LIVE_NOTE,
  TIMETABLE_TABS,
  TimetableForm,
  WeekGridView,
  conflictIds,
  todayWeekDay,
  type FormSeed,
} from "@/components/teaching/timetable";
import { errorMessage } from "@/lib/academics";
import { timetableService } from "@/lib/teaching/timetable";
import { WEEK_DAYS, type Availability, type TimetableEntry, type WeekDay } from "@/lib/teaching/types";
import { IconCalendar } from "@/lib/icons";

export default function TeacherSchedulePage() {
  return (
    <TeachingPage
      module="timetable"
      title="Teacher schedules"
      description="See a teacher's day or week, spot clashes and check whether they're free before booking a period."
      icon={<IconCalendar width={18} height={18} />}
      tabs={TIMETABLE_TABS}
      liveNote={TIMETABLE_LIVE_NOTE}
    >
      <ScheduleBody />
    </TeachingPage>
  );
}

function ScheduleBody() {
  const toast = useToast();
  const sessions = useSessions();
  const teachers = useTeachers();
  const currentSessionId = useCurrentSessionId();
  const [chosenSession, setChosenSession] = useState<number | "" | null>(null);
  const sessionId = chosenSession ?? currentSessionId;
  const [teacherId, setTeacherId] = useState<number | "">("");
  const [view, setView] = useState<"week" | "day">("week");
  const [day, setDay] = useState<WeekDay>(todayWeekDay());
  const [open, setOpen] = useState<TimetableEntry | null>(null);
  const [form, setForm] = useState<FormSeed | null>(null);
  const [deleting, setDeleting] = useState<TimetableEntry | null>(null);
  const ready = Boolean(sessionId && teacherId);

  const loader = useCallback(
    () => timetableService().teacherWeekly(Number(teacherId), Number(sessionId)).then((grid) => [grid]),
    [teacherId, sessionId],
  );
  const week = useOptions(ready ? loader : null);
  const grid = week.options[0] ?? null;
  const periods = grid ? grid.reduce((sum, item) => sum + item.entries.length, 0) : 0;
  const clashes = grid ? conflictIds(grid).size : 0;

  return (
    <>
      <div className="school-filters">
        <select aria-label="Academic session" value={sessionId} onChange={(event) => setChosenSession(event.target.value ? Number(event.target.value) : "")}>
          <option value="">{sessions.loading ? "Loading sessions…" : "Choose a session"}</option>
          {sessions.options.map((row) => (
            <option key={row.id} value={row.id}>
              {sessionLabel(row)}
            </option>
          ))}
        </select>
        <select aria-label="Teacher" value={teacherId} onChange={(event) => setTeacherId(event.target.value ? Number(event.target.value) : "")}>
          <option value="">{teachers.loading ? "Loading teachers…" : "Choose a teacher"}</option>
          {teachers.options.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <div className="teach-segmented" role="group" aria-label="View">
          <button type="button" className={view === "week" ? "is-active" : ""} aria-pressed={view === "week"} onClick={() => setView("week")}>
            Weekly
          </button>
          <button type="button" className={view === "day" ? "is-active" : ""} aria-pressed={view === "day"} onClick={() => setView("day")}>
            Daily
          </button>
        </div>
        {view === "day" ? (
          <select aria-label="Day" value={day} onChange={(event) => setDay(event.target.value as WeekDay)}>
            {WEEK_DAYS.map((item) => (
              <option key={item} value={item}>
                {DAY_LABEL[item]}
                {item === todayWeekDay() ? " (today)" : ""}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <ErrorAlert error={teachers.error ?? week.error} onRetry={() => void (teachers.error ? teachers.reload() : week.reload())} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">Choose a session and a teacher to see their schedule.</div>
        </div>
      ) : week.error ? null : (
        <>
          {grid ? (
            <div className="teach-summary">
              <Chip tone="blue">{periods} periods a week</Chip>
              {clashes ? <Chip tone="red">{clashes} periods overlap — open one to fix it</Chip> : <Chip tone="green">No clashes</Chip>}
            </div>
          ) : null}
          <WeekGridView
            grid={grid}
            loading={week.loading}
            show="teacher"
            days={view === "day" ? [day] : undefined}
            emptyText={view === "day" ? `No periods on ${DAY_LABEL[day]}.` : "This teacher has no periods in this session."}
            onOpen={setOpen}
          />
          <AvailabilityCheck teacherId={Number(teacherId)} sessionId={Number(sessionId)} />
        </>
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
          seed={form}
          onClose={() => setForm(null)}
          onSaved={() => {
            setForm(null);
            toast("success", "Period updated.");
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

/** Asks the server whether the teacher is free for a day and time range. */
function AvailabilityCheck({ teacherId, sessionId }: { teacherId: number; sessionId: number }) {
  const [day, setDay] = useState<WeekDay>(todayWeekDay());
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<Availability | null>(null);
  const [problem, setProblem] = useState("");

  async function check() {
    setResult(null);
    if (!/^\d{2}:\d{2}$/.test(start) || !/^\d{2}:\d{2}$/.test(end)) {
      setProblem("Enter both times as HH:MM, e.g. 10:00.");
      return;
    }
    if (end <= start) {
      setProblem("End time must be after the start time.");
      return;
    }
    setProblem("");
    setChecking(true);
    try {
      setResult(await timetableService().availability(teacherId, { sessionYearId: sessionId, day, start, end }));
    } catch (caught) {
      setProblem(errorMessage(caught, "Unable to check availability."));
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="resource-card teach-availability" aria-labelledby="availability-title">
      <h2 id="availability-title">Check availability</h2>
      <form
        className="teach-inline-form"
        onSubmit={(event) => {
          event.preventDefault();
          void check();
        }}
      >
        <div className="form-field">
          <label htmlFor="av-day">Day</label>
          <select id="av-day" value={day} onChange={(event) => setDay(event.target.value as WeekDay)}>
            {WEEK_DAYS.map((item) => (
              <option key={item} value={item}>
                {DAY_LABEL[item]}
              </option>
            ))}
          </select>
        </div>
        <TextField id="av-start" label="From" placeholder="10:00" value={start} onChange={setStart} />
        <TextField id="av-end" label="To" placeholder="10:45" value={end} onChange={setEnd} />
        <button className="btn-pill btn-pill-green" type="submit" disabled={checking}>
          {checking ? "Checking…" : "Check"}
        </button>
      </form>
      {problem ? (
        <p className="field-error" role="alert">
          {problem}
        </p>
      ) : null}
      {result ? (
        result.available ? (
          <p role="status">
            <Chip tone="green">Free</Chip> The teacher has no period on {DAY_LABEL[day]} between {start} and {end}.
          </p>
        ) : (
          <div role="status">
            <p>
              <Chip tone="red">Busy</Chip> Already teaching at that time:
            </p>
            <ul className="teach-list">
              {result.conflicts.map((item) => (
                <li key={`${item.id}-${item.start_time}`}>
                  {item.start_time}–{item.end_time} · {item.subject_name} · {item.class_name} {item.section_name}
                </li>
              ))}
            </ul>
          </div>
        )
      ) : null}
    </section>
  );
}
