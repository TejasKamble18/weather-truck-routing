import { Play, Pause, Wind, CloudRain, Snowflake, Layers } from "lucide-react";
import type { Layer, Heatmap } from "../api";
import { colors, dateTime, label, levels } from "../lib";
import { heatStops, legendLabels } from "../heat";
export default function HeatmapControls({
  heatmap,
  hour,
  setHour,
  layer,
  setLayer,
  playing,
  setPlaying,
  loading,
  error,
  onRetry,
}: {
  heatmap: Heatmap | null;
  hour: number;
  setHour: (h: number) => void;
  layer: Layer;
  setLayer: (l: Layer) => void;
  playing: boolean;
  setPlaying: (v: boolean) => void;
  loading: boolean;
  error: string;
  onRetry: () => void;
}) {
  const time = heatmap
    ? new Date(Date.parse(heatmap.start) + hour * 3600000).toISOString()
    : null;
  return (
    <div className="map-overlays">
      <div className="map-legend" aria-label="Checkpoint risk legend">
        <span>CHECKPOINT RISK</span>
        {levels.map((level) => (
          <span key={level}>
            <i style={{ background: colors[level] }} />
            {label(level)}
          </span>
        ))}
      </div>
      <section
        className="forecast-controls"
        aria-label="Weather forecast timeline"
      >
        <div className="forecast-top">
          <div>
            <span className="section-eyebrow">WEATHER OUTLOOK</span>
            <strong>{time ? dateTime(time) : "The next 48 hours"}</strong>
          </div>
          <div className="layer-options">
            {(
              [
                ["risk", Layers],
                ["wind", Wind],
                ["rain", CloudRain],
                ["snow", Snowflake],
              ] as const
            ).map(([value, Icon]) => (
              <button
                type="button"
                key={value}
                className={layer === value ? "active" : ""}
                aria-pressed={layer === value}
                onClick={() => setLayer(value)}
              >
                <Icon size={14} />
                {value}
              </button>
            ))}
          </div>
        </div>
        <div className="timeline">
          <button
            type="button"
            className="play-button"
            aria-label={playing ? "Pause forecast" : "Play forecast"}
            disabled={!heatmap}
            onClick={() => setPlaying(!playing)}
          >
            {playing ? <Pause size={17} /> : <Play size={17} />}
          </button>
          <div className="slider-wrap">
            <input
              aria-label="Forecast hour"
              type="range"
              min={0}
              max={48}
              step={1}
              disabled={!heatmap}
              value={hour}
              onChange={(e) => {
                setPlaying(false);
                setHour(Number(e.target.value));
              }}
            />
            <div className="ticks">
              <span>Now</span>
              <span>+12h</span>
              <span>+24h</span>
              <span>+36h</span>
              <span>+48h</span>
            </div>
          </div>
          <span className="hour-chip">+{hour}h</span>
        </div>
        {heatmap && (
          <div className="heat-scale">
            {heatStops(layer)
              .slice(1)
              .map(([threshold, color], i) => (
                <span key={threshold} className="heat-band">
                  <i style={{ background: color }} />
                  {legendLabels[layer][i]}
                </span>
              ))}
            <span>Same thresholds as checkpoint risk</span>
          </div>
        )}
        <div className="forecast-caption" aria-live="polite">
          {loading ? (
            "Loading corridor forecasts…"
          ) : error ? (
            <>
              <span>{error}</span>{" "}
              <button onClick={onRetry}>Retry heatmap</button>
            </>
          ) : heatmap ? (
            `${heatmap.cells.length} forecast cells · ${layer === "risk" ? "Load-adjusted weather risk" : layer === "wind" ? "Sustained wind · mph" : `${layer === "rain" ? "Rainfall" : "Snowfall"} · inches/hour`} · Route scores use arrival-time weather`
          ) : (
            "Plan a trip to explore the weather along your route."
          )}
        </div>
      </section>
    </div>
  );
}
