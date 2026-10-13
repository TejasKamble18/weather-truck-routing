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
            "No Travel miles",
            "Severe miles",
            "High miles",
            "average risk",
            "travel time",
        ]
        diff = next((i for i in range(5) if a[i] != b[i]), None)
        reason = (
            "Equal risk and travel time; route order breaks the tie."
            if diff is None
            else f"Lowest {labels[diff]}: {a[diff]:.2f} vs {b[diff]:.2f} for the next best route."
        )
    if winner["summary"]["no_travel_warning"]:
        reason = (
            "All routes include No Travel conditions. Consider delaying departure. "
            + reason
        )
    return {"route_id": winner["id"], "reason": reason}
