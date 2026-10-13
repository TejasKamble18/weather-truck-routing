export type Level = "low" | "moderate" | "high" | "severe" | "no_travel";
export type Layer = "risk" | "wind" | "rain" | "snow";
export interface Checkpoint {
  mile: number;
  lon: number;
  lat: number;
  eta: string;
  weather: {
    wind_mph: number;
    gust_mph: number;
    rain_in_hr: number;
    snow_in_hr: number;
    forecast_time: string;
  };
  risk: { level: Level; score: number; driver: string; load_adjusted: boolean };
}
export interface Route {
  id: string;
  name: string;
  source: string;
  distance_miles: number;
  duration_hours: number;
  arrival: string;
  geometry: { type: "LineString"; coordinates: number[][] };
  vertex_seconds: number[];
  checkpoints: Checkpoint[];
  summary: {
    miles_by_level: Record<Level, number>;
    average_risk: number;
    worst_level: Level;
    no_travel_warning: boolean;
  };
  rank: number;
  recommended: boolean;
}
export interface Plan {
  plan_id: string;
  origin: { label: string; lat: number; lon: number };
  destination: { label: string; lat: number; lon: number };
  departure: string;
  load_lbs: number;
  interval_miles: number;
  forecast_start: string;
  routes: Route[];
  notes: string[];
  recommendation: { route_id: string; reason: string };
  heatmap_url: string;
}
export interface Heatmap {
  start: string;
  hours: number;
  cells: number[][];
  layers: Record<Layer, number[][]>;
}
export interface PlanInput {
  origin: string;
  destination: string;
  departure: string;
  load_lbs: number;
  interval_miles: number;
}
const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
export async function api<T>(
  path: string,
  signal: AbortSignal,
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(base + path, {
      signal,
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Cannot reach the planner. Check your connection and try again.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail
          ? Object.entries(detail)
              .map(
                ([k, v]) =>
                  `${k.replaceAll("_", " ")}: ${Array.isArray(v) ? v.join(" ") : v}`,
              )
              .join(" · ")
          : "The service is temporarily unavailable. Please retry.",
    );
  }
  if (!data)
    throw new Error(
      "The service returned an unreadable response. Please retry.",
    );
  return data as T;
}
