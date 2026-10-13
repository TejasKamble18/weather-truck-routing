import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.BROWSER_EXECUTABLE || undefined,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.goto(process.env.PREVIEW_URL || "http://127.0.0.1:5173/", {
  waitUntil: "networkidle",
});
await page
  .getByRole("heading", { name: "Better roads. Clearer decisions." })
  .waitFor();
await page.locator('[data-map-ready="true"]').waitFor({ timeout: 60000 });
await mkdir("test-results", { recursive: true });
await page.screenshot({ path: "test-results/desktop-empty.png" });
const planResponse = page.waitForResponse(
  (r) =>
    /\/api\/plan\/[^/]+\/weather\/$/.test(r.url()) &&
    r.request().method() === "POST",
  { timeout: 120000 },
);
await page.getByRole("button", { name: "Find my routes" }).click();
const response = await planResponse;
const plan = await response.json();
if (!response.ok()) throw Error(JSON.stringify(plan));
await page
  .getByRole("button", { name: "Play forecast", exact: true })
  .waitFor({ state: "visible" });
await page.waitForFunction(
  () => !document.querySelector('[aria-label="Play forecast"]').disabled,
  null,
  { timeout: 120000 },
);
await page
  .locator(".sidebar")
  .evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: "instant" }));
await page.screenshot({ path: "test-results/desktop-plan.png" });
let requests = 0;
page.on("request", (r) => {
  if (r.url().includes("/api/") || r.url().includes("api.open-meteo.com"))
    requests++;
});
for (const hour of ["0", "24", "48"]) {
  await page.getByRole("slider", { name: "Forecast hour" }).fill(hour);
  for (const layer of ["risk", "wind", "rain", "snow"]) {
    await page.getByRole("button", { name: layer, exact: true }).click();
  }
}
await page.getByRole("button", { name: "Play forecast", exact: true }).click();
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Pause forecast", exact: true }).click();
if (requests)
  throw Error("Timeline fetched API data instead of using prepared frames");
if (await page.getByRole("button", { name: /Route B/ }).count())
  await page.getByRole("button", { name: /Route B/ }).click();
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(1000);
await page.screenshot({ path: "test-results/mobile-plan.png", fullPage: true });
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth > innerWidth,
);
if (overflow) throw Error("Mobile horizontal overflow");
console.log(
  JSON.stringify({
    routes: plan.routes.length,
    checkpoints: plan.routes.map((r) => r.checkpoints.length),
    timelineApiRequests: requests,
    pageErrors: errors,
    mobileOverflow: overflow,
  }),
);
await browser.close();
if (errors.length) process.exit(1);
