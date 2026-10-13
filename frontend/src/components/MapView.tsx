import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { FeatureCollection, Feature, Point, LineString } from "geojson";
import { Expand, Map as MapIcon } from "lucide-react";
import type { Plan, Heatmap, Layer } from "../api";
import {
  colors,
  dateTime,
  label,
  levels,
  routeColors,
  truckPosition,
} from "../lib";
import { cellRadiusAtZoom0, heatColorExpression } from "../heat";
import "maplibre-gl/dist/maplibre-gl.css";
maplibregl.setWorkerUrl(workerUrl);

const empty: FeatureCollection = { type: "FeatureCollection", features: [] };
export default function MapView({
  plan,
  selected,
  onSelect,
  heatmap,
  hour,
  layer,
}: {
  plan: Plan | null;
  selected: string;
  onSelect: (id: string) => void;
  heatmap: Heatmap | null;
  hour: number;
  layer: Layer;
}) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null),
    [ready, setReady] = useState(false),
    [mapError, setMapError] = useState("");
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  useEffect(() => {
    if (!container.current) return;
    let m: maplibregl.Map;
    try {
      m = new maplibregl.Map({
        container: container.current,
        style: "https://tiles.openfreemap.org/styles/positron",
        center: [-96, 38],
        zoom: 3.7,
        attributionControl: { compact: true },
      });
    } catch {
      setMapError(
        "The map needs WebGL. Try another browser; route details remain available.",
      );
      return;
    }
    map.current = m;
    m.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    m.on("error", (event) => {
      console.warn("Map resource:", event.error.message);
      setMapError("Some map tiles could not load. Check your connection.");
    });
    m.on("load", () => {
      setMapError("");
      for (const id of [
        "weather",
        "routes",
        "checkpoints",
        "endpoints",
        "trucks",
      ])
        m.addSource(id, { type: "geojson", data: empty });
      // Each forecast cell is a soft circle coloured by its own value (not a density
      // heatmap, which would make an isolated No Travel cell look mild and overlapping
      // calm cells look severe). Radius and colours are set once a heatmap arrives.
      m.addLayer({
        id: "weather",
        type: "circle",
        source: "weather",
        paint: {
          "circle-color": "rgba(0,0,0,0)",
          "circle-radius": 0,
          "circle-blur": 1,
          "circle-opacity": 0.6,
        },
      });
      m.addLayer({
        id: "route-outline",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#ffffff",
          "line-width": 8,
          "line-opacity": 0.85,
        },
      });
      m.addLayer({
        id: "routes",
        type: "line",
        source: "routes",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 4 },
      });
      m.addLayer({
        id: "checkpoints",
        type: "circle",
        source: "checkpoints",
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3, 8, 6],
          "circle-stroke-color": "white",
          "circle-stroke-width": 1.5,
        },
      });
      m.addLayer({
        id: "endpoints",
        type: "circle",
        source: "endpoints",
        paint: {
          "circle-color": "#163e35",
          "circle-radius": 9,
          "circle-stroke-width": 3,
          "circle-stroke-color": "white",
        },
      });
      m.addLayer({
        id: "trucks",
        type: "circle",
        source: "trucks",
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": 10,
          "circle-stroke-width": 4,
          "circle-stroke-color": "#fff",
        },
      });
      m.addLayer({
        id: "truck-labels",
        type: "symbol",
        source: "trucks",
        layout: {
          "text-field": ["get", "id"],
          // A font OpenFreeMap serves; MapLibre's default stack 404s on its glyph server.
          "text-font": ["Noto Sans Regular"],
          "text-size": 11,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#fff" },
      });
      const popup = new maplibregl.Popup({
        closeButton: false,
        offset: 14,
        maxWidth: "290px",
      });
      m.on("mouseenter", "checkpoints", () => {
        m.getCanvas().style.cursor = "pointer";
      });
      m.on("mousemove", "checkpoints", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties!,
          div = document.createElement("div");
        div.className = "checkpoint-popup";
        const title = document.createElement("strong");
        title.textContent = `${label(p.level)} · Mile ${Number(p.mile).toFixed(1)}`;
        title.style.color = p.color;
        div.append(title);
        for (const line of [
          `Arrival: ${dateTime(p.eta)}`,
          `Forecast: ${dateTime(p.forecast)}`,
          `Wind ${p.wind} mph · Gusts ${p.gust} mph`,
          `Rain ${p.rain} in/h · Snow ${p.snow} in/h`,
          `Deciding condition: ${p.driver}${p.adjusted ? " (load adjusted)" : ""}`,
        ]) {
          const row = document.createElement("div");
          row.textContent = line;
          div.append(row);
        }
        popup
          .setLngLat((f.geometry as Point).coordinates as [number, number])
          .setDOMContent(div)
          .addTo(m);
      });
      m.on("mouseleave", "checkpoints", () => {
        m.getCanvas().style.cursor = "";
        popup.remove();
      });
      m.on("click", "routes", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) selectRef.current(id);
      });
      setReady(true);
    });
    return () => {
      setReady(false);
      map.current = null;
      m.remove();
    };
  }, []);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const routes: Feature<LineString>[] = (plan?.routes || []).map((r) => ({
      type: "Feature",
      properties: { id: r.id, color: routeColors[r.id] },
      geometry: r.geometry,
    }));
    (m.getSource("routes") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: routes,
    });
    const ends: Feature<Point>[] = plan
      ? [plan.origin, plan.destination].map((p) => ({
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        }))
      : [];
    (m.getSource("endpoints") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: ends,
    });
    if (!plan) return;
    const fit = () => {
      const bounds = new maplibregl.LngLatBounds();
      plan.routes.forEach((r) =>
        r.geometry.coordinates.forEach((p) =>
          bounds.extend(p as [number, number]),
        ),
      );
      const narrow = m.getContainer().clientWidth < 600;
      m.resize();
      m.fitBounds(bounds, {
        padding: {
          top: 90,
          bottom: narrow ? 265 : 285,
          left: narrow ? 35 : 70,
          right: narrow ? 35 : 70,
        },
        maxZoom: 11,
        duration: 0,
      });
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(m.getContainer());
    return () => observer.disconnect();
  }, [plan, ready]);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    m.setPaintProperty("routes", "line-width", [
      "case",
      ["==", ["get", "id"], selected],
      5,
      2.5,
    ]);
    m.setPaintProperty("routes", "line-opacity", [
      "case",
      ["==", ["get", "id"], selected],
      1,
      0.5,
    ]);
    const points: Feature<Point>[] = (
      plan?.routes.find((r) => r.id === selected)?.checkpoints || []
    ).map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      properties: {
        color: colors[p.risk.level],
        level: p.risk.level,
        mile: p.mile,
        eta: p.eta,
        forecast: p.weather.forecast_time,
        wind: p.weather.wind_mph.toFixed(1),
        gust: p.weather.gust_mph.toFixed(1),
        rain: p.weather.rain_in_hr.toFixed(3),
        snow: p.weather.snow_in_hr.toFixed(3),
        driver: p.risk.driver,
        adjusted: p.risk.load_adjusted,
      },
    }));
    (m.getSource("checkpoints") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: points,
    });
  }, [plan, selected, ready]);
  const frames = useMemo(() => {
    if (!heatmap) return null;
    return heatmap.layers[layer].map((values) => ({
      type: "FeatureCollection" as const,
      features: heatmap.cells.map((coordinates, i) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates },
        properties: { value: values[i] },
      })),
    }));
  }, [heatmap, layer]);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !heatmap) return;
    const r0 = cellRadiusAtZoom0(heatmap.cells);
    m.setPaintProperty("weather", "circle-radius", [
      "interpolate",
      ["exponential", 2],
      ["zoom"],
      0,
      r0,
      20,
      r0 * 2 ** 20,
    ]);
    m.setPaintProperty(
      "weather",
      "circle-color",
      heatColorExpression(layer) as maplibregl.ExpressionSpecification,
    );
  }, [heatmap, layer, ready]);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource("weather") as maplibregl.GeoJSONSource).setData(
      frames?.[hour] || empty,
    );
    const time = heatmap
      ? new Date(Date.parse(heatmap.start) + hour * 3600000).toISOString()
      : null;
    const trucks: Feature<Point>[] = [];
    if (plan && time)
      for (const r of plan.routes) {
        const p = truckPosition(r, time, plan.departure);
        if (p)
          trucks.push({
            type: "Feature",
            geometry: { type: "Point", coordinates: p },
            properties: { id: r.id, color: routeColors[r.id] },
          });
      }
    (m.getSource("trucks") as maplibregl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: trucks,
    });
  }, [frames, hour, plan, heatmap, ready]);
  function fit() {
    const m = map.current;
    if (!m || !plan) return;
    const bounds = new maplibregl.LngLatBounds();
    plan.routes.forEach((r) =>
      r.geometry.coordinates.forEach((p) =>
        bounds.extend(p as [number, number]),
      ),
    );
    m.fitBounds(bounds, { padding: 100, maxZoom: 11 });
  }
  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        data-map-ready={ready}
        aria-label="Truck routes and weather map"
      />
      <div className="map-heading">
        <span>
          <MapIcon size={16} />
          {plan
            ? `${plan.origin.label} → ${plan.destination.label}`
            : "A clearer view of the road ahead"}
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={fit}
          disabled={!plan}
          aria-label="Fit all routes"
        >
          <Expand size={17} />
        </button>
      </div>
      {mapError && (
        <div className="map-error" role="status">
          {mapError}
        </div>
      )}
      {!plan && (
        <div className="map-empty">
          <NavigationGlyph />
          <span>YOUR NEXT JOURNEY, IN FOCUS</span>
          <h2>Know what’s ahead.</h2>
          <p>
            Compare truck routes with weather
            <br />
            at the time you’ll actually arrive.
          </p>
          <div>
            TRUCK ROUTING <i /> ARRIVAL-TIME FORECASTS
          </div>
        </div>
      )}
      <div className="map-legend">
        <span>CHECKPOINT RISK</span>
        {levels.map((l) => (
          <span key={l}>
            <i style={{ background: colors[l] }} />
            {label(l)}
          </span>
        ))}
      </div>
    </>
  );
}
function NavigationGlyph() {
  return (
    <svg
      width="46"
      height="46"
      viewBox="0 0 46 46"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9 35L23 7l14 28-14-6-14 6Z"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path d="M23 7v22" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
