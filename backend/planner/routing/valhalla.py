from ..http import request
from ..geo import decode_polyline
from ..errors import PlannerError
from .common import candidate


def routes(start, end):
    data = request(
        "POST",
        "https://valhalla1.openstreetmap.de/route",
        json={
            "locations": [
                {"lat": start.lat, "lon": start.lon},
                {"lat": end.lat, "lon": end.lon},
            ],
            "costing": "truck",
            "alternates": 2,
            "units": "miles",
            "directions_type": "maneuvers",
        },
    )
    try:
        trips = [data["trip"]] + [r["trip"] for r in data.get("alternates", [])]
        result = []
        for trip in trips:
            coords, steps, names = [], [], []
            for leg in trip["legs"]:
                shape = decode_polyline(leg["shape"])
                offset = len(coords) - 1 if coords else 0
                coords.extend(shape[1:] if coords else shape)
                for m in leg["maneuvers"]:
                    steps.append(
                        (
                            m["begin_shape_index"] + offset,
                            m["end_shape_index"] + offset,
                            m["time"],
                        )
                    )
                    names.extend(
                        (m.get("length", 0), n) for n in m.get("street_names", [])
                    )
            highways = list(dict.fromkeys(n for _, n in sorted(names, reverse=True)))[
                :2
            ]
            result.append(
                candidate(
                    coords,
                    trip["summary"]["length"],
                    trip["summary"]["time"],
                    steps,
                    "valhalla",
                    "via " + " / ".join(highways) if highways else "Truck route",
                )
            )
        return result
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PlannerError("Valhalla returned an incomplete route.") from exc
