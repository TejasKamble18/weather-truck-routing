from math import isfinite
from ..geo import cumulative
from ..errors import PlannerError


def candidate(coords, miles, seconds, maneuvers, source, name):
    if (
        len(coords) < 2
        or not isfinite(miles)
        or not isfinite(seconds)
        or miles <= 0
        or seconds <= 0
    ):
        raise PlannerError("No drivable route was returned.", "no_route", 422)
    raw = cumulative(coords)
    if not raw[-1]:
        raise PlannerError(
            "Origin and destination must be different.", "invalid_input", 400
        )
    profile = [0.0] * len(coords)
    elapsed = 0.0
    covered = 0
    for start, end, duration in maneuvers:
        if not 0 <= start <= end < len(coords) or duration < 0 or start != covered:
            raise ValueError("Invalid maneuver")
        span = raw[end] - raw[start]
        for i in range(start, end + 1):
            profile[i] = elapsed + duration * (
                (raw[i] - raw[start]) / span if span else 0
            )
        elapsed += duration
        covered = end
    if elapsed <= 0 or covered != len(coords) - 1:
        raise ValueError("Missing maneuver timing")
    # Providers may round maneuver times; anchor the final ETA to the summary.
    profile = [v * seconds / elapsed for v in profile]
    profile[-1] = seconds
    if any(a > b + 1e-5 for a, b in zip(profile, profile[1:])):
        raise ValueError("Non-monotonic maneuver timing")
    return {
        "source": source,
        "name": name,
        "distance_miles": miles,
        "duration_hours": seconds / 3600,
        "geometry": {"type": "LineString", "coordinates": coords},
        "_miles": [v * miles / raw[-1] for v in raw],
        "_seconds": profile,
    }
