/**
 * School transport: vehicles (with driver and helper), routes, stops and student assignments.
 * Live: /school-admin/vehicles, /transport-routes (with their stops), /transport-stops,
 *   /student-transport-assignments. The server keeps a vehicle's name, registration, seats and
 *   status only, and can't edit stops or student assignments (add and remove instead). It
 *   doesn't check seats, so this client refuses an assignment that would overfill a vehicle.
 * Sample: drivers and helpers are school staff (people client).
 */
import { studentRef, studentRefs } from "@/lib/ops/lookups";
import { isOpsLive } from "@/lib/ops/mode";
import { conflict, invalid, later, missing, nextId, opsDb, opsSave } from "@/lib/ops/store";
import { capacityProblem, sameRegistration, stopProblems, vehicleProblems } from "@/lib/ops/transport-rules";
import type { AssignmentInput, AssignmentQuery, Page, Route, RouteInput, Stop, StopInput, TransportAssignment, Vehicle, VehicleInput } from "@/lib/ops/types";
import { allPages, hhmm, notAvailable, num, optNum, optStr, send, str, type Raw } from "@/lib/teaching/client";
import { peopleService } from "@/lib/people";

export interface TransportService {
  vehicles(): Promise<Vehicle[]>;
  saveVehicle(input: VehicleInput, id?: number): Promise<Vehicle>;
  setVehicleStatus(id: number, status: 0 | 1): Promise<Vehicle>;
  routes(): Promise<Route[]>;
  route(id: number): Promise<Route>;
  saveRoute(input: RouteInput, id?: number): Promise<Route>;
  setRouteStatus(id: number, status: 0 | 1): Promise<Route>;
  saveStop(routeId: number, input: StopInput, id?: number): Promise<Stop>;
  removeStop(id: number): Promise<void>;
  assignments(query?: AssignmentQuery): Promise<Page<TransportAssignment>>;
  saveAssignment(input: AssignmentInput, id?: number): Promise<TransportAssignment>;
  removeAssignment(id: number): Promise<void>;
}

const T = "/school-admin";

/** Students per route, from the server's student transport list. */
async function liveRiders(): Promise<Raw[]> {
  return allPages(`${T}/student-transport-assignments`, {}, "Unable to load transport assignments.");
}

function liveVehicle(row: Raw, riders: Raw[], routes: Raw[]): Vehicle {
  const id = num(row.id);
  const routeIds = new Set(routes.filter((route) => optNum(route.vehicle_id) === id).map((route) => num(route.id)));
  return {
    id,
    registration_no: str(row.registration_no),
    vehicle_type: "other",
    // The server stores a vehicle name; the form's "model" field edits it.
    model: optStr(row.name),
    capacity: num(row.capacity),
    driver_id: null,
    driver_name: null,
    helper_id: null,
    helper_name: null,
    status: num(row.status ?? 1) === 0 ? 0 : 1,
    assigned_students: riders.filter((rider) => routeIds.has(num(rider.route_id))).length,
  };
}

function liveStop(row: Raw): Stop {
  return {
    id: num(row.id),
    route_id: num(row.route_id),
    name: str(row.name),
    stop_order: num(row.stop_order),
    pickup_time: optStr(row.pickup_time) ? hhmm(row.pickup_time) : null,
    drop_time: optStr(row.drop_time) ? hhmm(row.drop_time) : null,
    landmark: optStr(row.landmark),
  };
}

function liveRoute(row: Raw, vehicles: Raw[], riders: Raw[]): Route {
  const id = num(row.id);
  const vehicleId = optNum(row.vehicle_id);
  const vehicle = vehicles.find((item) => num(item.id) === vehicleId);
  const stops = (Array.isArray(row.stops) ? (row.stops as Raw[]) : []).map(liveStop).sort((a, b) => a.stop_order - b.stop_order);
  return {
    id,
    name: str(row.name),
    description: optStr(row.description),
    vehicle_id: vehicleId,
    vehicle_label: vehicle ? `${str(vehicle.registration_no)}${optNum(vehicle.capacity) ? ` (${num(vehicle.capacity)} seats)` : ""}` : null,
    capacity: vehicle ? optNum(vehicle.capacity) : null,
    assigned_students: riders.filter((rider) => num(rider.route_id) === id).length,
    status: num(row.status ?? 1) === 0 ? 0 : 1,
    stops,
  };
}

