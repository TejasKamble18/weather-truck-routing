# Waycast — Weather-aware truck routing

A React + Django application that compares truck routes against the weather **at
the time the truck reaches each checkpoint**. Enter two US locations, departure
time, load weight and a checkpoint interval. The app ranks up to three distinct
routes, explains its recommendation, and shows a 48-hour corridor weather map.

![Waycast route comparison and weather map](docs/screenshot.png)

See [verification notes](docs/verification.md) for test results and hosting status.

## Run locally

Requires Python 3.14 and Node.js 24. Commands below use PowerShell, from the repo root.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
# Optional for known US cities, required for address/coordinate lookup and ORS fallback:
# Set ORS_API_KEY in backend/.env to your OpenRouteService key.
cd backend
..\.venv\Scripts\python manage.py runserver
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to Django on port 8000. You do
not need `frontend/.env` for local development. On macOS/Linux, use
`.venv/bin/python` instead of `.venv\Scripts\python`.

Try **Chicago, IL → Dallas, TX**, **Denver, CO → Salt Lake City, UT**, or
**Dallas, TX → Houston, TX**. The first two returned three routes in live checks;
the last returned one distinct route. Provider results can change.

## What the app does

- Valhalla truck routing supplies alternatives. If needed, OpenRouteService's
  `driving-hgv` profile supplies routes through offset waypoints. Duplicates and
  routes over 40% longer than the shortest candidate are removed.
- Known `City, ST` inputs resolve from the included US Census places data.
  Addresses use ORS geocoding; coordinate inputs get a reverse-country check.
- Checkpoints appear every **10, 25 or 50 miles**, including both endpoints.
  ETA follows maneuver durations interpolated along route geometry, rather than
  assuming the same speed for the whole trip.
- Open-Meteo hourly weather is sampled at the nearest forecast hour to each ETA.
  Checkpoints share cached forecasts on a 0.25° grid. Missing or invalid weather
  produces an error; it is never silently treated as safe.
- Route cards show distance, driving time, arrival, miles per risk level and
  average risk. Click a card or map route to select it; hover a checkpoint for
  its weather, arrival time and deciding risk condition.
- The corridor heatmap loads separately after the routes. Its slider covers
  **0–48 hours from the plan's current UTC hour**. Slider and play controls use
  downloaded frames, with no API requests. Truck markers follow route timing;
  they are hidden before departure and after arrival.
- Each corridor cell is drawn as a soft circle **coloured by its own value**, using
  the same bands as checkpoint risk (e.g. wind 25/35/45/55 mph). A density heatmap
  was avoided on purpose: it would show an isolated No Travel cell as mild and
  overlapping calm cells as severe.
- The timeline changes the corridor overlay, **not the route recommendation**.
  Change departure and plan again to compare a different departure time.

## Risk rules

| Level | Sustained wind (mph) | Rain (in/hour) | Snow (in/hour) |
|---|---:|---:|---:|
| Low (0) | <25 | <0.10 | <0.5 |
| Moderate (1) | 25–<35 | 0.10–<0.25 | 0.5–<1 |
| High (2) | 35–<45 | 0.25–<0.50 | 1–<2 |
| Severe (3) | 45–<55 | 0.50–1.00 inclusive | 2–3 inclusive |
| No Travel (4) | ≥55 | >1.00 | >3 |

Wind from 45 to below 55 mph becomes No Travel when load **exceeds 30,000 lb**.
Wind from 35 to below 45 mph becomes Severe when load **exceeds 40,000 lb**.
Gusts are displayed but do not drive the assessment's sustained-wind rule.
The worst of adjusted wind, rain and snow determines checkpoint risk.

Each checkpoint represents the distance between midpoints to its neighbors.
Those distances sum to the route length. The average risk is distance-weighted.
Recommendation order is lexicographic: **No Travel miles, Severe miles, High
miles, average risk, driving time**. No Travel precedes the brief's order because
it is the highest risk. If every route contains it, the app suggests delaying
departure rather than presenting the winner as a safe route.

## API

`POST /api/plan/`

```json
{
  "origin": "Chicago, IL",
  "destination": "Dallas, TX",
  "load_lbs": 35000,
  "interval_miles": 25
}
```

`departure` is optional (defaults to now); when provided, use an ISO 8601
timestamp with timezone. Supported range: one hour ago through seven days ahead.
Load is 0–80,000 lb. Responses contain a `plan_id`, resolved locations,
`routes`, `recommendation`, `notes` and `heatmap_url`. Each route includes GeoJSON
geometry, timing, checkpoints with weather and risk, and its ranked summary.

`GET /api/plan/<plan_id>/heatmap/` returns `cells` in `[longitude, latitude]`
order and `layers.risk|wind|rain|snow[hour][cell]`, with 49 hourly frames.

`GET /api/health/` returns `{"status":"ok"}`.

Errors use `{"error":"code","detail":"message or field errors"}`. Input errors
return 400, unknown/out-of-US locations or expired plans 404, unavailable forecast
coverage 422, provider failures 502, missing provider configuration 503 and
provider timeouts 504. API requests are limited to 30/minute per anonymous client;
health checks are exempt.

## Implementation and performance

