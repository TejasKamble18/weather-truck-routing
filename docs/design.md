# Weather-Aware Truck Routing — Design

A React + Django web app that helps a truck driver choose the safest route
based on weather, load weight and travel time.

## Requirements (from the brief)

- Inputs: origin, destination, departure date/time, load weight.
- Generate **3 route options** using a routing API.
- Sample weather every **10 / 25 / 50 miles**, using the truck's **estimated
  arrival time** at each checkpoint.
- Classify weather risk with the provided risk and load rules.
- Recommend the best route, preferring in order: fewest Severe miles, fewest
  High miles, lowest average risk, shortest travel time.
- Show all routes, checkpoints, risk levels, ETAs and route summaries on a map.
- Show a **weather heatmap along the trip corridor** with a **0–48 hour
  forecast slider**.
- Deliverables: GitHub repository, hosted application, 5–10 minute Loom.
- Grading: 40% routes/weather/risk/recommendation logic, 35% UI/map/heatmap
  smoothness and performance, 10% code quality, 5% documentation.

## External services

| Purpose | Service | Notes |
|---|---|---|
| Routes (primary) | Valhalla public server `https://valhalla1.openstreetmap.de/route`, `costing=truck`, `alternates=2` | No key. Returns up to 3 truck routes with per-maneuver times |
| Routes (fill-in / fallback) | OpenRouteService `driving-hgv` via `https://api.heigit.org` | Key in `ORS_API_KEY`. Its own alternatives only work under 100 km, so extra options are made by forcing a via point |
| Geocoding | Local US Census places list, then OpenRouteService Pelias | Same approach as the fuel-route project; coordinates confirmed with a reverse country lookup |
| Weather | Open-Meteo `https://api.open-meteo.com/v1/forecast` | No key. Hourly `wind_speed_10m`, `wind_gusts_10m`, `rain`, `snowfall` with `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=UTC`. Many points per request |
| Base map | OpenFreeMap vector tiles (`https://tiles.openfreemap.org/styles/liberty`) | No key |

## Risk rules and rulings

Thresholds use **lower-bound-inclusive** bands so every value has exactly one level:

| Level (score) | Wind (mph, sustained) | Rain (in/hr) | Snow (in/hr) |
|---|---|---|---|
| Low (0) | < 25 | < 0.10 | < 0.5 |
| Moderate (1) | 25 – < 35 | 0.10 – < 0.25 | 0.5 – < 1.0 |
| High (2) | 35 – < 45 | 0.25 – < 0.50 | 1.0 – < 2.0 |
| Severe (3) | 45 – < 55 | 0.50 – ≤ 1.00 | 2.0 – ≤ 3.0 |
| No Travel (4) | ≥ 55 | > 1.00 | > 3.0 |

Load rules (applied to the wind level only):
- wind ≥ 55 → No Travel for any load (already the table);
- 45 ≤ wind < 55 and load > 30,000 lb → No Travel;
- 35 ≤ wind < 45 and load > 40,000 lb → Severe.

