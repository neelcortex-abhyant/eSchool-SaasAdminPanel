"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { useOptions } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ATTENDANCE_LIVE_NOTE, ATTENDANCE_TABS, AttendanceChip, todayIso } from "@/components/teaching/attendance";
import { Chip, Stat, TeachingPage } from "@/components/teaching/Frame";
import { EMPTY_PLACEMENT, PlacementFields, type PlacementValue } from "@/components/teaching/Pickers";
import { errorMessage } from "@/lib/academics";
import { attendanceRoster, attendanceService, attendanceSupport, STATUS_LABEL, tally, type MarkResult } from "@/lib/teaching/attendance";
import { sectionMap } from "@/lib/teaching/lookups";
import type { AttendanceRecord, AttendanceStatus } from "@/lib/teaching/types";
import { IconCheck } from "@/lib/icons";

export default function MarkAttendancePage() {
  return (
    <TeachingPage
      module="attendance"
      title="Mark attendance"
      description="Choose a section and date, set each student's status and save."
      icon={<IconCheck width={18} height={18} />}
      tabs={ATTENDANCE_TABS}
      liveNote={ATTENDANCE_LIVE_NOTE}
    >
      <Suspense fallback={<div className="skeleton" style={{ height: 120 }} />}>
        <MarkBody />
      </Suspense>
    </TeachingPage>
  );
}

type Row = { student_id: number; name: string; admission_no: string; roll: number | null; status: AttendanceStatus | ""; remark: string; saved: AttendanceRecord | null };

