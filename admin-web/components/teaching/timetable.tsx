"use client";

import { useCallback, useMemo, useState } from "react";
import { ConfirmDialog } from "@/components/billing/ConfirmDialog";
import { SelectField, TextField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { EMPTY_PLACEMENT, PlacementFields, SubjectTeacherFields, type PlacementValue } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { timetableService } from "@/lib/teaching/timetable";
import { WEEK_DAYS, type TimetableEntry, type TimetableInput, type WeekDay, type WeekGrid } from "@/lib/teaching/types";

export const DAY_LABEL: Record<WeekDay, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
};

export const TIMETABLE_TABS = [
  { href: "/school/timetable", label: "Weekly timetable" },
  { href: "/school/timetable/list", label: "All periods" },
  { href: "/school/timetable/teachers", label: "Teacher schedules" },
];

export const TIMETABLE_LIVE_NOTE = "Connected to the school's server. The server has no classroom field yet, so the classroom is saved at the start of the period's note.";

/** The day of the week for today, or Monday on Sunday. */
export function todayWeekDay(): WeekDay {
  const index = new Date().getDay(); // 0 = Sunday
  return index === 0 ? "monday" : WEEK_DAYS[index - 1];
}

export type FormSeed = { entry?: TimetableEntry; placement?: PlacementValue; day?: WeekDay; teacherId?: number };

/** Add or edit one period. Backend overlap conflicts (409) show at the top of the form. */
export function TimetableForm({ seed, onClose, onSaved }: { seed: FormSeed; onClose: () => void; onSaved: (entry: TimetableEntry, created: boolean) => void }) {
  const entry = seed.entry;
  const [placement, setPlacement] = useState<PlacementValue>(
    entry ? { session_year_id: String(entry.session_year_id), class_id: String(entry.class_id), class_section_id: String(entry.class_section_id) } : seed.placement ?? EMPTY_PLACEMENT,
  );
  const [subjectId, setSubjectId] = useState(entry ? String(entry.subject_id) : "");
  const [teacherId, setTeacherId] = useState(entry ? String(entry.teacher_user_id) : seed.teacherId ? String(seed.teacherId) : "");
  const [day, setDay] = useState<WeekDay | "">(entry?.day ?? seed.day ?? "");
  const [start, setStart] = useState(entry?.start_time ?? "");
  const [end, setEnd] = useState(entry?.end_time ?? "");
  const [note, setNote] = useState(entry?.note ?? "");
  const [room, setRoom] = useState(entry?.room ?? "");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  const onPlacement = useCallback((value: PlacementValue) => setPlacement(value), []);
  const onTeacher = useCallback((value: string) => setTeacherId(value), []);

  async function submit() {
    const invalid: Record<string, string> = {};
    if (!placement.session_year_id) invalid.session_year_id = "Choose an academic session.";
    if (!placement.class_id) invalid.class_id = "Choose a class.";
    if (!placement.class_section_id) invalid.class_section_id = "Choose a section.";
    if (!subjectId) invalid.subject_id = "Choose a subject.";
    if (!teacherId) invalid.teacher_user_id = "Choose a teacher.";
    if (!day) invalid.day = "Choose a day.";
    if (!start) invalid.start_time = "Enter a start time.";
    if (!end) invalid.end_time = "Enter an end time.";
    else if (start && end <= start) invalid.end_time = "End time must be after the start time.";
    if (Object.keys(invalid).length) {
      errors.setFieldErrors(invalid);
      errors.setFormError("");
      return;
    }
    errors.clear();
    setSaving(true);
    const input: TimetableInput = {
      session_year_id: Number(placement.session_year_id),
      class_section_id: Number(placement.class_section_id),
      subject_id: Number(subjectId),
      teacher_user_id: Number(teacherId),
      day: day as WeekDay,
      start_time: start,
      end_time: end,
      note: note || null,
      room: room || null,
    };
    try {
      const saved = entry ? await timetableService().update(entry.id, input) : await timetableService().create(input);
      onSaved(saved, !entry);
    } catch (caught) {
      errors.fromError(caught, "Unable to save the period.");
      setSaving(false);
    }
  }

  return (
    <FormModal
      title={entry ? "Edit period" : "Add period"}
      description="A section and a teacher can't have two periods at the same time."
      error={errors.formError}
      saving={saving}
      submitLabel={entry ? "Save changes" : "Add period"}
      wide
      onSubmit={() => void submit()}
      onClose={onClose}
    >
      <PlacementFields idPrefix="tt" value={placement} onChange={onPlacement} errors={errors.fieldErrors} />
      <SubjectTeacherFields idPrefix="tt" placement={placement} subjectId={subjectId} teacherId={teacherId} onSubject={setSubjectId} onTeacher={onTeacher} errors={errors.fieldErrors} />
      <SelectField
        id="tt-day"
        label="Day"
        required
        placeholder="Choose a day"
        value={day}
        onChange={(v) => setDay(v as WeekDay)}
        options={WEEK_DAYS.map((d) => ({ value: d, label: DAY_LABEL[d] }))}
        error={errors.fieldErrors.day}
      />
      <TextField id="tt-start" label="Start time" type="text" required placeholder="08:30" value={start} onChange={setStart} error={errors.fieldErrors.start_time} hint="24-hour time, e.g. 08:30" />
      <TextField id="tt-end" label="End time" type="text" required placeholder="09:15" value={end} onChange={setEnd} error={errors.fieldErrors.end_time} hint="24-hour time, e.g. 09:15" />
      <TextField id="tt-room" label="Classroom" maxLength={64} placeholder="Room 12" value={room} onChange={setRoom} />
      <TextField id="tt-note" label="Note" span maxLength={255} value={note} onChange={setNote} />
    </FormModal>
  );
}

