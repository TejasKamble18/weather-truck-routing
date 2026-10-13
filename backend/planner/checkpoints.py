from datetime import timedelta
from .geo import interpolate


def sample(route, interval, departure):
    total = route["distance_miles"]
    miles = list(range(0, int(total) + 1, interval))
    if not miles or abs(miles[-1] - total) > 1e-8:
        miles.append(total)
    points = []
    for mile in miles:
        lon, lat = interpolate(route["_miles"], route["geometry"]["coordinates"], mile)
        seconds = interpolate(route["_miles"], route["_seconds"], mile)
        points.append(
            {
                "mile": mile,
                "lon": lon,
                "lat": lat,
                "eta": (departure + timedelta(seconds=seconds)).isoformat(),
            }
        )
    return points
