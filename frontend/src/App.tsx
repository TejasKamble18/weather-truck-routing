import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  CloudSun,
  Route as RouteIcon,
  ShieldCheck,
  TriangleAlert,
  ArrowUpRight,
} from "lucide-react";
import {
  api,
  type Heatmap,
  type Layer,
  type Plan,
  type PlanInput,
} from "./api";
import PlanForm from "./components/PlanForm";
import RouteCards from "./components/RouteCards";
const MapView = lazy(() => import("./components/MapView"));
import HeatmapControls from "./components/HeatmapControls";
import { completeWeather, type PendingWeather } from './weather';

export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null),
    [heatmap, setHeatmap] = useState<Heatmap | null>(null),
    [selected, setSelected] = useState("A");
  const [busy, setBusy] = useState(false),
    [slow, setSlow] = useState(false),
    [heatBusy, setHeatBusy] = useState(false),
    [error, setError] = useState(""),
    [heatError, setHeatError] = useState("");
  const [hour, setHour] = useState(0),
    [layer, setLayer] = useState<Layer>("risk"),
    [playing, setPlaying] = useState(false),
    [showAbout, setShowAbout] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!busy) {
      setSlow(false);
      return;
    }
    const id = setTimeout(() => setSlow(true), 12000);
    return () => clearTimeout(id);
  }, [busy]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setHour((h) => (h + 1) % 49), 650);
    return () => clearInterval(id);
  }, [playing]);
  async function loadHeatmap(p: Plan, signal: AbortSignal) {
    setHeatBusy(true);
    setHeatError("");
    try {
      const pending = await api<Heatmap | PendingWeather>(p.heatmap_url, signal);
      const h = await completeWeather<Heatmap>(pending, signal);
      if (!signal.aborted) setHeatmap(h);
    } catch (e) {
      if (!signal.aborted)
        setHeatError(
          e instanceof Error ? e.message : "Could not load the heatmap.",
        );
    } finally {
      if (!signal.aborted) setHeatBusy(false);
    }
  }
  async function submit(input: PlanInput) {
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    setBusy(true);
    setError("");
    setHeatmap(null);
    setPlan(null);
    setHeatBusy(false);
    setHeatError("");
    setHour(0);
    setPlaying(false);
    try {
      const pending = await api<Plan | PendingWeather>("/api/plan/", c.signal, { ...input, weather_source: 'browser' });
      const p = await completeWeather<Plan>(pending, c.signal);
      if (c.signal.aborted) return;
      setPlan(p);
      setSelected(p.recommendation.route_id);
      setBusy(false);
      void loadHeatmap(p, c.signal);
    } catch (e) {
      if (!c.signal.aborted)
        setError(e instanceof Error ? e.message : "Could not plan this trip.");
    } finally {
      if (!c.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="app">
      <header className="header">
        <a className="brand" href="/" aria-label="Waycast home">
          <div className="brand-symbol">
            <RouteIcon size={24} />
          </div>
          <span>
            waycast<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="header-divider" />
        <span className="header-subtitle">WEATHER-AWARE TRUCK ROUTING</span>
        <div className="header-right">
          <span className="coverage">
            <i /> US ROAD NETWORK
          </span>
          <button onClick={() => setShowAbout(true)}>
            How it works <ArrowUpRight size={14} />
          </button>
        </div>
      </header>
      <main>
        <aside className="sidebar">
          <div className="sidebar-content">
            <PlanForm busy={busy} onSubmit={submit} />
            {error && (
              <div role="alert" className="error">
                <TriangleAlert size={18} />
                <span>{error}</span>
              </div>
            )}
            {busy && (
              <div className="loading-state" role="status">
                <div className="skeleton" />
                <div className="skeleton short" />
                <p>
                  {slow
                    ? "Still connecting to routing and weather services. The first request can take longer."
                    : "Comparing truck routes and checking the forecast at each arrival time…"}
                </p>
              </div>
            )}
            {plan && (
              <RouteCards
                plan={plan}
                selected={selected}
                onSelect={setSelected}
              />
            )}
            <div className="sidebar-footer">
              <ShieldCheck size={17} />
              <p>
                Weather changes. Your route should keep up.
                <br />
                <span>Forecast guidance for a more informed journey.</span>
              </p>
            </div>
          </div>
        </aside>
        <section className="map-panel">
          <Suspense
            fallback={
              <div className="map-heading" role="status">
                Loading map…
              </div>
            }
          >
            <MapView
              plan={plan}
              selected={selected}
              onSelect={setSelected}
              heatmap={heatmap}
              hour={hour}
              layer={layer}
            />
          </Suspense>
          <HeatmapControls
            heatmap={heatmap}
            hour={hour}
            setHour={setHour}
            layer={layer}
            setLayer={setLayer}
            playing={playing}
            setPlaying={setPlaying}
            loading={heatBusy}
            error={heatError}
            onRetry={() => {
              if (plan && controller.current)
                void loadHeatmap(plan, controller.current.signal);
            }}
          />
        </section>
      </main>
      <footer className="statusbar">
        <span>
          <CloudSun size={14} /> FORECASTS BY{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
            OPEN-METEO
          </a>
        </span>
        <span>Truck routing · Valhalla / OpenRouteService</span>
        <span>Made for the miles ahead.</span>
      </footer>
      {showAbout && (
        <div className="modal-backdrop" onClick={() => setShowAbout(false)}>
          <section
            className="about-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="close"
              onClick={() => setShowAbout(false)}
              autoFocus
            >
              Close ×
            </button>
            <div className="section-eyebrow">A LITTLE FORESIGHT</div>
            <h2 id="about-title">Weather where you’ll be.</h2>
            <p>
              Waycast compares up to three distinct truck routes. It samples the
              forecast every 10, 25, or 50 miles at your estimated arrival time.
            </p>
            <p>
              Wind, rain and snow determine each checkpoint’s risk. Load weight
              can increase wind risk. The route with the fewest No Travel miles
              wins, followed by Severe miles, High miles, average risk, then
              travel time.
            </p>
            <p>
              The timeline explores the next 48 hours from now. It changes the
              corridor weather and truck positions; route scores stay tied to
              the departure time you selected.
            </p>
            <p>
              Forecasts and travel times are estimates. This assessment does not
              model driver rest breaks, live traffic, or individual truck
              dimensions.
            </p>
            <button className="primary" onClick={() => setShowAbout(false)}>
              Got it <ArrowUpRight size={16} />
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
