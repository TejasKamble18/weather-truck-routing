from .risk import LEVELS


def summarize(points, total):
    miles = dict.fromkeys(LEVELS, 0.0)
    for i, point in enumerate(points):
        left = (points[i - 1]["mile"] + point["mile"]) / 2 if i else 0
        right = (
            (point["mile"] + points[i + 1]["mile"]) / 2
            if i + 1 < len(points)
            else total
        )
        miles[point["risk"]["level"]] += right - left
    return {
        "miles_by_level": miles,
        "average_risk": sum(i * miles[k] for i, k in enumerate(LEVELS)) / total,
        "worst_level": max((p["risk"]["level"] for p in points), key=LEVELS.index),
        "no_travel_warning": miles["no_travel"] > 0,
    }


def _hours(value, *, include_seconds=False):
    if include_seconds:
        seconds = round(value * 3600)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    minutes = round(value * 60)
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _compare(dimension, a, b):
    """Format the deciding values so the difference is visible to the reader."""
    if dimension == 4:
        for include_seconds in (False, True):
            left = _hours(a, include_seconds=include_seconds)
            right = _hours(b, include_seconds=include_seconds)
            if left != right:
                return f"{left} vs {right}"
        return "less than 1 s difference"
    unit = " mi" if dimension < 3 else ""
    for digits in range(1 if dimension < 3 else 2, 7):
        left, right = f"{a:.{digits}f}", f"{b:.{digits}f}"
        if left != right:
            return f"{left} vs {right}{unit}"
    # Keep negligible differences honest without displaying meaningless precision.
    return f"less than 0.000001{unit} difference"


def rank(routes):
    def key(r):
        s = r["summary"]
        return (
            s["miles_by_level"]["no_travel"],
            s["miles_by_level"]["severe"],
            s["miles_by_level"]["high"],
            s["average_risk"],
            r["duration_hours"],
        )

    ordered = sorted(routes, key=key)
    for i, r in enumerate(ordered):
        r.update(rank=i + 1, recommended=i == 0)
    winner = ordered[0]
    reason = "Only one distinct truck route was found."
    if len(ordered) > 1:
        a, b = key(winner), key(ordered[1])
        labels = [
            "Fewest No Travel miles",
            "Fewest Severe miles",
            "Fewest High miles",
            "Lowest average risk",
            "Shortest travel time",
        ]
        diff = next((i for i in range(5) if a[i] != b[i]), None)
        reason = (
            "Equal risk and travel time; route order breaks the tie."
            if diff is None
            else f"{labels[diff]}: {_compare(diff, a[diff], b[diff])} for the next best route."
        )
    if winner["summary"]["no_travel_warning"]:
        reason = (
            "All routes include No Travel conditions. Consider delaying departure. "
            + reason
        )
    return {"route_id": winner["id"], "reason": reason}
