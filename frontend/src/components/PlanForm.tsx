import { useState } from "react";
import {
  ArrowRight,
  ArrowDownUp,
  MapPin,
  Navigation,
  Clock3,
  Weight,
  LoaderCircle,
} from "lucide-react";
import type { PlanInput } from "../api";
import { localInputNow } from "../lib";
export default function PlanForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (input: PlanInput) => void;
}) {
  const [origin, setOrigin] = useState("Chicago, IL"),
    [destination, setDestination] = useState("Dallas, TX");
  const [departure, setDeparture] = useState(localInputNow),
    [load, setLoad] = useState(35000),
    [interval, setInterval] = useState(25);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          origin,
          destination,
          departure: new Date(departure).toISOString(),
          load_lbs: load,
          interval_miles: interval,
        });
      }}
    >
      <div className="section-eyebrow">01 / YOUR JOURNEY</div>
      <h1>
        Better roads.
        <br />
        <span>Clearer decisions.</span>
      </h1>
      <p className="intro">
        Find the right route for your load and the weather ahead.
      </p>
      <div className="locations">
        <label>
          <span>ORIGIN</span>
          <div className="input-wrap">
            <MapPin size={17} />
            <input
              aria-label="Origin"
              required
              maxLength={200}
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              placeholder="City, state or coordinates"
            />
          </div>
        </label>
        <button
          type="button"
          className="swap icon-button"
          aria-label="Swap origin and destination"
          onClick={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
        >
          <ArrowDownUp size={16} />
        </button>
        <label>
          <span>DESTINATION</span>
          <div className="input-wrap">
            <Navigation size={17} />
            <input
              aria-label="Destination"
              required
              maxLength={200}
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              placeholder="City, state or coordinates"
            />
          </div>
        </label>
      </div>
      <label>
        <span>
          <Clock3 size={13} /> DEPARTURE · YOUR LOCAL TIME
        </span>
        <input
          aria-label="Departure"
          type="datetime-local"
          required
          value={departure}
          onChange={(e) => setDeparture(e.target.value)}
        />
      </label>
      <label>
        <span>
          <Weight size={13} /> LOAD WEIGHT <b>{load.toLocaleString()} lb</b>
        </span>
        <div className="input-wrap">
          <input
            aria-label="Load weight in pounds"
            type="number"
            min={0}
            max={80000}
            step={1}
            required
            value={load}
            onChange={(e) => setLoad(Number(e.target.value))}
          />
          <span className="unit">lb</span>
        </div>
      </label>
      <fieldset>
        <legend>WEATHER CHECKPOINTS</legend>
        <div className="segments">
          {[10, 25, 50].map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={interval === n}
              className={interval === n ? "active" : ""}
              onClick={() => setInterval(n)}
            >
              Every {n} mi
            </button>
          ))}
        </div>
      </fieldset>
      <button className="primary" disabled={busy} type="submit">
        {busy ? (
          <>
            <LoaderCircle className="spin" size={18} /> Checking routes &
            weather
          </>
        ) : (
          <>
            Find my routes <ArrowRight size={18} />
          </>
        )}
      </button>
      <div className="examples">
        <span>TRY A TRIP</span>
        {[
          ["Chicago, IL", "Dallas, TX", "Chicago → Dallas"],
          ["Denver, CO", "Salt Lake City, UT", "Denver → Salt Lake"],
        ].map(([a, b, text]) => (
          <button
            type="button"
            key={text}
            onClick={() => {
              setOrigin(a);
              setDestination(b);
            }}
          >
            {text}
          </button>
        ))}
      </div>
    </form>
  );
}
