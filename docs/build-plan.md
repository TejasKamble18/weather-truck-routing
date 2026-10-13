# Implementation plan

Continue the approved design in `design.md`.

1. Configure Django/DRF, environment settings, shared cache and JSON errors.
2. Implement pure geometry, checkpoint timing, risk rules and route ranking; test boundaries.
3. Integrate Valhalla truck routes, ORS fallback and existing Census geocoding.
4. Fetch and cache Open-Meteo forecasts, then build plans and corridor heatmap frames.
5. Build the responsive React/MapLibre planner, route comparison, timeline and popups.
6. Verify unit/API tests, frontend production build and live routing/weather/browser behavior.
7. Document setup, limitations and deployment; provide Render and Vercel configuration.

Use real provider data. Missing forecasts must produce a clear error, never a low-risk score.
Preserve the fuel-route-optimizer project. Do not record or submit the Loom on the user's behalf.

## Completion notes

- Steps 1–5 implemented. Step 6: 60 backend tests, 4 frontend tests, Django system
  check and production build passed. Live provider and browser checks completed;
  production browser check is recorded in `verification.md`.
- Step 7: README, GitHub Actions, Render Blueprint and Vercel configuration added.
  Actual hosting still requires connected Render and Vercel accounts.
- Implementation uses plain CSS rather than Tailwind; no component framework is
  needed for this single-screen app.
- MapLibre 6 requires an explicitly bundled worker with Vite. The map is lazy
  loaded so the form can render before the map bundle.
- Forecast units are validated, including conversion of snowfall in centimeters.
  Missing/null/negative/nonfinite weather is rejected at the requested hour.
- Heatmap grids may coarsen beyond 1° on very long corridors to enforce 250 cells.
- The file cache supports multiple workers on one instance; restarts clear plans.
- No uptime-monitor integration is configured. Free-hosting cold starts remain a
  documented limitation, with a delayed-loading message in the UI.
