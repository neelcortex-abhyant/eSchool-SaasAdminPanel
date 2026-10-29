/**
 * Bus tracking, trips and transport attendance.
 * Live: trips and boarding events on the server's /school-admin/transport-trips routes (see
 * the live section). Bus positions stay simulated until the server has an admin GPS read route
 * (backend/docs/OPERATIONS_MODULES_API_CONTRACT.md).
 * Sample: built from the school's real vehicles, routes, stops and student transport (the
 * transport client, live or sample), with simulated GPS positions, trips and boarding records.
 * Corrections are kept in this browser.
 */
import { isOperationsLive } from "@/lib/operations/mode";
import type {
  BoardingStatus,
  Page,
  RouteAttendanceSummary,
  TransportAttendance,
  TransportAttendanceQuery,
  Trip,
  TripDirection,
  TripQuery,
  TripStatus,
  VehicleLocation,
} from "@/lib/operations/types";
import { transportService } from "@/lib/ops/transport";
import type { Route, TransportAssignment, Vehicle } from "@/lib/ops/types";
import { allPages, get, num, optNum, optStr, send, settleLimited, str, type Raw } from "@/lib/teaching/client";
import { staffDirectory, type StaffRef } from "@/lib/extras/api";
import { invalid, later, missing } from "@/lib/ops/store";
import { AcademicApiError } from "@/lib/academics/errors";

export interface TrackingService {
  locations(): Promise<VehicleLocation[]>;
  trips(query?: TripQuery): Promise<Page<Trip>>;
  trip(id: number): Promise<Trip>;
  attendance(query?: TransportAttendanceQuery): Promise<Page<TransportAttendance>>;
  correct(id: number, status: BoardingStatus, note: string): Promise<TransportAttendance>;
  routeReport(from: string, to: string): Promise<RouteAttendanceSummary[]>;
  /** Schedule, start and finish trips (the server's routes; not in the sample). */
  createTrip(routeId: number, vehicleId?: number | "", driverStaffId?: number | ""): Promise<void>;
  startTrip(id: number): Promise<void>;
  completeTrip(id: number): Promise<void>;
  canManageTrips: boolean;
}

/** A location older than this is shown as stale; older than OFFLINE_AFTER as offline. */
export const STALE_AFTER_MS = 5 * 60_000;
export const OFFLINE_AFTER_MS = 30 * 60_000;

export type Freshness = "live" | "stale" | "offline";

export function freshness(recordedAt: string, now = Date.now()): Freshness {
  const age = now - new Date(recordedAt).getTime();
  if (!(age >= 0) || Number.isNaN(age)) return age < 0 ? "live" : "offline";
  if (age > OFFLINE_AFTER_MS) return "offline";
  if (age > STALE_AFTER_MS) return "stale";
  return "live";
}

