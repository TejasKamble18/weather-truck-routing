import type { Level, Route } from "./api";
export const levels: Level[] = [
  "low",
  "moderate",
  "high",
  "severe",
  "no_travel",
];
export const colors: Record<Level, string> = {
  low: "#299e82",
  moderate: "#e5bc51",
  high: "#e88c4e",
  severe: "#d24c55",
  no_travel: "#843861",
};
export const routeColors: Record<string, string> = {
  A: "#167965",
  B: "#6579bd",
  C: "#c78e47",
};
export const label = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const duration = (hours: number) =>
  `${Math.floor(Math.round(hours * 60) / 60)}h ${Math.round(hours * 60) % 60}m`;
export const dateTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(new Date(value));
export function truckPosition(
  route: Route,
  time: string,
  departure: string,
): number[] | null {
  const seconds = (Date.parse(time) - Date.parse(departure)) / 1000;
  if (seconds < 0 || seconds > route.duration_hours * 3600) return null;
  const times = route.vertex_seconds,
    coords = route.geometry.coordinates;
  let lo = 0,
    hi = times.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= seconds) lo = mid;
    else hi = mid;
  }
  const f =
    times[hi] > times[lo] ? (seconds - times[lo]) / (times[hi] - times[lo]) : 0;
  return coords[lo].map((v, i) => v + (coords[hi][i] - v) * f);
}
export function localInputNow() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}