```text
backend/planner/
  geo.py, checkpoints.py   Geometry and maneuver-based checkpoint timing
  geocoding.py, datasets.py Local places plus geocoding fallback
  routing/                 Valhalla, ORS, distinct-route selection
  weather.py               Multi-location weather, units, caching and coverage checks
  risk.py, ranking.py       Pure assessment rules and recommendation
  heatmap.py, services.py   Corridor frames and plan orchestration
  serializers.py, views.py  API validation and responses
frontend/src/
  components/              Form, route cards, MapLibre map, timeline
  api.ts, lib.ts            API types, formatting and animated truck timing
```

Forecast requests use batches of at most 100 cells and up to three concurrent
requests. Weather and routes cache for 30 minutes; plans last two hours. A
file-backed cache is shared by Gunicorn workers on one Render instance. It is
not durable and is not shared across multiple instances. Use Redis for scaling.
The API compresses large geometry responses. The map loads as a separate chunk,
and its worker is bundled explicitly for MapLibre 6/Vite.

Observed local live checks: Chicago–Dallas plan **6.4 seconds**, then its
148-cell/49-frame heatmap **3.5 seconds**; Denver–Salt Lake plan **2.5 seconds**.
These are individual measurements, not guaranteed production latency. Network,
provider load, cache state and hosting cold starts affect response times.

## Tests

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python manage.py check
cd ..\frontend
npm test
npm run build
```

Tests cover risk and load boundaries, distance attribution, ranking priorities,
polyline decoding, maneuver timing, duplicate routes, forecast units and missing
data, caching, API validation, error responses and the plan pipeline. Frontend
tests cover truck timing, trip boundaries and duration rounding. GitHub Actions
runs backend tests and frontend tests/build on pushes and pull requests.

With both local servers running, `node scripts/browser-check.mjs` from `frontend`
checks a real trip, map load, timeline controls and mobile overflow, and saves
screenshots under ignored `frontend/test-results`. Install a Playwright Chromium
browser with `npx playwright install chromium`, or set `BROWSER_EXECUTABLE` to an
existing compatible Chromium executable. These live checks depend on providers.

For the responsive overlay regression check, run `node scripts/check-overlay-layout.mjs`
with the frontend server running. It mocks the API and base map, so it needs no
backend server or API key. It checks all four layers plus empty/error states at
320, 390, 768 and 1440 pixels wide, each 844 and 650 pixels tall (a 1366×768 laptop). `PREVIEW_URL` can target a production preview.

## Deploy

### Django on Render

1. Connect this GitHub repository to Render and create a Blueprint from
   **`render.yaml`**. It defines the free Python service, Gunicorn and health check.
2. Set `ORS_API_KEY` and `CORS_ALLOWED_ORIGINS` (the exact frontend origin, such as
   `https://your-project.vercel.app`, without a trailing slash). The Blueprint
   generates `DJANGO_SECRET_KEY`; `DEBUG` is off. Render's hostname is added to
   Django's allowed hosts automatically.
3. Verify `https://<service>.onrender.com/api/health/` returns `ok`.

There are no user accounts or persistent application models, so this assessment
does not need a managed database or migrations. The ephemeral cache is separate
from the bundled, read-only Census CSV.

### React on Vercel

1. Import this repository and set **Root Directory: `frontend`** and framework
   **Vite**. Build command: `npm run build`; output directory: `dist`.
2. Set `VITE_API_URL` to the Render service origin (no `/api` suffix or trailing
   slash), then deploy. This variable is embedded at build time.
3. Set Render's `CORS_ALLOWED_ORIGINS` to the resulting Vercel URL and verify an
   actual plan and heatmap from the hosted frontend.

Render's free service can spin down after inactivity. The UI shows a delayed-load
message while waiting. A health check does not guarantee a warm instance or
provider availability; allow for a cold start during the walkthrough.

Deployment configuration is included; a hosted URL still requires account access
and a successful deployment. Never commit `.env` files or API keys.

## Limits and assumptions

- Public routing/weather services have quotas and no availability guarantee.
- Fewer than three distinct truck routes may exist. No synthetic straight-line
  route is presented as a drivable option.
- Truck routing uses provider defaults; load weight adjusts weather risk. The
  app does not accept vehicle dimensions or gross vehicle weight for routing.
- ETAs exclude rest breaks, live traffic and hours-of-service rules.
- Forecasts use the nearest hourly value and approximate spatial grids, not
  real-time roadside observations. Trips beyond available forecast coverage fail
  explicitly. Heatmap cells are capped at 250 and coarsened for long corridors.
- Heat intensity is a spatially smoothed visualization. Checkpoint popups contain
  the actual forecast numbers used in the risk calculation.
- Free hosting restarts discard cached plans. Replan if a heatmap link expires.
- The application is scoped to US endpoints; provider paths may cross borders.

## Sources

- [Approved design](docs/design.md)
- [Open-Meteo forecast API and units](https://open-meteo.com/en/docs)
- [Valhalla routing API](https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/)
- [OpenRouteService](https://openrouteservice.org/)
- [US Census Gazetteer places](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html)
- [OpenFreeMap](https://openfreemap.org/quick_start/) and OpenStreetMap contributors
- [MapLibre Vite worker setup](https://maplibre.org/maplibre-gl-js/docs/)
- [Render Django deployment](https://render.com/docs/deploy-django), [free-service limits](https://render.com/docs/free)
- [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