/** Confirm and delete a period. */
export function DeletePeriod({ entry, onClose, onDeleted }: { entry: TimetableEntry; onClose: () => void; onDeleted: () => void }) {
  const toast = useToast();
  const [pending, setPending] = useState(false);
  return (
    <ConfirmDialog
      title="Delete this period?"
      body={`${entry.subject_name} with ${entry.teacher_name}, ${DAY_LABEL[entry.day]} ${entry.start_time}–${entry.end_time}, will be removed from ${entry.class_name} ${entry.section_name}.`}
      confirmLabel="Delete period"
      tone="danger"
      pending={pending}
      onCancel={onClose}
      onConfirm={async () => {
        setPending(true);
        try {
          await timetableService().remove(entry.id);
          toast("success", "Period deleted.");
          onDeleted();
        } catch (caught) {
          toast("error", errorMessage(caught, "Unable to delete the period."));
          onClose();
        } finally {
          setPending(false);
        }
      }}
    />
  );
}

/** Weekly grid: one column per day on wide screens, stacked days on phones. */
export function WeekGridView({
  grid,
  loading,
  show,
  onOpen,
  onAdd,
  emptyText,
  days,
}: {
  grid: WeekGrid | null;
  loading: boolean;
  show: "teacher" | "class";
  onOpen?: (entry: TimetableEntry) => void;
  onAdd?: (day: WeekDay) => void;
  emptyText: string;
  /** Limit to these days (the daily view passes one). */
  days?: WeekDay[];
}) {
  const shown = useMemo(() => (grid ?? WEEK_DAYS.map((day) => ({ day, entries: [] as TimetableEntry[] }))).filter((item) => !days || days.includes(item.day)), [grid, days]);
  const total = shown.reduce((sum, day) => sum + day.entries.length, 0);
  const clashes = useMemo(() => conflictIds(shown), [shown]);
  if (loading && !grid) return <div className="resource-card"><div className="skeleton" style={{ height: 220 }} /></div>;
  return (
    <div className={`teach-week${loading ? " is-stale" : ""}${days?.length === 1 ? " is-single" : ""}`}>
      {total === 0 ? <div className="empty-state teach-week-empty">{emptyText}</div> : null}
      {shown.map(({ day, entries }) => (
        <section key={day} className="teach-day" aria-label={DAY_LABEL[day]}>
          <header>
            <h3>{DAY_LABEL[day]}</h3>
            {onAdd ? (
              <button className="link-btn" type="button" onClick={() => onAdd(day)}>
                + Add<span className="acad-sr"> period on {DAY_LABEL[day]}</span>
              </button>
            ) : null}
          </header>
          {entries.length === 0 ? <p className="muted teach-day-empty">No periods</p> : null}
          <ul>
            {entries.map((entry) => (
              <li key={entry.id}>
                <button className={`teach-period${clashes.has(entry.id) ? " is-conflict" : ""}`} type="button" onClick={() => onOpen?.(entry)} disabled={!onOpen} style={{ borderLeftColor: subjectColor(entry.subject_id) }}>
                  <span className="teach-period-time">
                    {entry.start_time}–{entry.end_time}
                  </span>
                  <strong>{entry.subject_name}</strong>
                  <span className="muted">
                    {show === "class" ? entry.teacher_name : `${entry.class_name} ${entry.section_name}`}
                    {entry.room ? ` · ${entry.room}` : ""}
                  </span>
                  {clashes.has(entry.id) ? <span className="teach-conflict-text">Overlaps another period</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

const PALETTE = ["#16a34a", "#2563eb", "#d97706", "#9333ea", "#db2777", "#0891b2", "#65a30d", "#dc2626"];

/** A steady colour per subject so periods are easy to tell apart. */
export function subjectColor(subjectId: number): string {
  return PALETTE[Math.abs(subjectId) % PALETTE.length];
}

/** Ids of periods that overlap another period on the same day. */
export function conflictIds(grid: WeekGrid): Set<number> {
  const ids = new Set<number>();
  for (const { entries } of grid) {
    for (let i = 0; i < entries.length; i += 1) {
      for (let j = i + 1; j < entries.length; j += 1) {
        if (entries[i].start_time < entries[j].end_time && entries[j].start_time < entries[i].end_time) {
          ids.add(entries[i].id);
          ids.add(entries[j].id);
        }
      }
    }
  }
  return ids;
}

/** Details of one period with Edit and Delete. */
export function PeriodDialog({ entry, onEdit, onDelete, onClose }: { entry: TimetableEntry; onEdit: () => void; onDelete: () => void; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="period-title">
        <h2 id="period-title">{entry.subject_name}</h2>
        <dl className="teach-facts">
          <div><dt>Class</dt><dd>{entry.class_name} {entry.section_name}</dd></div>
          <div><dt>Teacher</dt><dd>{entry.teacher_name}</dd></div>
          <div><dt>When</dt><dd>{DAY_LABEL[entry.day]}, {entry.start_time}–{entry.end_time}</dd></div>
          {entry.room ? <div><dt>Classroom</dt><dd>{entry.room}</dd></div> : null}
          {entry.note ? <div><dt>Note</dt><dd>{entry.note}</dd></div> : null}
        </dl>
        <div className="page-actions">
          <button className="btn-pill btn-pill-green" type="button" onClick={onEdit}>Edit</button>
          <button className="btn-pill btn-pill-danger" type="button" onClick={onDelete}>Delete</button>
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
