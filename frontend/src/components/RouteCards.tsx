import { ArrowUpRight, ShieldCheck, TriangleAlert } from "lucide-react";
import type { Plan } from "../api";
import { colors, levels, label, routeColors, duration, dateTime } from "../lib";
export default function RouteCards({
  plan,
  selected,
  onSelect,
}: {
  plan: Plan;
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="results">
      <div className="section-eyebrow">
        02 / ROUTE COMPARISON <span>{plan.routes.length} OPTIONS</span>
      </div>
      <h2>
        A little foresight.
        <br />A better way forward.
      </h2>
      <div className="recommendation">
        <ShieldCheck size={20} />
        <p>{plan.recommendation.reason}</p>
      </div>
      {[...plan.routes]
        .sort((a, b) => a.rank - b.rank)
        .map((route) => (
          <button
            type="button"
            className={`route-card ${selected === route.id ? "selected" : ""}`}
            key={route.id}
            onClick={() => onSelect(route.id)}
            aria-pressed={selected === route.id}
          >
            <div className="route-card-top">
              <span
                className="route-letter"
                style={{ background: routeColors[route.id] }}
              >
                {route.id}
              </span>
              <strong>Route {route.id}</strong>
              {route.recommended && (
                <span className="recommended">RECOMMENDED</span>
              )}
              <ArrowUpRight size={16} />
            </div>
            <div className="route-name">{route.name}</div>
            <div className="route-stats">
              <strong>{duration(route.duration_hours)}</strong>
              <span>
                {Math.round(route.distance_miles).toLocaleString()} mi
              </span>
              <span>{route.checkpoints.length} checks</span>
            </div>
            <div className="risk-bar">
              {levels.map((level) => (
                <i
                  key={level}
                  style={{
                    width: `${(route.summary.miles_by_level[level] / route.distance_miles) * 100}%`,
                    background: colors[level],
                  }}
                />
              ))}
            </div>
            <div className="risk-breakdown">
              {levels
                .filter((l) => route.summary.miles_by_level[l] > 0)
                .map((l) => (
                  <span key={l}>
                    <i style={{ background: colors[l] }} />
                    {label(l)} {route.summary.miles_by_level[l].toFixed(1)} mi
                  </span>
                ))}
            </div>
            <div className="arrival">
              Arrival {dateTime(route.arrival)} · Avg risk{" "}
              {route.summary.average_risk.toFixed(2)}/4
            </div>
            {route.summary.no_travel_warning && (
              <p className="travel-warning">
                <TriangleAlert size={14} /> No Travel conditions on this route
              </p>
            )}
          </button>
        ))}
      {plan.notes.map((note) => (
        <p className="note" key={note}>
          {note}
        </p>
      ))}
    </section>
  );
}