/** "2 min ago", "1 h 5 min ago". */
export function ageLabel(recordedAt: string, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - new Date(recordedAt).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${minutes % 60} min ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

export function boardingRate(rows: Pick<TransportAttendance, "status">[]): number {
  const counted = rows.filter((row) => row.status !== "pending");
  if (!counted.length) return 0;
  return Math.round((counted.filter((row) => row.status === "boarded" || row.status === "dropped").length / counted.length) * 100);
}

// ---------- live ----------
// Trips, boarding events and trip reports use the server's routes (backend 0041):
//   GET/POST /school-admin/transport-trips, POST /transport-trips/{id}/start|complete,
//   GET/POST /transport-trips/{id}/attendance {student_id, event_type: board|drop, stop_id},
//   GET /school-admin/transport/reports/trips.
// The server has no admin route that returns GPS fixes yet (drivers post them), so bus positions
// on the map are simulated around the school; trip status on the map is real.

const SA = "/school-admin";

const STATUS_FROM_SERVER: Record<string, TripStatus> = { scheduled: "scheduled", in_progress: "active", completed: "completed", cancelled: "cancelled" };
const STATUS_TO_SERVER: Record<TripStatus, string> = { scheduled: "scheduled", active: "in_progress", completed: "completed", cancelled: "cancelled" };

type LiveContext = { routes: Route[]; vehicles: Vehicle[]; riders: TransportAssignment[]; people: StaffRef[] };

async function liveContext(): Promise<LiveContext> {
  const data = await fleet();
  const people = await staffDirectory().catch(() => [] as StaffRef[]);
  return { ...data, people };
}

function localDay(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function tripFromServer(row: Raw, context: Pick<LiveContext, "routes" | "vehicles" | "riders" | "people">, boarded = 0): Trip {
  const route = context.routes.find((item) => item.id === num(row.route_id));
  const vehicle = context.vehicles.find((item) => item.id === num(row.vehicle_id));
  const driver = context.people.find((person) => person.staff_id === optNum(row.driver_staff_id));
  const started = optStr(row.started_at);
  return {
    id: num(row.id),
    route_id: num(row.route_id),
    route_name: route?.name ?? `Route #${num(row.route_id)}`,
    vehicle_id: num(row.vehicle_id),
    registration_no: vehicle?.registration_no ?? `Vehicle #${num(row.vehicle_id)}`,
    driver_name: driver?.name ?? vehicle?.driver_name ?? null,
    helper_name: vehicle?.helper_name ?? null,
    direction: null,
    status: STATUS_FROM_SERVER[str(row.status)] ?? "scheduled",
    trip_date: localDay(started ?? optStr(row.created_at)),
    scheduled_start: optStr(row.created_at) ? new Date(str(row.created_at)).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "",
    started_at: started,
    ended_at: optStr(row.ended_at),
    boarded,
    expected: context.riders.filter((rider) => rider.route_id === num(row.route_id)).length,
  };
}

async function tripEvents(tripId: number): Promise<Raw[]> {
  const data = await get(`${SA}/transport-trips/${tripId}/attendance`, {}, "Unable to load boarding records.");
  return Array.isArray(data.items) ? (data.items as Raw[]) : [];
}

/** One row per student on the trip's route, from the trip's board and drop events. */
export function attendanceFromEvents(trip: Trip, events: Raw[], context: Pick<LiveContext, "routes" | "riders">): TransportAttendance[] {
  const route = context.routes.find((item) => item.id === trip.route_id);
  const riders = context.riders.filter((rider) => rider.route_id === trip.route_id);
  const extra = [...new Set(events.map((event) => num(event.student_id)))].filter((id) => !riders.some((rider) => rider.student_id === id));
  const people = [...riders.map((rider) => ({ student_id: rider.student_id, student_name: rider.student_name, admission_no: rider.admission_no, stop_id: rider.stop_id })), ...extra.map((id) => ({ student_id: id, student_name: `Student #${id}`, admission_no: "", stop_id: 0 }))];
  return people.map((person) => {
    const mine = events.filter((event) => num(event.student_id) === person.student_id);
    const board = mine.find((event) => str(event.event_type) === "board");
    const drop = mine.find((event) => str(event.event_type) === "drop");
    const stopId = optNum((drop ?? board)?.stop_id) ?? person.stop_id;
    const status: BoardingStatus = drop ? "dropped" : board ? "boarded" : trip.status === "completed" || trip.status === "cancelled" ? "absent" : "pending";
    return {
      id: trip.id * 100_000 + person.student_id,
      trip_id: trip.id,
      trip_date: trip.trip_date,
      direction: trip.direction,
      route_id: trip.route_id,
      route_name: trip.route_name,
      student_id: person.student_id,
      student_name: person.student_name,
      admission_no: person.admission_no,
      stop_name: route?.stops.find((stop) => stop.id === stopId)?.name ?? null,
      status,
      boarded_at: board ? str(board.recorded_at) : null,
      dropped_at: drop ? str(drop.recorded_at) : null,
      corrected_by: null,
      note: null,
    };
  });
}

async function allLiveTrips(query: TripQuery, context: LiveContext): Promise<Trip[]> {
  const rows = await allPages(`${SA}/transport-trips`, { status: query.status ? STATUS_TO_SERVER[query.status] : undefined, route_id: query.routeId || undefined }, "Unable to load trips.");
  return rows
    .map((row) => tripFromServer(row, context))
    .filter((trip) => !query.vehicleId || trip.vehicle_id === query.vehicleId)
    .filter((trip) => !query.from || !trip.trip_date || trip.trip_date >= query.from)
    .filter((trip) => !query.to || !trip.trip_date || trip.trip_date <= query.to)
    .sort((a, b) => (b.started_at ?? b.trip_date).localeCompare(a.started_at ?? a.trip_date) || b.id - a.id);
}

/** Boarded counts for a page of trips (one request per trip, a few at a time). */
async function withBoarded(trips: Trip[]): Promise<Trip[]> {
  const counts = await settleLimited(trips.map((trip) => () => (trip.status === "scheduled" ? Promise.resolve([] as Raw[]) : tripEvents(trip.id))), 4);
  return trips.map((trip, index) => {
    const events = counts[index].ok ? counts[index].value : [];
    return { ...trip, boarded: new Set(events.filter((event) => str(event.event_type) === "board").map((event) => num(event.student_id))).size };
  });
}

function paged<T>(rows: T[], page = 1, pageSize = 20): Page<T> {
  const size = Math.min(pageSize, 50);
  const current = Math.max(page, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

export const liveTracking: TrackingService = {
  async locations() {
    const context = await liveContext();
    const trips = await allLiveTrips({}, context).catch(() => [] as Trip[]);
    const now = Date.now();
    return context.vehicles.map((vehicle): VehicleLocation => {
      const trip = trips.find((row) => row.vehicle_id === vehicle.id && row.status === "active") ?? trips.find((row) => row.vehicle_id === vehicle.id && row.trip_date === localDay(new Date().toISOString())) ?? null;
      const route = context.routes.find((row) => row.vehicle_id === vehicle.id && row.status === 1) ?? null;
      const position = samplePosition(vehicle.id, now);
      return {
        vehicle_id: vehicle.id,
        registration_no: vehicle.registration_no,
        route_id: trip?.route_id ?? route?.id ?? null,
        route_name: trip?.route_name ?? route?.name ?? null,
        driver_name: trip?.driver_name ?? vehicle.driver_name,
        trip_id: trip?.id ?? null,
        trip_status: trip?.status ?? null,
        latitude: Number(position.latitude.toFixed(6)),
        longitude: Number(position.longitude.toFixed(6)),
        speed_kmph: null,
        heading: position.heading,
        // Simulated position: "live" while a trip runs, offline otherwise.
        recorded_at: new Date(trip?.status === "active" ? now : now - 2 * 3_600_000).toISOString(),
      };
    });
  },
  async trips(query = {}) {
    const context = await liveContext();
    const page = paged(await allLiveTrips(query, context), query.page, query.pageSize);
    return { ...page, items: await withBoarded(page.items) };
  },
  async trip(id) {
    const context = await liveContext();
    const trip = (await allLiveTrips({}, context)).find((row) => row.id === id) ?? missing("Trip");
    return (await withBoarded([trip]))[0];
  },
  async attendance(query = {}) {
    const context = await liveContext();
    let trips = await allLiveTrips({ routeId: query.routeId }, context);
    if (query.tripId) trips = trips.filter((trip) => trip.id === query.tripId);
    if (query.date) trips = trips.filter((trip) => trip.trip_date === query.date);
    if (!query.tripId && !query.date) trips = trips.slice(0, 30);
    trips = trips.filter((trip) => trip.status !== "scheduled" || query.tripId);
    const events = await settleLimited(trips.map((trip) => () => tripEvents(trip.id)), 4);
    const rows = trips
      .flatMap((trip, index) => attendanceFromEvents(trip, events[index].ok ? events[index].value : [], context))
      .filter((row) => !query.studentId || row.student_id === query.studentId)
      .filter((row) => !query.status || row.status === query.status);
    return paged(rows, query.page, query.pageSize);
  },
  async correct(id, status, note) {
    void note;
    const tripId = Math.floor(id / 100_000);
    const studentId = id % 100_000;
    if (status === "absent" || status === "pending") invalid({ status: "The server records boarding and drop-off only, so a record can't be set back to absent." });
    const context = await liveContext();
    const rider = context.riders.find((row) => row.student_id === studentId);
    const events = await tripEvents(tripId);
    const has = (type: string) => events.some((event) => num(event.student_id) === studentId && str(event.event_type) === type);
    const post = (event_type: string) => send("POST", `${SA}/transport-trips/${tripId}/attendance`, { student_id: studentId, event_type, stop_id: rider?.stop_id || null }, "Unable to save the boarding record.");
    if (!has("board")) await post("board");
    if (status === "dropped" && !has("drop")) await post("drop");
    const trip = (await allLiveTrips({}, context)).find((row) => row.id === tripId) ?? missing("Trip");
    return attendanceFromEvents(trip, await tripEvents(tripId), context).find((row) => row.student_id === studentId) ?? missing("Transport attendance");
  },
  async routeReport(from, to) {
    const context = await liveContext();
    const trips = (await allLiveTrips({ from, to }, context)).filter((trip) => trip.status !== "scheduled");
    const events = await settleLimited(trips.map((trip) => () => tripEvents(trip.id)), 4);
    const rows = trips.flatMap((trip, index) => attendanceFromEvents(trip, events[index].ok ? events[index].value : [], context));
    return context.routes
      .filter((route) => trips.some((trip) => trip.route_id === route.id))
      .map((route) => {
        const mine = rows.filter((row) => row.route_id === route.id);
        return {
          route_id: route.id,
          route_name: route.name,
          trips: trips.filter((trip) => trip.route_id === route.id).length,
          expected: mine.length,
          boarded: mine.filter((row) => row.status === "boarded" || row.status === "dropped").length,
          absent: mine.filter((row) => row.status === "absent").length,
          rate: boardingRate(mine),
        };
      });
  },
  async createTrip(routeId, vehicleId, driverStaffId) {
    if (!routeId) invalid({ route_id: "Choose a route." });
    await send("POST", `${SA}/transport-trips`, { route_id: routeId, vehicle_id: vehicleId || null, driver_staff_id: driverStaffId || null }, "Unable to schedule the trip.");
  },
  async startTrip(id) {
    await send("POST", `${SA}/transport-trips/${id}/start`, {}, "Unable to start the trip.");
  },
  async completeTrip(id) {
    await send("POST", `${SA}/transport-trips/${id}/complete`, {}, "Unable to complete the trip.");
  },
  canManageTrips: true,
};

// ---------- sample ----------

const CORRECTIONS_KEY = "operations-transport-corrections-v1";
/** Where sample buses drive: around a school in central Bengaluru. */
export const SCHOOL_POSITION = { latitude: 12.9716, longitude: 77.5946 };

type Fleet = { vehicles: Vehicle[]; routes: Route[]; riders: TransportAssignment[] };

async function fleet(): Promise<Fleet> {
  const service = transportService();
  const [vehicles, routes, riders] = await Promise.all([
    service.vehicles(),
    service.routes(),
    service.assignments({ pageSize: 50 }).then((page) => page.items),
  ]);
  return { vehicles, routes, riders };
}

function localDate(offsetDays: number, now = new Date()): string {
  const day = new Date(now.getTime() - offsetDays * 86_400_000);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

/** A steady pseudo-random number in [0, 1) for a seed, so sample data doesn't change on reload. */
export function seeded(seed: number): number {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

const SCHEDULE: Record<TripDirection, { start: string; minutes: number }> = {
  pickup: { start: "07:00", minutes: 60 },
  drop: { start: "14:30", minutes: 60 },
};

function at(date: string, time: string, plusMinutes = 0): Date {
  const [h, m] = time.split(":").map(Number);
  const value = new Date(`${date}T00:00:00`);
  value.setHours(h, m + plusMinutes, 0, 0);
  return value;
}

function tripId(dayOffset: number, routeId: number, direction: TripDirection): number {
  return (30 - dayOffset) * 100_000 + routeId * 10 + (direction === "pickup" ? 1 : 2);
}

/** Trips for the last 14 days and today, two a day per active route with a vehicle. */
function sampleTrips(data: Fleet, now = new Date()): Trip[] {
  const trips: Trip[] = [];
  for (let offset = 14; offset >= 0; offset -= 1) {
    const date = localDate(offset, now);
    const weekday = new Date(`${date}T00:00:00`).getDay();
    if (weekday === 0) continue;
    for (const route of data.routes.filter((row) => row.status === 1 && row.vehicle_id)) {
      const vehicle = data.vehicles.find((row) => row.id === route.vehicle_id);
      if (!vehicle) continue;
      const expected = data.riders.filter((row) => row.route_id === route.id).length;
      for (const direction of ["pickup", "drop"] as TripDirection[]) {
        const start = at(date, SCHEDULE[direction].start);
        const end = at(date, SCHEDULE[direction].start, SCHEDULE[direction].minutes);
        const status: TripStatus = now < start ? "scheduled" : now < end ? "active" : "completed";
        const id = tripId(offset, route.id, direction);
        const boarded = status === "scheduled" ? 0 : data.riders.filter((rider) => rider.route_id === route.id && sampleStatus(id, rider.student_id, status) !== "absent").length;
        trips.push({
          id,
          route_id: route.id,
          route_name: route.name,
          vehicle_id: vehicle.id,
          registration_no: vehicle.registration_no,
          driver_name: vehicle.driver_name,
          helper_name: vehicle.helper_name,
          direction,
          status,
          trip_date: date,
          scheduled_start: SCHEDULE[direction].start,
          started_at: status === "scheduled" ? null : new Date(start.getTime() + Math.round(seeded(id) * 6) * 60_000).toISOString(),
          ended_at: status === "completed" ? new Date(end.getTime() + Math.round(seeded(id + 1) * 10) * 60_000).toISOString() : null,
          boarded,
          expected,
        });
      }
    }
  }
  return trips.sort((a, b) => b.trip_date.localeCompare(a.trip_date) || b.scheduled_start.localeCompare(a.scheduled_start) || a.route_name.localeCompare(b.route_name));
}

function sampleStatus(tripIdValue: number, studentId: number, tripStatus: TripStatus): BoardingStatus {
  if (tripStatus === "scheduled") return "pending";
  const roll = seeded(tripIdValue * 31 + studentId);
  if (roll < 0.08) return "absent";
  if (tripStatus === "active" && roll < 0.3) return "pending";
  return tripIdValue % 10 === 2 ? "dropped" : "boarded";
}

function readCorrections(): Record<string, { status: BoardingStatus; note: string; at: string }> {
  try {
    return JSON.parse(window.localStorage.getItem(CORRECTIONS_KEY) || "{}");
  } catch {
    return {};
  }
}

function sampleAttendance(data: Fleet, trips: Trip[]): TransportAttendance[] {
  const corrections = readCorrections();
  const rows: TransportAttendance[] = [];
  for (const trip of trips) {
    const route = data.routes.find((row) => row.id === trip.route_id);
    for (const rider of data.riders.filter((row) => row.route_id === trip.route_id)) {
      const id = trip.id * 1000 + rider.student_id;
      const fix = corrections[String(id)];
      const status = fix?.status ?? sampleStatus(trip.id, rider.student_id, trip.status);
      const stopIndex = route?.stops.findIndex((stop) => stop.id === rider.stop_id) ?? 0;
      const time = trip.started_at ? new Date(new Date(trip.started_at).getTime() + (Math.max(stopIndex, 0) + 1) * 7 * 60_000).toISOString() : null;
      rows.push({
        id,
        trip_id: trip.id,
        trip_date: trip.trip_date,
        direction: trip.direction,
        route_id: trip.route_id,
        route_name: trip.route_name,
        student_id: rider.student_id,
        student_name: rider.student_name,
        admission_no: rider.admission_no,
        stop_name: rider.stop_name || null,
        status,
        boarded_at: status === "boarded" || status === "dropped" ? time : null,
        dropped_at: status === "dropped" && time ? new Date(new Date(time).getTime() + 25 * 60_000).toISOString() : null,
        corrected_by: fix ? "School admin" : null,
        note: fix?.note ?? null,
      });
    }
  }
  return rows;
}

/** Positions on a loop around the school; each bus is somewhere on its loop depending on the time. */
export function samplePosition(vehicleId: number, now = Date.now()): { latitude: number; longitude: number; heading: number } {
  const radius = 0.012 + (vehicleId % 3) * 0.006;
  const angle = (now / 600_000 + vehicleId * 1.7) % (2 * Math.PI);
  return {
    latitude: SCHOOL_POSITION.latitude + radius * Math.sin(angle),
    longitude: SCHOOL_POSITION.longitude + radius * Math.cos(angle),
    heading: Math.round(((angle * 180) / Math.PI + 90) % 360),
  };
}

function paginate<T>(rows: T[], page = 1, pageSize = 20): Page<T> {
  const size = Math.min(pageSize, 50);
  const current = Math.max(page, 1);
  return { items: rows.slice((current - 1) * size, current * size), total: rows.length, page: current, page_size: size };
}

function sampleOnly(): Promise<void> {
  return Promise.reject(new AcademicApiError(400, "Trips can be scheduled only on the school's server."));
}

export const mockTracking: TrackingService = {
  async locations() {
    const data = await fleet();
    const trips = sampleTrips(data).filter((trip) => trip.trip_date === localDate(0));
    const now = Date.now();
    return data.vehicles.map((vehicle, index): VehicleLocation => {
      const route = data.routes.find((row) => row.vehicle_id === vehicle.id && row.status === 1) ?? null;
      const trip = trips.find((row) => row.vehicle_id === vehicle.id && row.status === "active") ?? trips.find((row) => row.vehicle_id === vehicle.id) ?? null;
      const position = samplePosition(vehicle.id, now);
      // The last vehicle's tracker hasn't reported for a while, and an inactive one is offline.
      const age = vehicle.status === 0 ? 3 * 3_600_000 : index === data.vehicles.length - 1 && data.vehicles.length > 1 ? 12 * 60_000 : 20_000;
      return {
        vehicle_id: vehicle.id,
        registration_no: vehicle.registration_no,
        route_id: route?.id ?? null,
        route_name: route?.name ?? null,
        driver_name: vehicle.driver_name,
        trip_id: trip?.id ?? null,
        trip_status: trip?.status ?? null,
        latitude: Number(position.latitude.toFixed(6)),
        longitude: Number(position.longitude.toFixed(6)),
        speed_kmph: trip?.status === "active" ? 18 + Math.round(seeded(vehicle.id + now / 60_000) * 20) : 0,
        heading: position.heading,
        recorded_at: new Date(now - age).toISOString(),
      };
    });
  },
  async trips(query = {}) {
    const rows = sampleTrips(await fleet())
      .filter((row) => !query.status || row.status === query.status)
      .filter((row) => !query.routeId || row.route_id === query.routeId)
      .filter((row) => !query.vehicleId || row.vehicle_id === query.vehicleId)
      .filter((row) => !query.from || row.trip_date >= query.from)
      .filter((row) => !query.to || row.trip_date <= query.to);
    return later(paginate(rows, query.page, query.pageSize));
  },
  async trip(id) {
    const row = sampleTrips(await fleet()).find((item) => item.id === id);
    return later(row ?? missing("Trip"));
  },
  async attendance(query = {}) {
    const data = await fleet();
    const trips = sampleTrips(data)
      .filter((trip) => !query.tripId || trip.id === query.tripId)
      .filter((trip) => !query.routeId || trip.route_id === query.routeId)
      .filter((trip) => !query.date || trip.trip_date === query.date);
    const rows = sampleAttendance(data, trips)
      .filter((row) => !query.studentId || row.student_id === query.studentId)
      .filter((row) => !query.status || row.status === query.status);
    return later(paginate(rows, query.page, query.pageSize));
  },
  async correct(id, status, note) {
    if (!note.trim()) invalid({ note: "Say why the record is being changed." });
    const corrections = readCorrections();
    corrections[String(id)] = { status, note: note.trim(), at: new Date().toISOString() };
    try {
      window.localStorage.setItem(CORRECTIONS_KEY, JSON.stringify(corrections));
    } catch {
      // Storage unavailable: the change lasts until the page reloads.
    }
    const data = await fleet();
    const row = sampleAttendance(data, sampleTrips(data)).find((item) => item.id === id);
    return later(row ?? missing("Transport attendance"));
  },
  async routeReport(from, to) {
    const data = await fleet();
    const trips = sampleTrips(data).filter((trip) => trip.status !== "scheduled" && trip.trip_date >= from && trip.trip_date <= to);
    const rows = sampleAttendance(data, trips);
    return later(
      data.routes
        .filter((route) => trips.some((trip) => trip.route_id === route.id))
        .map((route) => {
          const mine = rows.filter((row) => row.route_id === route.id);
          return {
            route_id: route.id,
            route_name: route.name,
            trips: trips.filter((trip) => trip.route_id === route.id).length,
            expected: mine.length,
            boarded: mine.filter((row) => row.status === "boarded" || row.status === "dropped").length,
            absent: mine.filter((row) => row.status === "absent").length,
            rate: boardingRate(mine),
          };
        }),
    );
  },
  createTrip: sampleOnly,
  startTrip: sampleOnly,
  completeTrip: sampleOnly,
  canManageTrips: false,
};

export function trackingService(): TrackingService {
  return isOperationsLive("tracking") ? liveTracking : mockTracking;
}
