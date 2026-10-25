import { describe, expect, it } from "vitest";
import { capacityProblem, sameRegistration, seatsLeft, stopProblems, vehicleProblems } from "@/lib/ops/transport-rules";

describe("capacity", () => {
  it("allows a student while seats remain and refuses one past capacity", () => {
    expect(capacityProblem(40, 39)).toBe("");
    expect(capacityProblem(40, 40)).toMatch(/40 seats and 40 are taken/);
    expect(capacityProblem(null, 100)).toBe("");
    expect(seatsLeft(40, 37)).toBe(3);
    expect(seatsLeft(null, 3)).toBeNull();
  });
});

describe("vehicleProblems", () => {
  const base = { registration_no: "KA 01 AB 1234", vehicle_type: "bus" as const, model: null, capacity: 40, driver_id: 1, helper_id: 2, status: 1 as const };
  it("accepts a valid vehicle", () => {
    expect(vehicleProblems(base)).toEqual({});
  });
  it("refuses capacity below current riders and the same person as driver and helper", () => {
    expect(vehicleProblems({ ...base, capacity: 10 }, 12).capacity).toMatch(/12 students/);
    expect(vehicleProblems({ ...base, helper_id: 1 }).helper_id).toBeTruthy();
    expect(vehicleProblems({ ...base, registration_no: "!" }).registration_no).toBeTruthy();
  });
  it("treats registrations with different spacing as the same", () => {
    expect(sameRegistration("KA 01 AB 1234", "ka01ab-1234")).toBe(true);
  });
});

describe("stopProblems", () => {
  const others = [{ id: 1, name: "Gate", stop_order: 1 }];
  it("refuses duplicate names and orders on a route, and bad times", () => {
    const errors = stopProblems({ name: "gate", stop_order: 1, pickup_time: "7:5", drop_time: "25:00", landmark: null }, others);
    expect(errors.name).toBeTruthy();
    expect(errors.stop_order).toBeTruthy();
    expect(errors.pickup_time).toBeTruthy();
    expect(errors.drop_time).toBeTruthy();
  });
  it("lets a stop keep its own name and order when edited", () => {
    expect(stopProblems({ name: "Gate", stop_order: 1, pickup_time: "07:05", drop_time: null, landmark: null }, others, 1)).toEqual({});
  });
});
