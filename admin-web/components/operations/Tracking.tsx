"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DataTable, Pagination, type Column } from "@/components/academics/DataTable";
import { ErrorAlert } from "@/components/academics/ErrorAlert";
import { SelectField, TextAreaField } from "@/components/academics/Fields";
import { FormModal } from "@/components/academics/FormModal";
import { useFormErrors, useOptions, usePagedList } from "@/components/academics/hooks";
import { useToast } from "@/components/academics/Toasts";
import { ExtrasPage, StudentSearch } from "@/components/extras/Frame";
import { Chip, Stat, type ChipTone } from "@/components/teaching/Frame";
import { downloadText, toCsv } from "@/lib/operations/export";
import { isOperationsLive, OPERATIONS_SAMPLE_NOTE, TRACKING_LIVE_NOTE } from "@/lib/operations/mode";
import { ageLabel, boardingRate, freshness, trackingService, type Freshness } from "@/lib/operations/tracking";
import type { BoardingStatus, TransportAttendance, Trip, TripStatus, VehicleLocation } from "@/lib/operations/types";
import { transportService } from "@/lib/ops/transport";
import { staffDirectory } from "@/lib/extras/api";
import { errorMessage } from "@/lib/academics";
import type { StudentRow } from "@/lib/people";
import { IconPackage } from "@/lib/icons";

const BusMap = dynamic(() => import("@/components/operations/BusMap").then((mod) => mod.BusMap), {
  ssr: false,
  loading: () => <div className="bus-map skeleton" />,
});

export const TRACKING_TABS = [
  { href: "/school/transport/tracking", label: "Live tracking" },
  { href: "/school/transport/trips", label: "Trips" },
  { href: "/school/transport/boarding", label: "Boarding" },
  { href: "/school/transport/reports", label: "Reports" },
];

const icon = <IconPackage width={18} height={18} />;
const note = () => (isOperationsLive("tracking") ? TRACKING_LIVE_NOTE : OPERATIONS_SAMPLE_NOTE.tracking);

export function directionLabel(direction: Trip["direction"]): string {
  return direction === "pickup" ? "Morning pickup" : direction === "drop" ? "Afternoon drop" : "Trip";
}

export const TRIP_STATUS: Record<TripStatus, { label: string; tone: ChipTone }> = {
  scheduled: { label: "Scheduled", tone: "blue" },
  active: { label: "On the road", tone: "green" },
  completed: { label: "Completed", tone: "grey" },
  cancelled: { label: "Cancelled", tone: "red" },
};

export const BOARDING_STATUS: Record<BoardingStatus, { label: string; tone: ChipTone }> = {
  boarded: { label: "Boarded", tone: "green" },
  dropped: { label: "Dropped off", tone: "green" },
  absent: { label: "Absent", tone: "red" },
  pending: { label: "Not yet", tone: "amber" },
};

const FRESHNESS: Record<Freshness, { label: string; tone: ChipTone }> = {
  live: { label: "Live", tone: "green" },
  stale: { label: "Stale", tone: "amber" },
  offline: { label: "Offline", tone: "grey" },
};

