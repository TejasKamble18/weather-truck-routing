import { describe, it, expect } from "vitest";
import { cellStep, faintLow, heatColor, heatStops } from "./heat";
import { colors } from "./lib";

describe("weather layer colours follow the actual values", () => {
  it("colours a No Travel risk cell with the No Travel colour, however isolated", () => {
    expect(heatColor("risk", 4)).toBe(colors.no_travel);
    expect(heatColor("risk", 2)).toBe(colors.high);
  });
  it("uses the assessment thresholds for raw weather layers", () => {
    expect(heatColor("wind", 55)).toBe(colors.no_travel);
    expect(heatColor("wind", 45)).toBe(colors.severe);
    expect(heatColor("rain", 1.01)).toBe(colors.no_travel);
    expect(heatColor("snow", 2)).toBe(colors.severe);
  });
  it("leaves dry cells transparent but tints low risk and light wind so the corridor reads as one surface", () => {
    expect(heatColor("rain", 0)).toBe("rgba(0,0,0,0)");
    expect(heatColor("snow", 0)).toBe("rgba(0,0,0,0)");
    expect(heatColor("risk", 0)).toBe(faintLow);
    expect(heatColor("wind", 5)).toBe(faintLow);
  });
  it("builds ascending MapLibre stops for every layer", () => {
    for (const layer of ["risk", "wind", "rain", "snow"] as const) {
      const values = heatStops(layer).map(([v]) => v);
      expect(values).toEqual([...values].sort((a, b) => a - b));
    }
  });
});

describe("cell spacing", () => {
  it("finds the grid step from the cell centres", () => {
    expect(cellStep([[-90, 40], [-89.5, 40], [-89.5, 40.5]])).toBe(0.5);
    expect(cellStep([[-90, 40], [-89, 40]])).toBe(1);
    expect(cellStep([[-90, 40]])).toBe(0.5);
  });
});
