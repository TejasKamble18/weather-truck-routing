import { api } from "./api";

export interface ForecastRequest {
  cells: [number, number][];
  start_date: string;
  end_date: string;
  hourly: string[];
  submit_url: string;
}
export interface PendingWeather {
  status: "weather_required";
  forecast_request: ForecastRequest;
}
type Forecast = {
  latitude: number;
  longitude: number;
  hourly: Record<string, unknown[]>;
};
type Entry = { cell: [number, number]; forecast: Forecast };
const cache = new Map<string, { expires: number; forecast: Forecast }>();
const MAX_CACHE = 1000;

function cacheKey(cell: number[], spec: ForecastRequest) {
  return JSON.stringify([cell, spec.start_date, spec.end_date, spec.hourly]);
}

async function pause(ms: number, signal: AbortSignal) {
  signal.throwIfAborted();
  await new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

async function download(
  cells: [number, number][],
  spec: ForecastRequest,
  signal: AbortSignal,
): Promise<Forecast[]> {
  const query = new URLSearchParams({
    latitude: cells.map((c) => c[1]).join(","),
    longitude: cells.map((c) => c[0]).join(","),
    hourly: spec.hourly.join(","),
    start_date: spec.start_date,
    end_date: spec.end_date,
    wind_speed_unit: "mph",
    precipitation_unit: "inch",
    timezone: "UTC",
  });
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(
      `https://api.open-meteo.com/v1/forecast?${query}`,
      {
        signal: AbortSignal.any([signal, AbortSignal.timeout(30000)]),
      },
    );
    if ([429, 502, 503, 504].includes(response.status)) {
      const header = response.headers.get("Retry-After");
      const delay =
        header === null
          ? 1500
          : /^\d+$/.test(header)
            ? Number(header) * 1000
            : Date.parse(header) - Date.now();
      if (
        attempt === 0 &&
        Number.isFinite(delay) &&
        delay >= 0 &&
        delay <= 10000
      ) {
        await pause(delay, signal);
        continue;
      }
      throw new Error(
        response.status === 429
          ? "The weather service is rate-limiting requests. Please wait a few minutes and try again."
          : "The weather service is unavailable. Please try again later.",
      );
    }
    if (!response.ok)
      throw new Error(
        "The weather service is unavailable. Please try again later.",
      );
    const data = await response.json();
    const records: Forecast[] = Array.isArray(data) ? data : [data];
    if (
      records.length !== cells.length ||
      records.some(
        (r, i) =>
          !r ||
          !Number.isFinite(r.latitude) ||
          !Number.isFinite(r.longitude) ||
          Math.abs(r.latitude - cells[i][1]) > 0.25 ||
          Math.abs(r.longitude - cells[i][0]) > 0.25 ||
          !r.hourly,
      )
    ) {
      throw new Error(
        "The weather service returned incomplete forecasts. Please try again.",
      );
    }
    return records;
  }
  throw new Error("Could not download the weather.");
}

export async function completeWeather<T>(
  value: T | PendingWeather,
  signal: AbortSignal,
): Promise<T> {
  if ((value as PendingWeather).status !== "weather_required")
    return value as T;
  const spec = (value as PendingWeather).forecast_request;
  const controller = new AbortController();
  const combined = AbortSignal.any([signal, controller.signal]);
  const entries = new Map<string, Entry>();
  const missing: [number, number][] = [];
  for (const cell of spec.cells) {
    const hit = cache.get(cacheKey(cell, spec));
    if (hit && hit.expires > Date.now())
      entries.set(cell.toString(), { cell, forecast: hit.forecast });
    else missing.push(cell);
  }
  const chunks = Array.from(
    { length: Math.ceil(missing.length / 100) },
    (_, i) => missing.slice(i * 100, i * 100 + 100),
  );
  let next = 0;
  async function worker() {
    while (next < chunks.length) {
      combined.throwIfAborted();
      const chunk = chunks[next++];
      const forecasts = await download(chunk, spec, combined);
      chunk.forEach((cell, i) =>
        entries.set(cell.toString(), { cell, forecast: forecasts[i] }),
      );
    }
  }
  try {
    await Promise.all([worker(), worker()]);
    const forecasts = spec.cells.map((cell) => entries.get(cell.toString())!);
    const result = await api<T>(spec.submit_url, combined, { forecasts });
    // Cache only after Django accepted the forecasts; memory-only, limited to this page.
    forecasts.forEach(({ cell, forecast }) => {
      const key = cacheKey(cell, spec);
      const previous = cache.get(key);
      const expires =
        previous?.forecast === forecast
          ? previous.expires
          : Date.now() + 30 * 60000;
      cache.delete(key);
      cache.set(key, { expires, forecast });
      if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value!);
    });
    return result;
  } catch (error) {
    controller.abort();
    // A rejected upload must not keep retrying an already cached invalid record.
    spec.cells.forEach((cell) => cache.delete(cacheKey(cell, spec)));
    if (signal.aborted) throw signal.reason;
    if (
      error instanceof TypeError ||
      (error instanceof DOMException && error.name === "TimeoutError")
    ) {
      throw new Error(
        "Could not reach the weather service. Check your connection and try again.",
      );
    }
    throw error;
  }
}