Rulings where the brief is silent:
1. **Wind** means sustained 10 m wind speed (the table's "Wind"). Gusts are fetched
   and displayed but not scored.
2. **Checkpoint level** = the worst of wind (after load rules), rain and snow. The
   response records which condition drove it.
3. **Miles per level:** each checkpoint represents the stretch from halfway to the
   previous checkpoint to halfway to the next one (the first and last cover half a
   gap at the route ends).
4. **No Travel** ranks worse than Severe: the comparison first prefers fewest No
   Travel miles, then the brief's order. A route with any No Travel miles carries a
   warning.
5. **Average risk** = distance-weighted mean of checkpoint scores.
6. **ETA** = departure + the route's own travel time to that point (from the
   routing engine's per-maneuver times, interpolated by distance). Weather is the
   forecast hour nearest the ETA.
7. **Departure** must be between 1 hour in the past and 7 days ahead (forecast
   horizon). Forecast data is requested out to the latest arrival (max 16 days).
8. **Heatmap slider** hours count from the current hour (forecast time, 0–48). The
   map also shows where the truck would be on each route at that hour.
9. Fewer than 3 distinct routes may exist (for example a single obvious highway).
   The app shows what it found and says why.

## Backend (Django 6.1 + DRF)

### Endpoints

`POST /api/plan/`
```json
{"origin": "Chicago, IL", "destination": "Dallas, TX",
 "departure": "2026-10-13T08:00:00-05:00", "load_lbs": 38000, "interval_miles": 25}
```
- `departure` optional (default: now). `load_lbs` 0–80,000. `interval_miles` ∈ {10, 25, 50}.

Response:
```json
{
  "plan_id": "…",
  "origin": {"label": "Chicago, IL", "lat": 41.88, "lon": -87.63},
  "destination": {"label": "Dallas, TX", "lat": 32.78, "lon": -96.80},
  "departure": "2026-10-13T13:00:00Z", "load_lbs": 38000, "interval_miles": 25,
  "routes": [
    {
      "id": "A", "name": "via I-57 / I-30", "source": "valhalla",
      "distance_miles": 965.6, "duration_hours": 14.9, "arrival": "…",
      "geometry": {"type": "LineString", "coordinates": [[-87.63, 41.88], "…"]},
      "checkpoints": [
        {"mile": 0, "lat": 41.88, "lon": -87.63, "eta": "…",
         "weather": {"wind_mph": 12.3, "gust_mph": 21.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0},
         "risk": {"level": "low", "score": 0, "driver": "wind", "load_adjusted": false}}
      ],
      "summary": {"miles_by_level": {"low": 900.1, "moderate": 50.0, "high": 15.5, "severe": 0, "no_travel": 0},
                  "average_risk": 0.08, "worst_level": "high", "no_travel_warning": false},
      "rank": 1, "recommended": true
    }
  ],
  "recommendation": {"route_id": "A", "reason": "Fewest High miles (15 vs 40 and 62)."},
  "notes": ["Only 2 distinct routes exist between these points."],
  "heatmap_url": "/api/plan/<plan_id>/heatmap/"
}
```

`GET /api/plan/<plan_id>/heatmap/`
```json
{"start": "2026-10-12T11:00:00Z", "hours": 49,
 "cells": [[-87.5, 41.5], "…"],
 "layers": {"risk": [[0, 1, "…"], "…"], "wind": "…", "rain": "…", "snow": "…"}}
```
`layers.<name>[hour][cell]`. Risk uses the plan's load. Loaded after the plan so
the routes appear first.

`GET /api/health/` → `{"status": "ok"}` (for the uptime monitor).

Errors: `{"error": "<code>", "detail": "…"}` — 400 `invalid_input`, 404
`location_not_found` / `outside_usa`, 422 `no_route`, 502/504 for upstream
failures.

### Pipeline for one plan

1. Geocode origin and destination (local first).
2. **Routes:** Valhalla truck route with `alternates=2`, `directions_type=maneuvers`.
   Decode the polyline6 shape; build a timing profile (cumulative miles and seconds
   per shape vertex) from maneuver times. If fewer than 3 distinct routes, request
   OpenRouteService `driving-hgv` routes through a via point offset perpendicular to
   the main route at its midpoint (±max(15 mi, 8% of distance)), with instructions
   for step times. Discard candidates longer than 1.4× the shortest or overlapping an
   existing route by more than 90%. If Valhalla fails, OpenRouteService supplies the
   main route too. Routes are labelled A/B/C and named by their main highways.
3. **Checkpoints** every `interval_miles` from mile 0, plus the destination, with
   ETA from the timing profile.
4. **Weather:** checkpoints from all routes are snapped to a 0.25° grid and
   deduplicated; one Open-Meteo call per chunk of up to 100 cells, chunks fetched in
   parallel; hourly series cached 30 minutes per cell.
5. **Risk** per checkpoint (pure function of weather + load).
6. **Summaries and ranking** (pure), recommendation reason text.
7. Cache the plan (2 hours) under `plan_id`.

Heatmap: cells on a 0.5° grid whose centres lie within 40 miles of any route
sample (coarsened to 0.75° then 1.0° if more than 250 cells); 49 hourly frames from
the current hour; same weather fetch and cache; risk with the plan's load.

### Code layout

```
backend/
  config/                       settings (env-driven), urls, wsgi
  planner/
    geo.py                      haversine, polyline6 decode, interpolation helpers
    geocoding.py, places.py     local Census lookup + ORS fallback (from fuel-route project)
    routing/valhalla.py         Valhalla client → RouteCandidate
    routing/ors.py              ORS client (directions with via point, geocode, reverse)
    routing/routes.py           pick 3 distinct routes, timing profiles, naming
    checkpoints.py              sample points + ETAs
    weather.py                  Open-Meteo client, grid snapping, cache, parallel chunks
    risk.py                     risk/load rules (pure)
    ranking.py                  summaries, ranking, recommendation reason (pure)
    heatmap.py                  corridor grid + frames
    services.py                 orchestration + plan cache
    views.py, serializers.py, errors.py, urls.py
  data/us_places.csv
  tests/
  render.yaml (at repo root)
```

## Frontend (React 19 + Vite + TypeScript + Tailwind + MapLibre GL)

- **Layout:** left panel (form, then route cards); map fills the rest; a bottom bar
  over the map holds the heatmap controls.
- **Form:** origin, destination, departure (`datetime-local`, default now), load
  (lb, default 35,000), interval (10 / 25 / 50 segmented control). Example chips
  (e.g. "Chicago → Dallas") fill the form for the demo.
- **Route cards:** one per route, coloured to match its line: name, distance,
  duration, ETA, a stacked bar of miles by risk level, average risk, warnings; the
  recommended card is marked with the reason. Clicking a card highlights its route.
- **Map:** three route lines (recommended thicker, others dimmed until hovered or
  selected); checkpoint circles coloured by risk level; hover popup with mile, ETA,
  wind/gust, rain, snow and the deciding condition; origin and destination markers.
- **Heatmap:** MapLibre circle layer (GPU), each cell a blurred circle coloured by
  its own value with the risk-rule bands (a density `heatmap` layer misrepresents
  isolated or overlapping values). All 49 frames are built once into
  GeoJSON when the heatmap response arrives; the slider only calls `setData` on the
  prepared frame, so dragging never waits on the network. Layer toggle: Risk / Wind
  / Rain / Snow, with a legend. Play button animates hours. A truck marker on each
  route shows its position at the slider's hour.
- **States:** loading skeletons, errors shown inline with the API's `detail`, and a
  note when the heatmap is still loading.
- `VITE_API_URL` points at the backend.

```
frontend/src/
  api.ts            types + fetch helpers
  App.tsx
  components/       PlanForm, RouteCards, MapView, HeatmapControls, Legend
  lib/              risk colours, time formatting, truck position at time
```

## Hosting

- Backend on **Render** (free web service, Python, `gunicorn`), configured by
  `render.yaml`; `ORS_API_KEY`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS` as env vars. An uptime monitor pings `/api/health/` to
  avoid cold starts during review.
- Frontend on **Vercel** (root `frontend/`), `VITE_API_URL` = Render URL.

## Performance targets

- Plan (uncached): about 3–6 s, dominated by routing and weather calls.
- Heatmap: under 3 s after the plan.
- Slider: no network calls; frame switch well under 50 ms.

## Testing

- Backend (pytest): risk bands at every boundary and the load rules; checkpoint
  sampling and ETA interpolation; miles-by-level attribution; ranking order
  including ties and No Travel; polyline6 decoding; route de-duplication; weather
  grid snapping and response parsing (mocked HTTP); API validation and error codes.
- Frontend (vitest): truck position at time, risk colour mapping, formatting.
- Manual: hosted app on 3 routes, slider smoothness checked in the browser.

## Out of scope

Live traffic, hours-of-service rules, user accounts, saving plans, routes outside
the USA.
