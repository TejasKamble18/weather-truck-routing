from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import floor, isfinite
from django.core.cache import cache
from .http import request
from .errors import PlannerError

FIELDS = {
    "wind_mph": "wind_speed_10m",
    "gust_mph": "wind_gusts_10m",
    "rain_in_hr": "rain",
    "snow_in_hr": "snowfall",
}


def snap(lon, lat):
    return (floor(lon * 4 + 0.5) / 4, floor(lat * 4 + 0.5) / 4)


def parse_series(data):
    try:
        hourly, units = data["hourly"], data["hourly_units"]
        factors = {}
        for key, field in FIELDS.items():
            unit = units[field]
            allowed = (
                {"mp/h": 1, "mph": 1}
                if key in ("wind_mph", "gust_mph")
                else (
                    {"inch": 1, "cm": 2.54}
                    if key == "snow_in_hr"
                    else {"inch": 1, "mm": 25.4}
                )
            )
            factors[key] = allowed[unit]
            if len(hourly[field]) != len(hourly["time"]):
                raise ValueError("Mismatched series")
        series = {}
        for i, t in enumerate(hourly["time"]):
            stamp = int(
                datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp()
            )
            series[stamp] = {
                key: None
                if hourly[field][i] is None
                else float(hourly[field][i]) / factors[key]
                for key, field in FIELDS.items()
            }
        if not series:
            raise ValueError("Empty forecast")
        return series
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise PlannerError(
            "The weather provider returned incomplete data.", "weather_unavailable"
        ) from exc


def fetch(cells, end, now=None):
    now = now or datetime.now(timezone.utc)
    days = max(3, (end.date() - now.date()).days + 2)
    if days > 16:
        raise PlannerError(
            "This trip arrives beyond the 16-day forecast horizon. Choose an earlier departure.",
            "forecast_unavailable",
            422,
        )
    cells = sorted(set(cells))

    def key(cell):
        return f"weather:v1:{now.date()}:{days}:{cell[0]}:{cell[1]}"

    result, missing = {}, []
    for cell in cells:
        hit = cache.get(key(cell))
        if hit is None:
            missing.append(cell)
        else:
            result[cell] = hit

    def batch(chunk):
        data = request(
            "GET",
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": ",".join(str(c[1]) for c in chunk),
                "longitude": ",".join(str(c[0]) for c in chunk),
                "hourly": ",".join(FIELDS.values()),
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
                "forecast_days": days,
                "past_days": 1,
            },
        )
        records = data if isinstance(data, list) else [data]
        if len(records) != len(chunk):
            raise PlannerError(
                "Weather is missing for some checkpoints.", "weather_unavailable"
            )
        parsed = {}
        for cell, item in zip(chunk, records):
            series = parse_series(item)
            cache.set(key(cell), series, 1800)
            parsed[cell] = series
        return parsed

    chunks = [missing[i : i + 100] for i in range(0, len(missing), 100)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for parsed in pool.map(batch, chunks):
            result.update(parsed)
    return result


def at(series, moment):
    stamp = int(floor(moment.timestamp() / 3600 + 0.5) * 3600)
    data = series.get(stamp)
    if data is None or any(
        v is None or not isfinite(v) or v < 0 for v in data.values()
    ):
        raise PlannerError(
            "No complete forecast is available at a checkpoint arrival time. Try an earlier departure.",
            "forecast_unavailable",
            422,
        )
    return {
        **data,
        "forecast_time": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
    }
