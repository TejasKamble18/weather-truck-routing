import { afterEach, beforeEach, expect, it, vi } from "vitest";

beforeEach(() => vi.resetModules());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const spec = (cells: [number, number][] = [[-90, 40]]) => ({
  cells,
  start_date: "2026-10-12",
  end_date: "2026-10-15",
  hourly: ["wind_speed_10m", "wind_gusts_10m", "rain", "snowfall"],
  submit_url: "/api/plan/test/weather/",
});
function provider(url: string) {
  const u = new URL(url);
  const lons = u.searchParams.get("longitude")!.split(",").map(Number);
  return lons.map((lon, i) => ({
    longitude: lon,
    latitude: Number(u.searchParams.get("latitude")!.split(",")[i]),
    hourly: {},
  }));
}

it("passes completed responses through without downloading", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const { completeWeather } = await import("./weather");
  expect(
    await completeWeather({ hours: 49 }, new AbortController().signal),
  ).toEqual({ hours: 49 });
  expect(fetch).not.toHaveBeenCalled();
});

it("batches at 100 cells with at most two downloads and reuses validated weather", async () => {
  let active = 0,
    maxActive = 0,
    downloads = 0;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (!url.startsWith("https://api.open-meteo.com/")) {
      const body = JSON.parse(init.body as string);
      expect(body.forecasts.length).toBe(205);
      return Response.json({ status: "complete" });
    }
    downloads++;
    active++;
    maxActive = Math.max(maxActive, active);
    const records = provider(url);
    expect(records.length).toBeLessThanOrEqual(100);
    await new Promise((r) => setTimeout(r, 5));
    active--;
    return Response.json(records);
  });
  vi.stubGlobal("fetch", fetch);
  const { completeWeather } = await import("./weather");
  const pending = {
    status: "weather_required" as const,
    forecast_request: spec(
      Array.from({ length: 205 }, (_, i) => [-90 + i / 1000, 40]),
    ),
  };
  await completeWeather(pending, new AbortController().signal);
  await completeWeather(pending, new AbortController().signal);
  expect(downloads).toBe(3);
  expect(maxActive).toBe(2);
});

it("stops after one short retry on a rate limit", async () => {
  const fetch = vi.fn(
    async () =>
      new Response("", { status: 429, headers: { "Retry-After": "0" } }),
  );
  vi.stubGlobal("fetch", fetch);
  const { completeWeather } = await import("./weather");
  await expect(
    completeWeather(
      { status: "weather_required", forecast_request: spec() },
      new AbortController().signal,
    ),
  ).rejects.toThrow("rate-limiting");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("does not retry a long Retry-After or submit incomplete provider responses", async () => {
  const fetch = vi.fn(
    async () =>
      new Response("", { status: 429, headers: { "Retry-After": "60" } }),
  );
  vi.stubGlobal("fetch", fetch);
  const { completeWeather } = await import("./weather");
  const pending = {
    status: "weather_required" as const,
    forecast_request: spec(),
  };
  await expect(
    completeWeather(pending, new AbortController().signal),
  ).rejects.toThrow("rate-limiting");
  expect(fetch).toHaveBeenCalledTimes(1);
  fetch.mockImplementation(async () => Response.json([]));
  await expect(
    completeWeather(pending, new AbortController().signal),
  ).rejects.toThrow("incomplete");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("cancels before downloads when the plan has been replaced", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const { completeWeather } = await import("./weather");
  const controller = new AbortController();
  controller.abort();
  await expect(
    completeWeather(
      { status: "weather_required", forecast_request: spec() },
      controller.signal,
    ),
  ).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});

it("does not cache forecasts rejected by Django", async () => {
  let downloads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("https://api.open-meteo.com/")) {
        downloads++;
        return Response.json(provider(url));
      }
      return Response.json({ detail: "Invalid forecast" }, { status: 400 });
    }),
  );
  const { completeWeather } = await import("./weather");
  const pending = {
    status: "weather_required" as const,
    forecast_request: spec(),
  };
  for (let i = 0; i < 2; i++) {
    await expect(
      completeWeather(pending, new AbortController().signal),
    ).rejects.toThrow("Invalid forecast");
  }
  expect(downloads).toBe(2);
});
