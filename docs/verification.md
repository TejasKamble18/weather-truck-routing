# Verification — 13 October 2026

## Browser weather update

- Backend: **91 tests pass**, including pending/completed plans, both weather
  submissions, validation, upload limits, expiry and isolated forecast storage.
- Frontend: **16 tests pass**; TypeScript and Vite production build pass.
- Real Chrome against the local production build and real providers returned
  three Chicago–Dallas routes with 40/40/41 checkpoints and a 148-cell heatmap.
- All four layers, hours 0/24/48, play/pause and route selection were exercised.
  Timeline interactions made zero planner/weather API calls. No JavaScript
  errors or mobile horizontal overflow were observed.
- Browser weather solves the hosted server's observed Open-Meteo rate-limit
  failure without moving risk calculations out of Django. See README for the
  validation limits and client-data authenticity tradeoff.
- Production addresses: https://weather-truck-routing-swart.vercel.app and
  https://weather-truck-routing-api.onrender.com. After deploying `84172b1`, the
  same real Chrome test passed against these public services: three routes,
  40/40/41 checkpoints, all layers and timeline controls, zero timeline API
  requests, no JavaScript errors and no mobile overflow. The first attempt
  during rollout timed out; the repeat after the backend became ready passed.
- All **48 overlay layout checks** pass after waiting for web fonts. The short
  tablet layout received 8 px more clearance below its welcome card.
- GitHub Actions passed for `84172b1`. Browser cache reuse also has a regression
  test ensuring it never extends the original 30-minute forecast freshness.

## Original implementation checks

- Backend: **70 pytest tests passed**; Django system check reported no issues.
- Frontend: **9 Vitest tests passed**; TypeScript and Vite production build passed.
- Follow-up fixes: close comparisons use additional decimals or seconds, with an
  explicit difference below the display precision for very small gaps. Exact
  ranking ties still receive the tie explanation.
- Checkpoint legend and forecast controls now share a vertical layout. The
  deterministic browser regression check passes **24 cases**: empty, four weather
  layers and forecast errors at 320, 390, 768 and 1440 pixels, with at least 12
  pixels between overlays and no horizontal overflow or page errors.
- Follow-up: the layout check now waits for the lazy-loaded map and also runs at
  650 px tall; it caught the welcome card overlapping the legend on a 1366×768
  laptop and on phones, both fixed. **48 cases pass.** Favicon added (no console 404).
- Dependency audit after updating MapLibre and Vitest: **0 known npm vulnerabilities**.
- Desktop Chromium, 1440×1000: map loaded, three real Chicago–Dallas routes,
  40/40/41 checkpoints, route selection, forecast slider, layer switch and play/pause.
- Mobile Chromium, 390×844: no horizontal overflow. Route bounds refit when the
  map container resizes.
- Production preview was tested separately on port 4173, including the bundled
  MapLibre worker. **No page JavaScript errors; zero API calls during timeline
  slider/play interactions.** Map tile requests are separate from API requests.
- Live routing: Chicago–Dallas returned three routes; Denver–Salt Lake City
  returned three; Dallas–Houston returned one with the fewer-routes explanation.
- Live ORS fallback: Chicago–Dallas returned about 966 miles and 5,413 timed
  geometry vertices. Toronto, ON was rejected as outside the USA.
- Live heatmap: Chicago–Dallas returned 148 corridor cells and 49 hourly frames.
- Staged-file check: no configured ORS key, `.env`, virtualenv, node_modules or
  test screenshots included in the source commit.

![Production browser screenshot](screenshot.png)

## Original hosting status (superseded by the browser weather update above)

Render and Vercel account connections are needed to create the hosted services.
The repository includes their configuration; hosted behavior has **not** been
verified. The final deliverables also need the user's recorded Loom walkthrough.

The Vite build reports a large map chunk (~1.05 MB, ~287 KB gzip). It is lazy
loaded separately from the ~242 KB (~77 KB gzip) application bundle. This is a
known tradeoff of including the vector map renderer, not a build failure.
