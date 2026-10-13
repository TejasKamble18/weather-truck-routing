import { describe, it, expect } from "vitest";
import { truckPosition, duration } from "./lib";
import type { Route } from "./api";
describe("truck timing", () => {
  const route = {
    duration_hours: 3,
    vertex_seconds: [0, 7200, 10800],
    geometry: {
      type: "LineString",
      coordinates: [
        [0, 0],
        [2, 0],
        [4, 0],
      ],
    },
  } as Route;
  const departure = "2026-10-12T00:00:00Z";
  it("uses maneuver timing instead of average speed", () => {
    expect(truckPosition(route, "2026-10-12T01:00:00Z", departure)).toEqual([
      1, 0,
    ]);
    expect(truckPosition(route, "2026-10-12T02:30:00Z", departure)).toEqual([
      3, 0,
    ]);
  });
  it("hides trucks before departure and after arrival", () => {
    expect(truckPosition(route, "2026-10-11T23:00:00Z", departure)).toBeNull();
    expect(truckPosition(route, "2026-10-12T04:00:00Z", departure)).toBeNull();
  });
  it("anchors exact arrival at the destination", () => {
    expect(truckPosition(route, "2026-10-12T03:00:00Z", departure)).toEqual([
      4, 0,
    ]);
  });
  it("rolls rounded minutes into hours", () => {
    expect(duration(1.999)).toBe("2h 0m");
  });
});