function MarkBody() {
  const toast = useToast();
  const params = useSearchParams();
  const support = attendanceSupport();
  const statuses: AttendanceStatus[] = support.leave ? ["present", "absent", "late", "leave"] : ["present", "absent", "late"];
  const [placement, setPlacement] = useState<PlacementValue>(EMPTY_PLACEMENT);
  const [date, setDate] = useState(() => {
    const value = params.get("date") ?? "";
    return /^\d{4}-\d{2}-\d{2}$/.test(value) && value <= todayIso() ? value : todayIso();
  });
  const [rows, setRows] = useState<Row[]>([]);
  const [results, setResults] = useState<Map<number, MarkResult>>(new Map());
  const [saving, setSaving] = useState(false);
  const [lockBusy, setLockBusy] = useState(false);
  const onPlacement = useCallback((value: PlacementValue) => setPlacement(value), []);

  // A dashboard link passes ?section=; fill in its class once the sections are known.
  // Waits for the session to be filled in first, which would otherwise clear the class and section.
  const linkApplied = useRef(false);
  useEffect(() => {
    const section = Number(params.get("section"));
    if (!section || !placement.session_year_id || linkApplied.current) return;
    linkApplied.current = true;
    void sectionMap().then((map) => {
      const found = map.get(section);
      if (found) setPlacement((current) => ({ ...current, class_id: String(found.class_id), class_section_id: String(section) }));
    });
  }, [params, placement.session_year_id]);

  const sessionId = Number(placement.session_year_id);
  const sectionId = Number(placement.class_section_id);
  const ready = Boolean(sessionId && sectionId && date);

  const loader = useCallback(async () => {
    const [roster, records, locks] = await Promise.all([
      attendanceRoster(sessionId, sectionId),
      attendanceService().records({ sessionYearId: sessionId, classSectionId: sectionId, from: date, to: date }),
      attendanceService().locks(sectionId),
    ]);
    return [{ roster: roster.filter((student) => student.status === 1), records, locked: locks.some((lock) => lock.date === date && lock.locked) }];
  }, [sessionId, sectionId, date]);
  const state = useOptions(ready ? loader : null);
  const data = state.options[0] ?? null;

  useEffect(() => {
    if (!data) {
      setRows([]);
      return;
    }
    const byStudent = new Map(data.records.map((record) => [record.student_id, record]));
    setRows(
      [...data.roster]
        .sort((a, b) => (a.roll_number ?? 9999) - (b.roll_number ?? 9999) || a.name.localeCompare(b.name))
        .map((student) => {
          const saved = byStudent.get(student.id) ?? null;
          return { student_id: student.id, name: student.name, admission_no: student.admission_no, roll: student.roll_number, status: saved?.status ?? "", remark: saved?.remark ?? "", saved };
        }),
    );
    setResults(new Map());
  }, [data]);

  const locked = data?.locked ?? false;
  // On the live server a saved record can't be changed, so those rows are read-only.
  const editable = (row: Row) => !locked && (!row.saved || support.correction);
  const changed = rows.filter((row) => editable(row) && row.status && (!row.saved || row.saved.status !== row.status || (row.saved.remark ?? "") !== row.remark.trim()));
  const unmarked = rows.filter((row) => !row.status).length;
  const counts = useMemo(() => tally(rows.filter((row) => row.status).map((row) => ({ status: row.status as AttendanceStatus }))), [rows]);

  function setRow(studentId: number, patch: Partial<Row>) {
    setRows((list) => list.map((row) => (row.student_id === studentId ? { ...row, ...patch } : row)));
  }

  function markAll(status: AttendanceStatus) {
    setRows((list) => list.map((row) => (editable(row) && !row.saved ? { ...row, status } : row)));
  }

  async function save() {
    if (!changed.length) {
      toast("error", unmarked ? "Choose a status for at least one student." : "Nothing has changed.");
      return;
    }
    setSaving(true);
    try {
      const outcome = await attendanceService().mark(
        sessionId,
        sectionId,
        date,
        changed.map((row) => ({ student_id: row.student_id, status: row.status as AttendanceStatus, remark: row.remark.trim() || null })),
      );
      const map = new Map(outcome.map((result) => [result.student_id, result]));
      setResults(map);
      const saved = outcome.filter((result) => result.ok).length;
      const skipped = outcome.filter((result) => result.skipped).length;
      const failed = outcome.length - saved - skipped;
      if (failed) toast("error", `${saved} saved, ${failed} failed${skipped ? `, ${skipped} already marked` : ""}. Failed rows are highlighted.`);
      else toast("success", `Attendance saved for ${saved} student${saved === 1 ? "" : "s"}${skipped ? ` (${skipped} were already marked)` : ""}.`);
      await state.reload();
      setResults(map);
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to save attendance."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleLock() {
    setLockBusy(true);
    try {
      await attendanceService().setLock(sectionId, date, !locked);
      toast("success", locked ? "Attendance unlocked for changes." : "Attendance locked for this date.");
      void state.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the lock."));
    } finally {
      setLockBusy(false);
    }
  }

  return (
    <>
      <section className="resource-card">
        <div className="resource-fields">
          <PlacementFields idPrefix="att" value={placement} onChange={onPlacement} />
          <div className="form-field">
            <label htmlFor="att-date">Date *</label>
            <input id="att-date" type="date" value={date} max={todayIso()} onChange={(event) => setDate(event.target.value)} />
          </div>
        </div>
      </section>
      <ErrorAlert error={state.error} onRetry={() => void state.reload()} />
      {!ready ? (
        <div className="resource-card">
          <div className="empty-state">Choose a session, class, section and date to load the students.</div>
        </div>
      ) : state.loading && !data ? (
        <div className="resource-card">
          <div className="skeleton" style={{ height: 200 }} />
        </div>
      ) : data && rows.length === 0 ? (
        <div className="resource-card">
          <div className="empty-state">No active students in this section.</div>
        </div>
      ) : data ? (
        <>
          <div className="teach-stats">
            <Stat label="Students" value={rows.length} />
            <Stat label="Present" value={counts.present} tone="green" />
            <Stat label="Absent" value={counts.absent} tone="red" />
            <Stat label="Late" value={counts.late} tone="amber" />
            {support.leave ? <Stat label="Leave" value={counts.leave} tone="blue" /> : null}
            <Stat label="Not marked" value={unmarked} tone="grey" />
          </div>
          {locked ? <div className="alert alert-info">Attendance for this date is locked. Unlock it to make changes.</div> : null}
          {!support.correction && rows.some((row) => row.saved) ? (
            <div className="alert alert-info">Students already marked for this date are shown read-only; the server can't change saved attendance yet.</div>
          ) : null}
          <div className="teach-toolbar">
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={locked} onClick={() => markAll("present")}>
              Mark all present
            </button>
            <button className="btn-pill btn-pill-green-soft" type="button" disabled={locked} onClick={() => markAll("absent")}>
              Mark all absent
            </button>
            {support.locks ? (
              <button className="btn-pill btn-pill-green-soft" type="button" disabled={lockBusy} onClick={() => void toggleLock()}>
                {locked ? "Unlock date" : "Lock date"}
              </button>
            ) : null}
          </div>
          <div className="resource-card">
            <ul className="teach-roster" aria-label="Students">
              {rows.map((row) => {
                const result = results.get(row.student_id);
                const canEdit = editable(row);
                return (
                  <li key={row.student_id} className={result && !result.ok && !result.skipped ? "has-error" : undefined}>
                    <div className="teach-roster-name">
                      <strong>
                        {row.roll !== null ? `${row.roll}. ` : ""}
                        {row.name}
                      </strong>
                      <span className="muted">{row.admission_no}</span>
                      {row.saved && row.saved.history.length ? <span className="muted">Corrected {row.saved.history.length}×, was {STATUS_LABEL[row.saved.history[0].status]}</span> : null}
                      {result && !result.ok ? <span className={result.skipped ? "muted" : "field-error"}>{result.message}</span> : null}
                    </div>
                    {canEdit ? (
                      <div className="teach-status-group" role="radiogroup" aria-label={`Status for ${row.name}`}>
                        {statuses.map((status) => (
                          <label key={status} className={`teach-status-option is-${status}${row.status === status ? " is-checked" : ""}`}>
                            <input type="radio" name={`status-${row.student_id}`} value={status} checked={row.status === status} onChange={() => setRow(row.student_id, { status })} />
                            {STATUS_LABEL[status]}
                          </label>
                        ))}
                      </div>
                    ) : row.status ? (
                      <div>
                        <AttendanceChip status={row.status} /> {row.saved ? <Chip tone="grey">Saved</Chip> : null}
                      </div>
                    ) : null}
                    <input
                      className="teach-remark"
                      type="text"
                      aria-label={`Remark for ${row.name}`}
                      placeholder="Remark (optional)"
                      maxLength={255}
                      value={row.remark}
                      disabled={!canEdit}
                      onChange={(event) => setRow(row.student_id, { remark: event.target.value })}
                    />
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="teach-savebar">
            <span className="muted">
              {changed.length} change{changed.length === 1 ? "" : "s"} to save{unmarked ? ` · ${unmarked} not marked` : ""}
            </span>
            <button className="btn-pill btn-pill-green" type="button" disabled={saving || locked || !changed.length} onClick={() => void save()}>
              {saving ? "Saving…" : "Save attendance"}
            </button>
          </div>
        </>
      ) : null}
    </>
  );
}
