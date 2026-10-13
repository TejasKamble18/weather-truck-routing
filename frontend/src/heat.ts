import type { Layer } from "./api";
import { colors } from "./lib";

const clear = "rgba(0,0,0,0)";
/** Low risk / light wind: the Low colour, faint, so the corridor reads as one surface. */
export const faintLow = "rgba(41,158,130,0.35)";

// [threshold, colour]: a value takes the colour of the highest threshold it reaches.
// Bands mirror the assessment's risk rules, so the weather layer and the checkpoint
// dots use the same colours for the same conditions. "No Travel" for rain and snow is
// strictly greater than the Severe upper bound.
const bands: Record<Layer, [number, string][]> = {
  risk: [[0, faintLow], [1, colors.moderate], [2, colors.high], [3, colors.severe], [4, colors.no_travel]],
  wind: [[0, faintLow], [15, colors.low], [25, colors.moderate], [35, colors.high], [45, colors.severe], [55, colors.no_travel]],
  rain: [[0, clear], [0.01, colors.low], [0.1, colors.moderate], [0.25, colors.high], [0.5, colors.severe], [1.000001, colors.no_travel]],
  snow: [[0, clear], [0.01, colors.low], [0.5, colors.moderate], [1, colors.high], [2, colors.severe], [3.000001, colors.no_travel]],
};

export const legendLabels: Record<Layer, string[]> = {
  risk: ["Moderate", "High", "Severe", "No Travel"],
  wind: ["15+", "25+", "35+", "45+", "55+ mph"],
  rain: ["Any", "0.1+", "0.25+", "0.5+", ">1 in/h"],
  snow: ["Any", "0.5+", "1+", "2+", ">3 in/h"],
};

export function heatStops(layer: Layer): [number, string][] {
  return bands[layer];
}

export function heatColor(layer: Layer, value: number): string {
  let colour = bands[layer][0][1];
  for (const [threshold, c] of bands[layer]) if (value >= threshold) colour = c;
  return colour;
}

/** MapLibre `step` expression colouring each cell by its own value. */
export function heatColorExpression(layer: Layer) {
  const [[, first], ...rest] = bands[layer];
  return ["step", ["get", "value"], first, ...rest.flat()];
}

/** Grid spacing in degrees, from the distinct cell latitudes and longitudes. */
export function cellStep(cells: number[][]): number {
  let step = Infinity;
  for (const axis of [0, 1]) {
    const values = [...new Set(cells.map((c) => c[axis]))].sort((a, b) => a - b);
    for (let i = 1; i < values.length; i++)
      step = Math.min(step, Math.round((values[i] - values[i - 1]) * 1e4) / 1e4);
  }
  return Number.isFinite(step) && step > 0 ? step : 0.5;
}

/** Circle radius (px) at zoom 0 that lets neighbouring cells blend into one surface. */
export function cellRadiusAtZoom0(cells: number[][]): number {
  const meanLat = cells.length ? cells.reduce((s, c) => s + c[1], 0) / cells.length : 38;
  const pxPerDegree = 256 / 360;
  // 1.6× the cell spacing so blurred neighbours overlap into a continuous field.
  return (1.6 * cellStep(cells) * pxPerDegree) / Math.cos((meanLat * Math.PI) / 180);
}