function time(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function todayLocal(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function daysAgo(days: number): string {
  const day = new Date(Date.now() - days * 86_400_000);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

/** Routes and vehicles for the filters. */
function useFleetOptions() {
  const routes = useOptions(useCallback(() => transportService().routes(), []));
  const vehicles = useOptions(useCallback(() => transportService().vehicles(), []));
  return {
    routes: routes.options.map((row) => ({ value: String(row.id), label: row.name })),
    vehicles: vehicles.options.map((row) => ({ value: String(row.id), label: row.registration_no })),
  };
}

// ---------- Live tracking ----------

const REFRESH_SECONDS = 15;

export function TrackingDashboard() {
  return (
    <ExtrasPage title="Live bus tracking" description="Where each school bus is now, its trip and when it last reported." icon={icon} tabs={TRACKING_TABS} note={note()}>
      <TrackingBody />
    </ExtrasPage>
  );
}

/** Buses matching the filters; freshness is worked out against `now`. */
export function filterLocations(rows: VehicleLocation[], filter: { routeId: string; vehicleId: string; status: string }, now = Date.now()): VehicleLocation[] {
  return rows.filter((row) => {
    if (filter.routeId && String(row.route_id) !== filter.routeId) return false;
    if (filter.vehicleId && String(row.vehicle_id) !== filter.vehicleId) return false;
    if (!filter.status) return true;
    if (filter.status === "offline" || filter.status === "stale") return freshness(row.recorded_at, now) === filter.status;
    if (filter.status === "none") return !row.trip_status;
    return row.trip_status === filter.status;
  });
}

function TrackingBody() {
  const options = useFleetOptions();
  const state = useOptions(useCallback(() => trackingService().locations(), []));
  const [filter, setFilter] = useState({ routeId: "", vehicleId: "", status: "" });
  const [selected, setSelected] = useState<number | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [, tick] = useState(0);
  const { reload } = state;

  useEffect(() => {
    if (!state.loading && !state.error) setUpdated(new Date());
  }, [state.loading, state.error, state.options]);

  // Refresh positions every 15 seconds while the tab is visible, and keep the "x min ago" labels current.
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void reload();
      tick((value) => value + 1);
    }, REFRESH_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [reload]);

  const rows = filterLocations(state.options, filter);
  const counts = useMemo(() => {
    return {
      onRoad: state.options.filter((row) => row.trip_status === "active").length,
      live: state.options.filter((row) => freshness(row.recorded_at) === "live").length,
      stale: state.options.filter((row) => freshness(row.recorded_at) === "stale").length,
      offline: state.options.filter((row) => freshness(row.recorded_at) === "offline").length,
    };
  }, [state.options]);

  return (
    <>
      <div className="school-filters">
        <select aria-label="Route" value={filter.routeId} onChange={(event) => setFilter({ ...filter, routeId: event.target.value })}>
          <option value="">All routes</option>
          {options.routes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <select aria-label="Vehicle" value={filter.vehicleId} onChange={(event) => setFilter({ ...filter, vehicleId: event.target.value })}>
          <option value="">All vehicles</option>
          {options.vehicles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <select aria-label="Trip status" value={filter.status} onChange={(event) => setFilter({ ...filter, status: event.target.value })}>
          <option value="">Any status</option>
          <option value="active">On the road</option>
          <option value="scheduled">Scheduled</option>
          <option value="completed">Completed</option>
          <option value="none">No trip today</option>
          <option value="stale">Stale location</option>
          <option value="offline">Offline</option>
        </select>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={() => void reload()} disabled={state.loading}>
          {state.loading ? "Refreshing…" : "Refresh"}
        </button>
        <span className="muted">{updated ? `Updated ${updated.toLocaleTimeString("en-IN")} · refreshes every ${REFRESH_SECONDS} s` : ""}</span>
      </div>
      <div className="teach-stats">
        <Stat label="On the road" value={counts.onRoad} tone="green" />
        <Stat label="Reporting live" value={counts.live} tone="blue" />
        <Stat label="Stale (over 5 min)" value={counts.stale} tone={counts.stale ? "amber" : "grey"} />
        <Stat label="Offline (over 30 min)" value={counts.offline} tone={counts.offline ? "red" : "grey"} />
      </div>
      <ErrorAlert error={state.error} onRetry={() => void reload()} />
      <div className="bus-layout">
        <section className="resource-card bus-map-card" aria-label="Map">
          <BusMap locations={rows} selected={selected} onSelect={setSelected} />
        </section>
        <section className="resource-card bus-list" aria-label="Buses">
          {state.loading && !state.options.length ? <div className="skeleton" style={{ height: 200 }} /> : null}
          {!state.loading && !rows.length ? <div className="empty-state">{state.options.length ? "No bus matches these filters." : "No vehicles yet. Add them under Transport → Vehicles."}</div> : null}
          <ul>
            {rows.map((row) => {
              const fresh = freshness(row.recorded_at);
              return (
                <li key={row.vehicle_id}>
                  <button type="button" className={`bus-row${selected === row.vehicle_id ? " is-selected" : ""}`} onClick={() => setSelected(row.vehicle_id)} aria-pressed={selected === row.vehicle_id}>
                    <span className="bus-row-head">
                      <strong>{row.registration_no}</strong>
                      <Chip tone={FRESHNESS[fresh].tone}>{FRESHNESS[fresh].label}</Chip>
                    </span>
                    <span className="muted">{row.route_name ?? "No route"} · {row.driver_name ?? "No driver"}</span>
                    <span className="bus-row-meta">
                      {row.trip_status ? <Chip tone={TRIP_STATUS[row.trip_status].tone}>{TRIP_STATUS[row.trip_status].label}</Chip> : <span className="muted">No trip today</span>}
                      <span className="muted">
                        {row.latitude.toFixed(5)}, {row.longitude.toFixed(5)}
                        {row.speed_kmph ? ` · ${row.speed_kmph} km/h` : ""} · {ageLabel(row.recorded_at)}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </>
  );
}

// ---------- Trips ----------

export function TripsPage() {
  const [scheduling, setScheduling] = useState(false);
  return (
    <ExtrasPage
      title="Trips"
      description="Scheduled, running and finished bus trips, with their vehicle, driver and helper."
      icon={icon}
      tabs={TRACKING_TABS}
      note={note()}
      actions={
        trackingService().canManageTrips ? (
          <button className="btn-pill btn-pill-green" type="button" onClick={() => setScheduling(true)}>
            Schedule trip
          </button>
        ) : undefined
      }
    >
      <TripsBody scheduling={scheduling} setScheduling={setScheduling} />
    </ExtrasPage>
  );
}

function TripsBody({ scheduling, setScheduling }: { scheduling: boolean; setScheduling: (value: boolean) => void }) {
  const toast = useToast();
  const options = useFleetOptions();
  const [busy, setBusy] = useState<number | null>(null);
  const [status, setStatus] = useState<TripStatus | "">("");
  const [routeId, setRouteId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(todayLocal());
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<Trip | null>(null);
  const list = usePagedList(
    useCallback(() => trackingService().trips({ page, pageSize: 20, status, routeId: routeId ? Number(routeId) : "", vehicleId: vehicleId ? Number(vehicleId) : "", from, to }), [page, status, routeId, vehicleId, from, to]),
  );
  const columns: Column<Trip>[] = [
    { key: "date", label: "Date", render: (row) => <div><strong>{row.trip_date}</strong><div className="muted">{directionLabel(row.direction)}{row.scheduled_start ? ` · ${row.scheduled_start}` : ""}</div></div> },
    { key: "route", label: "Route", render: (row) => row.route_name },
    { key: "vehicle", label: "Vehicle", render: (row) => <div>{row.registration_no}<div className="muted">{row.driver_name ?? "No driver"}{row.helper_name ? ` · ${row.helper_name}` : ""}</div></div> },
    { key: "status", label: "Status", render: (row) => <Chip tone={TRIP_STATUS[row.status].tone}>{TRIP_STATUS[row.status].label}</Chip> },
    { key: "times", label: "Started – ended", render: (row) => `${time(row.started_at)} – ${time(row.ended_at)}` },
    { key: "riders", label: "Boarded", render: (row) => (row.status === "scheduled" ? `— / ${row.expected}` : `${row.boarded} / ${row.expected}`) },
  ];
  const reset = () => setPage(1);
  async function act(trip: Trip, action: "start" | "complete") {
    setBusy(trip.id);
    try {
      if (action === "start") await trackingService().startTrip(trip.id);
      else await trackingService().completeTrip(trip.id);
      toast("success", action === "start" ? `${trip.route_name}: trip started.` : `${trip.route_name}: trip completed.`);
      void list.reload();
    } catch (caught) {
      toast("error", errorMessage(caught, "Unable to change the trip."));
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      <div className="school-filters">
        <select aria-label="Trip status" value={status} onChange={(event) => { setStatus(event.target.value as TripStatus | ""); reset(); }}>
          <option value="">All trips</option>
          {(Object.keys(TRIP_STATUS) as TripStatus[]).map((key) => <option key={key} value={key}>{TRIP_STATUS[key].label}</option>)}
        </select>
        <select aria-label="Route" value={routeId} onChange={(event) => { setRouteId(event.target.value); reset(); }}>
          <option value="">All routes</option>
          {options.routes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <select aria-label="Vehicle" value={vehicleId} onChange={(event) => { setVehicleId(event.target.value); reset(); }}>
          <option value="">All vehicles</option>
          {options.vehicles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <label className="ops-filter-label">From <input type="date" value={from} max={to} onChange={(event) => { setFrom(event.target.value); reset(); }} /></label>
        <label className="ops-filter-label">To <input type="date" value={to} min={from} onChange={(event) => { setTo(event.target.value); reset(); }} /></label>
      </div>
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={list.data?.items ?? []}
          loading={list.loading}
          emptyText={list.error ? "Trips couldn't be loaded." : "No trips match these filters."}
          actions={(row) => (
            <>
              {trackingService().canManageTrips && row.status === "scheduled" ? (
                <button className="link-btn" type="button" disabled={busy !== null} onClick={() => void act(row, "start")}>Start</button>
              ) : null}
              {trackingService().canManageTrips && row.status === "active" ? (
                <button className="link-btn" type="button" disabled={busy !== null} onClick={() => void act(row, "complete")}>Complete</button>
              ) : null}
              <button className="link-btn" type="button" onClick={() => setOpen(row)}>Details</button>
            </>
          )}
        />
        <Pagination page={page} pageSize={20} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {open ? <TripDialog trip={open} onClose={() => setOpen(null)} /> : null}
      {scheduling ? (
        <ScheduleTrip
          onClose={() => setScheduling(false)}
          onSaved={() => {
            setScheduling(false);
            toast("success", "Trip scheduled.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}

function TripDialog({ trip, onClose }: { trip: Trip; onClose: () => void }) {
  const riders = useOptions(useCallback(() => trackingService().attendance({ tripId: trip.id, pageSize: 50 }).then((page) => page.items), [trip.id]));
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal-card acad-modal" role="dialog" aria-modal="true" aria-labelledby="trip-title">
        <h2 id="trip-title">{trip.route_name}</h2>
        <p className="muted">{trip.trip_date} · {directionLabel(trip.direction)}</p>
        <dl className="teach-facts">
          <div><dt>Status</dt><dd><Chip tone={TRIP_STATUS[trip.status].tone}>{TRIP_STATUS[trip.status].label}</Chip></dd></div>
          <div><dt>Vehicle</dt><dd>{trip.registration_no}</dd></div>
          <div><dt>Driver</dt><dd>{trip.driver_name ?? "—"}</dd></div>
          <div><dt>Helper</dt><dd>{trip.helper_name ?? "—"}</dd></div>
          <div><dt>Scheduled</dt><dd>{trip.scheduled_start}</dd></div>
          <div><dt>Started</dt><dd>{time(trip.started_at)}</dd></div>
          <div><dt>Ended</dt><dd>{time(trip.ended_at)}</dd></div>
        </dl>
        <h3>Students ({riders.options.length})</h3>
        <ErrorAlert error={riders.error} onRetry={() => void riders.reload()} />
        {riders.loading ? <div className="skeleton" style={{ height: 80 }} /> : null}
        <ul className="teach-list">
          {riders.options.map((row) => (
            <li key={row.id}>
              {row.student_name} · {row.stop_name ?? "—"} · <Chip tone={BOARDING_STATUS[row.status].tone}>{BOARDING_STATUS[row.status].label}</Chip> {row.boarded_at ? time(row.boarded_at) : ""}
            </li>
          ))}
        </ul>
        <div className="resource-actions acad-modal-actions">
          <button className="btn-pill btn-pill-green-soft" type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function ScheduleTrip({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const options = useFleetOptions();
  const people = useOptions(useCallback(() => staffDirectory(), []));
  const [routeId, setRouteId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [driverId, setDriverId] = useState("");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    if (!routeId) {
      errors.setFieldErrors({ route_id: "Choose a route." });
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await trackingService().createTrip(Number(routeId), vehicleId ? Number(vehicleId) : "", driverId ? Number(driverId) : "");
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to schedule the trip.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="Schedule a trip" description="Start it when the bus leaves; the driver app records boarding and GPS while it runs." error={errors.formError} saving={saving} submitLabel="Schedule" onSubmit={() => void submit()} onClose={onClose}>
      <SelectField id="st-route" label="Route" required placeholder="Choose a route" value={routeId} onChange={setRouteId} options={options.routes} error={errors.fieldErrors.route_id} />
      <SelectField id="st-vehicle" label="Vehicle" placeholder="The route's vehicle" value={vehicleId} onChange={setVehicleId} options={options.vehicles} error={errors.fieldErrors.vehicle_id} />
      <SelectField id="st-driver" label="Driver" placeholder="The vehicle's driver" loading={people.loading} value={driverId} onChange={setDriverId} options={people.options.map((row) => ({ value: String(row.staff_id), label: `${row.name}${row.designation ? ` · ${row.designation}` : ""}` }))} />
    </FormModal>
  );
}

// ---------- Boarding (transport attendance) ----------

export function BoardingPage() {
  return (
    <ExtrasPage title="Transport attendance" description="When each student boarded and was dropped off. Correct a record if the bus staff missed it." icon={icon} tabs={TRACKING_TABS} note={note()}>
      <BoardingBody />
    </ExtrasPage>
  );
}

function BoardingBody() {
  const toast = useToast();
  const options = useFleetOptions();
  const [date, setDate] = useState(todayLocal());
  const [routeId, setRouteId] = useState("");
  const [status, setStatus] = useState<BoardingStatus | "">("");
  const [student, setStudent] = useState<StudentRow | null>(null);
  const [page, setPage] = useState(1);
  const [fixing, setFixing] = useState<TransportAttendance | null>(null);
  const list = usePagedList(
    useCallback(() => trackingService().attendance({ page, pageSize: 20, date, routeId: routeId ? Number(routeId) : "", status, studentId: student?.id ?? "" }), [page, date, routeId, status, student]),
  );
  const rows = list.data?.items ?? [];
  const columns: Column<TransportAttendance>[] = [
    { key: "student", label: "Student", render: (row) => <div><strong>{row.student_name}</strong><div className="muted">{row.admission_no}</div></div> },
    { key: "trip", label: "Trip", render: (row) => <div>{row.route_name}<div className="muted">{row.trip_date} · {directionLabel(row.direction)}</div></div> },
    { key: "stop", label: "Stop", render: (row) => row.stop_name ?? "—" },
    { key: "status", label: "Status", render: (row) => <div><Chip tone={BOARDING_STATUS[row.status].tone}>{BOARDING_STATUS[row.status].label}</Chip>{row.corrected_by ? <div className="muted">Corrected{row.note ? `: ${row.note}` : ""}</div> : null}</div> },
    { key: "on", label: "Boarded", render: (row) => time(row.boarded_at) },
    { key: "off", label: "Dropped", render: (row) => time(row.dropped_at) },
  ];
  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">Date <input type="date" value={date} max={todayLocal()} onChange={(event) => { setDate(event.target.value); setPage(1); }} /></label>
        <select aria-label="Route" value={routeId} onChange={(event) => { setRouteId(event.target.value); setPage(1); }}>
          <option value="">All routes</option>
          {options.routes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <select aria-label="Boarding status" value={status} onChange={(event) => { setStatus(event.target.value as BoardingStatus | ""); setPage(1); }}>
          <option value="">Any status</option>
          {(Object.keys(BOARDING_STATUS) as BoardingStatus[]).map((key) => <option key={key} value={key}>{BOARDING_STATUS[key].label}</option>)}
        </select>
      </div>
      <div className="resource-card resource-fields">
        <StudentSearch id="ta-student" label="One student only (optional)" value={student} onChange={(next) => { setStudent(next); setPage(1); }} />
      </div>
      {rows.length ? (
        <div className="teach-stats">
          <Stat label="On this page" value={rows.length} />
          <Stat label="Boarded" value={rows.filter((row) => row.status === "boarded" || row.status === "dropped").length} tone="green" />
          <Stat label="Absent" value={rows.filter((row) => row.status === "absent").length} tone="red" />
          <Stat label="Boarding rate" value={`${boardingRate(rows)}%`} tone="blue" />
        </div>
      ) : null}
      <ErrorAlert error={list.error} onRetry={() => void list.reload()} />
      <div className="resource-card">
        <DataTable
          columns={columns}
          rows={rows}
          loading={list.loading}
          emptyText={list.error ? "Records couldn't be loaded." : "No boarding records for these filters."}
          actions={(row) => <button className="link-btn" type="button" onClick={() => setFixing(row)}>Correct</button>}
        />
        <Pagination page={page} pageSize={20} total={list.data?.total ?? 0} onPage={setPage} />
      </div>
      {fixing ? (
        <CorrectionForm
          row={fixing}
          onClose={() => setFixing(null)}
          onSaved={() => {
            setFixing(null);
            toast("success", "Record corrected.");
            void list.reload();
          }}
        />
      ) : null}
    </>
  );
}

function CorrectionForm({ row, onClose, onSaved }: { row: TransportAttendance; onClose: () => void; onSaved: () => void }) {
  const live = isOperationsLive("tracking");
  // The server records boarding and drop-off events only, so a live record can move forward but not back.
  const choices = (Object.keys(BOARDING_STATUS) as BoardingStatus[]).filter((key) => !live || key === "boarded" || key === "dropped");
  const [status, setStatus] = useState<BoardingStatus>(live && !choices.includes(row.status) ? "boarded" : row.status);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const errors = useFormErrors();
  async function submit() {
    if (!live && !reason.trim()) {
      errors.setFieldErrors({ note: "Say why the record is being changed." });
      return;
    }
    errors.clear();
    setSaving(true);
    try {
      await trackingService().correct(row.id, status, reason);
      onSaved();
    } catch (caught) {
      errors.fromError(caught, "Unable to correct the record.");
      setSaving(false);
    }
  }
  return (
    <FormModal title="Correct boarding record" description={`${row.student_name} · ${row.route_name} · ${row.trip_date} · ${directionLabel(row.direction)}`} error={errors.formError} saving={saving} submitLabel="Save correction" onSubmit={() => void submit()} onClose={onClose}>
      <SelectField id="tc-status" label="Status" required value={status} onChange={(value) => setStatus(value as BoardingStatus)} options={choices.map((key) => ({ value: key, label: BOARDING_STATUS[key].label }))} hint={live ? "Records boarding (and drop-off) now, for students the bus staff missed." : undefined} />
      {live ? null : <TextAreaField id="tc-note" label="Reason" required value={reason} onChange={setReason} error={errors.fieldErrors.note} hint="Kept with the record, e.g. “Parent picked the child up at the gate”." span />}
    </FormModal>
  );
}

// ---------- Reports ----------

export function TransportReportsPage() {
  return (
    <ExtrasPage title="Transport reports" description="Boarding by route, and each student's transport history." icon={icon} tabs={TRACKING_TABS} note={note()}>
      <ReportsBody />
    </ExtrasPage>
  );
}

function ReportsBody() {
  const toast = useToast();
  const [from, setFrom] = useState(daysAgo(30));
  const [to, setTo] = useState(todayLocal());
  const [student, setStudent] = useState<StudentRow | null>(null);
  const report = useOptions(useCallback(() => trackingService().routeReport(from, to), [from, to]));
  const history = useOptions(
    useCallback(
      () =>
        student
          ? trackingService()
              .attendance({ studentId: student.id, pageSize: 50 })
              .then((page) => page.items.filter((row) => row.trip_date >= from && row.trip_date <= to))
          : Promise.resolve([] as TransportAttendance[]),
      [student, from, to],
    ),
  );
  const routeRows = report.options.map((row) => ({ ...row, id: row.route_id }));
  const columns: Column<(typeof routeRows)[number]>[] = [
    { key: "route", label: "Route", render: (row) => <strong>{row.route_name}</strong> },
    { key: "trips", label: "Trips", render: (row) => row.trips },
    { key: "expected", label: "Expected rides", render: (row) => row.expected },
    { key: "boarded", label: "Boarded", render: (row) => row.boarded },
    { key: "absent", label: "Absent", render: (row) => row.absent },
    { key: "rate", label: "Boarding rate", render: (row) => <Chip tone={row.rate >= 90 ? "green" : row.rate >= 75 ? "amber" : "red"}>{row.rate}%</Chip> },
  ];
  const historyColumns: Column<TransportAttendance>[] = [
    { key: "date", label: "Date", render: (row) => row.trip_date },
    { key: "trip", label: "Trip", render: (row) => `${row.route_name} · ${directionLabel(row.direction)}` },
    { key: "status", label: "Status", render: (row) => <Chip tone={BOARDING_STATUS[row.status].tone}>{BOARDING_STATUS[row.status].label}</Chip> },
    { key: "on", label: "Boarded", render: (row) => time(row.boarded_at) },
    { key: "off", label: "Dropped", render: (row) => time(row.dropped_at) },
  ];

  function exportRoutes() {
    if (!report.options.length) {
      toast("error", "Nothing to export for these dates.");
      return;
    }
    downloadText(
      `transport-routes-${from}-to-${to}.csv`,
      toCsv(report.options, [
        { label: "Route", value: (row) => row.route_name },
        { label: "Trips", value: (row) => row.trips },
        { label: "Expected rides", value: (row) => row.expected },
        { label: "Boarded", value: (row) => row.boarded },
        { label: "Absent", value: (row) => row.absent },
        { label: "Boarding rate %", value: (row) => row.rate },
      ]),
    );
  }

  return (
    <>
      <div className="school-filters">
        <label className="ops-filter-label">From <input type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></label>
        <label className="ops-filter-label">To <input type="date" value={to} min={from} max={todayLocal()} onChange={(event) => setTo(event.target.value)} /></label>
        <button className="btn-pill btn-pill-green-soft" type="button" onClick={exportRoutes} disabled={report.loading}>Export CSV</button>
      </div>
      <ErrorAlert error={report.error} onRetry={() => void report.reload()} />
      <div className="resource-card">
        <h2>By route</h2>
        <DataTable columns={columns} rows={routeRows} loading={report.loading} emptyText="No completed trips in these dates." />
      </div>
      <div className="resource-card resource-fields">
        <h2 className="field-span">One student's history</h2>
        <StudentSearch id="tr-student" label="Student" value={student} onChange={setStudent} />
      </div>
      {student ? (
        <div className="resource-card">
          <ErrorAlert error={history.error} onRetry={() => void history.reload()} />
          <DataTable columns={historyColumns} rows={history.options} loading={history.loading} emptyText={`No transport records for ${student.name} in these dates.`} />
        </div>
      ) : null}
    </>
  );
}
