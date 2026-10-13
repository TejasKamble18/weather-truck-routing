import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

// Deterministic UI regression check: no routing/weather provider or API key needed.
const start = new Date().toISOString();
const departure = new Date(Date.now() + 86400000).toISOString();
const arrival = new Date(Date.parse(departure) + 3600000).toISOString();
const plan = {
  plan_id: "overlay-test",
  origin: { label: "Dallas, TX", lon: -96.8, lat: 32.78 },
  destination: { label: "Houston, TX", lon: -95.37, lat: 29.76 },
  departure,
  load_lbs: 35000,
  interval_miles: 25,
  forecast_start: start,
  routes: [
    {
      id: "A",
      name: "Test route",
      source: "fixture",
      distance_miles: 240,
      duration_hours: 1,
      arrival,
      rank: 1,
      recommended: true,
      checkpoints: [],
      geometry: {
        type: "LineString",
        coordinates: [
          [-96.8, 32.78],
          [-95.37, 29.76],
        ],
      },
      vertex_seconds: [0, 3600],
      summary: {
        miles_by_level: {
          low: 240,
          moderate: 0,
          high: 0,
          severe: 0,
          no_travel: 0,
        },
        average_risk: 0,
        worst_level: "low",
        no_travel_warning: false,
      },
    },
  ],
  recommendation: { route_id: "A", reason: "Only one route in this test." },
  notes: [],
  heatmap_url: "/api/plan/overlay-test/heatmap/",
};
const heatmap = {
  start,
  hours: 49,
  cells: [[-96, 31]],
  layers: Object.fromEntries(
    ["risk", "wind", "rain", "snow"].map((layer) => [
      layer,
      Array.from({ length: 49 }, () => [0]),
    ]),
  ),
};
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.BROWSER_EXECUTABLE || undefined,
});
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("https://tiles.openfreemap.org/**", (route) =>
    route.fulfill({ json: { version: 8, sources: {}, layers: [] } }),
  );
  let failWeather = false;
  await page.route("**/api/**", (route) => {
    const isPlan = route.request().method() === "POST";
    return route.fulfill({
      status: !isPlan && failWeather ? 502 : 200,
      json: isPlan
        ? plan
        : failWeather
          ? {
              error: "weather_unavailable",
              detail:
                "The forecast provider is temporarily unavailable. Please retry the corridor weather request.",
            }
          : heatmap,
    });
  });
  await page.goto(process.env.PREVIEW_URL || "http://127.0.0.1:5173/");
  async function checkLayout(state) {
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 844 });
      const layout = await page.evaluate(() => {
        const legend = document
          .querySelector(".map-legend")
          .getBoundingClientRect();
        const controls = document
          .querySelector(".forecast-controls")
          .getBoundingClientRect();
        return {
          gap: controls.top - legend.bottom,
          overflow: document.documentElement.scrollWidth > innerWidth,
        };
      });
      assert.ok(
        layout.gap >= 11,
        `${state} at ${width}px: overlays overlap (${layout.gap}px gap)`,
      );
      assert.equal(
        layout.overflow,
        false,
        `${state} at ${width}px: horizontal overflow`,
      );
    }
  }
  await checkLayout("empty");
  await page.getByRole("button", { name: "Find my routes" }).click();
  await page.waitForFunction(
    () => !document.querySelector('[aria-label="Play forecast"]').disabled,
  );
  for (const layer of ["risk", "wind", "rain", "snow"]) {
    await page.getByRole("button", { name: layer, exact: true }).click();
    await checkLayout(layer);
  }
  failWeather = true;
  await page.getByRole("button", { name: "Find my routes" }).click();
  await page.getByRole("button", { name: "Retry heatmap" }).waitFor();
  await checkLayout("forecast error");
  assert.deepEqual(errors, []);
  console.log(
    "PASS: 24 overlay checks across empty, four layers and error states at 320/390/768/1440px; no page errors.",
  );
} finally {
  await browser.close();
}