async function liveAll() {
  const [vehicles, routes, riders] = await Promise.all([
    allPages(`${T}/vehicles`, {}, "Unable to load vehicles."),
    allPages(`${T}/transport-routes`, {}, "Unable to load routes."),
    liveRiders(),
  ]);
  return { vehicles, routes, riders };
}

function vehicleBody(input: VehicleInput) {
  const registration = input.registration_no.trim().toUpperCase();
  return { name: input.model?.trim() || registration, registration_no: registration, capacity: input.capacity, status: input.status };
}

export const liveTransport: TransportService = {
  async vehicles() {
    const { vehicles, routes, riders } = await liveAll();
    return vehicles.map((row) => liveVehicle(row, riders, routes)).sort((a, b) => b.status - a.status || a.registration_no.localeCompare(b.registration_no));
  },
  async saveVehicle(input, id) {
    const { vehicles, routes, riders } = await liveAll();
    const current = id ? vehicles.find((row) => num(row.id) === id) : null;
    const problems = vehicleProblems(input, current ? liveVehicle(current, riders, routes).assigned_students : 0);
    if (Object.keys(problems).length) invalid(problems);
    if (vehicles.some((row) => num(row.id) !== id && sameRegistration(str(row.registration_no), input.registration_no))) conflict("Another vehicle has this registration number.", "registration_no");
    const row = id
      ? await send("PATCH", `${T}/vehicles/${id}`, vehicleBody(input), "Unable to save the vehicle.")
      : await send("POST", `${T}/vehicles`, vehicleBody(input), "Unable to add the vehicle.");
    return liveVehicle(row, riders, routes);
  },
  async setVehicleStatus(id, status) {
    const { routes, riders } = await liveAll();
    if (status === 0 && routes.some((route) => optNum(route.vehicle_id) === id && num(route.status ?? 1) === 1 && riders.some((rider) => num(rider.route_id) === num(route.id)))) {
      conflict("Students ride routes that use this vehicle. Move the route to another vehicle first.");
    }
    return liveVehicle(await send("PATCH", `${T}/vehicles/${id}`, { status }, "Unable to change the vehicle."), riders, routes);
  },
  async routes() {
    const { vehicles, routes, riders } = await liveAll();
    return routes.map((row) => liveRoute(row, vehicles, riders)).sort((a, b) => b.status - a.status || a.name.localeCompare(b.name, undefined, { numeric: true }));
  },
  async route(id) {
    const route = (await liveTransport.routes()).find((row) => row.id === id);
    return route ?? missing("Route");
  },
  async saveRoute(input, id) {
    if (!input.name.trim()) invalid({ name: "Enter the route name." });
    const { vehicles, routes, riders } = await liveAll();
    if (routes.some((row) => num(row.id) !== id && str(row.name).trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("Another route has this name.", "name");
    const vehicle = input.vehicle_id ? vehicles.find((row) => num(row.id) === input.vehicle_id) : null;
    if (vehicle && num(vehicle.status ?? 1) === 0) invalid({ vehicle_id: "This vehicle is inactive." });
    const body = { name: input.name.trim(), description: input.description?.trim() || null, vehicle_id: input.vehicle_id, status: input.status };
    const row = id ? await send("PATCH", `${T}/transport-routes/${id}`, body, "Unable to save the route.") : await send("POST", `${T}/transport-routes`, body, "Unable to add the route.");
    return liveRoute(row, vehicles, riders);
  },
  async setRouteStatus(id, status) {
    const { vehicles, riders } = await liveAll();
    if (status === 0 && riders.some((rider) => num(rider.route_id) === id)) conflict("Students are assigned to this route. Move them first.");
    return liveRoute(await send("PATCH", `${T}/transport-routes/${id}`, { status }, "Unable to change the route."), vehicles, riders);
  },
  async saveStop(routeId, input, id) {
    if (id) return notAvailable("The server can't edit a stop yet. Remove it and add it again.");
    const others = (await allPages(`${T}/transport-stops`, { route_id: routeId }, "Unable to load stops.")).map(liveStop);
    const problems = stopProblems(input, others);
    if (Object.keys(problems).length) invalid(problems);
    const body = { route_id: routeId, name: input.name.trim(), stop_order: input.stop_order, pickup_time: input.pickup_time || null, drop_time: input.drop_time || null, landmark: input.landmark?.trim() || null };
    return liveStop(await send("POST", `${T}/transport-stops`, body, "Unable to add the stop."));
  },
  async removeStop(id) {
    if ((await liveRiders()).some((rider) => optNum(rider.stop_id) === id)) conflict("Students board at this stop. Move them to another stop first.");
    await send("DELETE", `${T}/transport-stops/${id}`, undefined, "Unable to remove the stop.");
  },
  async assignments(query = {}) {
    const { routes, riders } = await liveAll();
    const students = await studentRefs(riders.map((row) => num(row.student_id)));
    const needle = query.q?.trim().toLowerCase() ?? "";
    const rows = riders
      .map((row): TransportAssignment => {
        const route = routes.find((item) => num(item.id) === num(row.route_id));
        const stop = route && Array.isArray(route.stops) ? (route.stops as Raw[]).find((item) => num(item.id) === optNum(row.stop_id)) : undefined;
        const student = students.get(num(row.student_id));
        return {
          id: num(row.id),
          student_id: num(row.student_id),
          student_name: student?.student_name ?? `Student #${num(row.student_id)}`,
          admission_no: student?.admission_no ?? "",
          class_name: student?.class_name ?? "",
          section_name: student?.section_name ?? "",
          route_id: num(row.route_id),
          route_name: route ? str(route.name) : `Route #${num(row.route_id)}`,
          stop_id: num(row.stop_id),
          stop_name: stop ? str(stop.name) : optNum(row.stop_id) ? `Stop #${num(row.stop_id)}` : "—",
          direction: "both",
          start_date: str(row.created_at).slice(0, 10),
          status: 1,
        };
      })
      .filter((row) => !query.routeId || row.route_id === query.routeId)
      .filter((row) => !query.classSectionId || students.get(row.student_id)?.class_section_id === query.classSectionId)
      .filter((row) => !needle || row.student_name.toLowerCase().includes(needle) || row.admission_no.toLowerCase().includes(needle))
      .sort((a, b) => a.route_name.localeCompare(b.route_name) || a.student_name.localeCompare(b.student_name));
    const size = Math.min(query.pageSize ?? 20, 50);
    const page = Math.max(query.page ?? 1, 1);
    return { items: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size };
  },
  async saveAssignment(input, id) {
    if (id) return notAvailable("The server can't edit student transport yet. Remove it and assign the student again.");
    const errors: Record<string, string> = {};
    if (!input.student_id) errors.student_id = "Choose a student.";
    if (!input.route_id) errors.route_id = "Choose a route.";
    if (!input.stop_id) errors.stop_id = "Choose a stop.";
    if (Object.keys(errors).length) invalid(errors);
    const { vehicles, routes, riders } = await liveAll();
    const route = routes.find((row) => num(row.id) === input.route_id) ?? missing("Route");
    if (num(route.status ?? 1) === 0) invalid({ route_id: "This route is inactive." });
    if (riders.some((row) => num(row.student_id) === input.student_id)) conflict("This student already has transport. Remove their current assignment first.", "student_id");
    // The server doesn't check seats, so check them here: a vehicle's seats are shared by its routes.
    const vehicleId = optNum(route.vehicle_id);
    const vehicle = vehicles.find((row) => num(row.id) === vehicleId);
    if (vehicle) {
      const routeIds = new Set(routes.filter((row) => optNum(row.vehicle_id) === vehicleId).map((row) => num(row.id)));
      const problem = capacityProblem(optNum(vehicle.capacity), riders.filter((row) => routeIds.has(num(row.route_id))).length);
      if (problem) conflict(problem, "route_id");
    }
    const row = await send("POST", `${T}/student-transport-assignments`, { student_id: input.student_id, route_id: input.route_id, stop_id: input.stop_id }, "Unable to assign transport.");
    const student = (await studentRefs([input.student_id])).get(input.student_id);
    const route_ = liveRoute(route, vehicles, riders);
    return {
      id: num(row.id),
      student_id: input.student_id,
      student_name: student?.student_name ?? `Student #${input.student_id}`,
      admission_no: student?.admission_no ?? "",
      class_name: student?.class_name ?? "",
      section_name: student?.section_name ?? "",
      route_id: input.route_id,
      route_name: route_.name,
      stop_id: input.stop_id,
      stop_name: route_.stops.find((stop) => stop.id === input.stop_id)?.name ?? "",
      direction: "both",
      start_date: str(row.created_at).slice(0, 10),
      status: 1,
    };
  },
  async removeAssignment(id) {
    await send("DELETE", `${T}/student-transport-assignments/${id}`, undefined, "Unable to remove the assignment.");
  },
};

// ---------- sample data ----------

function riders(routeIds: number[]): number {
  return opsDb().transportAssignments.filter((row) => row.status === 1 && routeIds.includes(row.route_id)).length;
}

function vehicleOut(row: ReturnType<typeof opsDb>["vehicles"][number]): Vehicle {
  const routeIds = opsDb().routes.filter((route) => route.vehicle_id === row.id).map((route) => route.id);
  return { ...row, assigned_students: riders(routeIds) };
}

function routeOut(row: ReturnType<typeof opsDb>["routes"][number]): Route {
  const db = opsDb();
  const vehicle = db.vehicles.find((item) => item.id === row.vehicle_id) ?? null;
  return {
    ...row,
    vehicle_label: vehicle ? `${vehicle.registration_no} (${vehicle.capacity} seats)` : null,
    capacity: vehicle?.capacity ?? null,
    assigned_students: riders([row.id]),
    stops: db.stops.filter((stop) => stop.route_id === row.id).sort((a, b) => a.stop_order - b.stop_order),
  };
}

/** Riders on all routes sharing a vehicle (a vehicle's seats are shared across its routes). */
function vehicleLoad(vehicleId: number | null, excludeAssignmentId?: number): { capacity: number | null; assigned: number } {
  if (!vehicleId) return { capacity: null, assigned: 0 };
  const db = opsDb();
  const vehicle = db.vehicles.find((item) => item.id === vehicleId);
  const routeIds = db.routes.filter((route) => route.vehicle_id === vehicleId).map((route) => route.id);
  const assigned = db.transportAssignments.filter((row) => row.status === 1 && routeIds.includes(row.route_id) && row.id !== excludeAssignmentId).length;
  return { capacity: vehicle?.capacity ?? null, assigned };
}

async function staffName(id: number | null): Promise<string | null> {
  if (!id) return null;
  try {
    return (await peopleService("staff").getEmployee("staff", id)).name;
  } catch {
    return `Staff #${id}`;
  }
}

function assignmentOut(row: ReturnType<typeof opsDb>["transportAssignments"][number]): TransportAssignment {
  const db = opsDb();
  return {
    ...row,
    route_name: db.routes.find((route) => route.id === row.route_id)?.name ?? `Route #${row.route_id}`,
    stop_name: db.stops.find((stop) => stop.id === row.stop_id)?.name ?? `Stop #${row.stop_id}`,
  };
}

export const mockTransport: TransportService = {
  async vehicles() {
    return later(opsDb().vehicles.map(vehicleOut).sort((a, b) => b.status - a.status || a.registration_no.localeCompare(b.registration_no)));
  },
  async saveVehicle(input, id) {
    const db = opsDb();
    const current = id ? db.vehicles.find((row) => row.id === id) ?? missing("Vehicle") : null;
    const problems = vehicleProblems(input, current ? vehicleOut(current).assigned_students : 0);
    if (Object.keys(problems).length) invalid(problems);
    if (db.vehicles.some((row) => row.id !== id && sameRegistration(row.registration_no, input.registration_no))) conflict("Another vehicle has this registration number.", "registration_no");
    for (const [field, staffId] of [["driver_id", input.driver_id], ["helper_id", input.helper_id]] as const) {
      const other = staffId ? db.vehicles.find((row) => row.id !== id && row.status === 1 && (row.driver_id === staffId || row.helper_id === staffId)) : null;
      if (other) conflict(`This person is already assigned to ${other.registration_no}.`, field);
    }
    const row = {
      id: current?.id ?? nextId(db.vehicles),
      registration_no: input.registration_no.trim().toUpperCase(),
      vehicle_type: input.vehicle_type,
      model: input.model?.trim() || null,
      capacity: input.capacity,
      driver_id: input.driver_id,
      driver_name: await staffName(input.driver_id),
      helper_id: input.helper_id,
      helper_name: await staffName(input.helper_id),
      status: input.status,
    };
    if (current) db.vehicles[db.vehicles.indexOf(current)] = row;
    else db.vehicles.push(row);
    opsSave();
    return later(vehicleOut(row));
  },
  async setVehicleStatus(id, status) {
    const db = opsDb();
    const row = db.vehicles.find((item) => item.id === id) ?? missing("Vehicle");
    if (status === 0 && db.routes.some((route) => route.vehicle_id === id && route.status === 1 && riders([route.id]) > 0)) {
      conflict("Students ride routes that use this vehicle. Move the route to another vehicle first.");
    }
    row.status = status;
    opsSave();
    return later(vehicleOut(row));
  },
  async routes() {
    return later(opsDb().routes.map(routeOut).sort((a, b) => b.status - a.status || a.name.localeCompare(b.name, undefined, { numeric: true })));
  },
  async route(id) {
    return later(routeOut(opsDb().routes.find((row) => row.id === id) ?? missing("Route")));
  },
  async saveRoute(input, id) {
    const db = opsDb();
    if (!input.name.trim()) invalid({ name: "Enter the route name." });
    if (db.routes.some((row) => row.id !== id && row.name.trim().toLowerCase() === input.name.trim().toLowerCase())) conflict("Another route has this name.", "name");
    const vehicle = input.vehicle_id ? db.vehicles.find((row) => row.id === input.vehicle_id) ?? missing("Vehicle") : null;
    if (vehicle && vehicle.status === 0) invalid({ vehicle_id: "This vehicle is inactive." });
    const current = id ? db.routes.find((row) => row.id === id) ?? missing("Route") : null;
    if (vehicle && current && current.vehicle_id !== vehicle.id) {
      const load = vehicleLoad(vehicle.id);
      const problem = capacityProblem(load.capacity, load.assigned, riders([current.id]));
      if (problem) conflict(`Moving this route's ${riders([current.id])} students would overfill ${vehicle.registration_no}. ${problem}`, "vehicle_id");
    }
    const row = { id: current?.id ?? nextId(db.routes), name: input.name.trim(), description: input.description?.trim() || null, vehicle_id: input.vehicle_id, status: input.status };
    if (current) db.routes[db.routes.indexOf(current)] = row;
    else db.routes.push(row);
    opsSave();
    return later(routeOut(row));
  },
  async setRouteStatus(id, status) {
    const row = opsDb().routes.find((item) => item.id === id) ?? missing("Route");
    if (status === 0 && riders([id]) > 0) conflict("Students are assigned to this route. Move them first.");
    row.status = status;
    opsSave();
    return later(routeOut(row));
  },
  async saveStop(routeId, input, id) {
    const db = opsDb();
    if (!db.routes.some((row) => row.id === routeId)) missing("Route");
    const others = db.stops.filter((stop) => stop.route_id === routeId);
    const problems = stopProblems(input, others, id);
    if (Object.keys(problems).length) invalid(problems);
    const row = { id: id ?? nextId(db.stops), route_id: routeId, name: input.name.trim(), stop_order: input.stop_order, pickup_time: input.pickup_time || null, drop_time: input.drop_time || null, landmark: input.landmark?.trim() || null };
    const index = db.stops.findIndex((stop) => stop.id === id);
    if (id && index < 0) missing("Stop");
    if (index >= 0) db.stops[index] = row;
    else db.stops.push(row);
    opsSave();
    return later(row);
  },
  async removeStop(id) {
    const db = opsDb();
    if (!db.stops.some((stop) => stop.id === id)) missing("Stop");
    if (db.transportAssignments.some((row) => row.stop_id === id && row.status === 1)) conflict("Students board at this stop. Move them to another stop first.");
    db.stops = db.stops.filter((stop) => stop.id !== id);
    opsSave();
    await later(null);
  },
  async assignments(query = {}) {
    const needle = query.q?.trim().toLowerCase() ?? "";
    const rows = opsDb()
      .transportAssignments.filter((row) => !query.routeId || row.route_id === query.routeId)
      .filter((row) => !query.classSectionId || row.class_section_id === query.classSectionId)
      .filter((row) => !needle || row.student_name.toLowerCase().includes(needle) || row.admission_no.toLowerCase().includes(needle))
      .map(assignmentOut)
      .sort((a, b) => a.route_name.localeCompare(b.route_name) || a.student_name.localeCompare(b.student_name));
    const size = Math.min(query.pageSize ?? 20, 50);
    const page = Math.max(query.page ?? 1, 1);
    return later({ items: rows.slice((page - 1) * size, page * size), total: rows.length, page, page_size: size });
  },
  async saveAssignment(input, id) {
    const db = opsDb();
    const errors: Record<string, string> = {};
    if (!input.student_id) errors.student_id = "Choose a student.";
    if (!input.route_id) errors.route_id = "Choose a route.";
    if (!input.stop_id) errors.stop_id = "Choose a stop.";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(input.start_date)) errors.start_date = "Choose the start date.";
    if (Object.keys(errors).length) invalid(errors);
    const route = db.routes.find((row) => row.id === input.route_id) ?? missing("Route");
    if (route.status === 0) invalid({ route_id: "This route is inactive." });
    if (!db.stops.some((stop) => stop.id === input.stop_id && stop.route_id === route.id)) invalid({ stop_id: "This stop isn't on the chosen route." });
    if (db.transportAssignments.some((row) => row.id !== id && row.student_id === input.student_id && row.status === 1)) {
      conflict("This student already has transport. Edit their current assignment instead.", "student_id");
    }
    const current = id ? db.transportAssignments.find((row) => row.id === id) ?? missing("Transport assignment") : null;
    if (input.status === 1) {
      const load = vehicleLoad(route.vehicle_id, current?.id);
      const problem = capacityProblem(load.capacity, load.assigned);
      if (problem) conflict(problem, "route_id");
    }
    const student = await studentRef(input.student_id);
    const { class_id: _c, session_year_id: _s, ...ref } = student;
    const row = { id: current?.id ?? nextId(db.transportAssignments), ...ref, route_id: input.route_id, stop_id: input.stop_id, direction: input.direction, start_date: input.start_date, status: input.status };
    if (current) db.transportAssignments[db.transportAssignments.indexOf(current)] = row;
    else db.transportAssignments.push(row);
    opsSave();
    return later(assignmentOut(row));
  },
  async removeAssignment(id) {
    const db = opsDb();
    if (!db.transportAssignments.some((row) => row.id === id)) missing("Transport assignment");
    db.transportAssignments = db.transportAssignments.filter((row) => row.id !== id);
    opsSave();
    await later(null);
  },
};

export function transportService(): TransportService {
  return isOpsLive("transport") ? liveTransport : mockTransport;
}
