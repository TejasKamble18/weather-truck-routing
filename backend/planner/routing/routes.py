from concurrent.futures import ThreadPoolExecutor
from math import cos, radians
from django.conf import settings
from django.core.cache import cache
from ..geo import distance, interpolate
from ..errors import PlannerError
from . import valhalla
from .ors import ORSClient


def route_samples(route, spacing=5):
    total = route["distance_miles"]
    return [
        interpolate(route["_miles"], route["geometry"]["coordinates"], m)
        for m in range(0, int(total) + 1, spacing)
    ] + [route["geometry"]["coordinates"][-1]]


def overlap(a, b):
    aa, bb = route_samples(a), route_samples(b, 2)
    return sum(
        any(
            abs(p[1] - q[1]) < 0.04 and abs(p[0] - q[0]) < 0.08 and distance(p, q) < 2
            for q in bb
        )
        for p in aa
    ) / len(aa)


def distinct(routes):
    result = []
    for route in sorted(routes, key=lambda r: r["distance_miles"]):
        if result and route["distance_miles"] > 1.4 * result[0]["distance_miles"]:
            continue
        if all(max(overlap(route, r), overlap(r, route)) <= 0.9 for r in result):
            result.append(route)
    return result[:3]


def find_routes(start, end):
    if distance([start.lon, start.lat], [end.lon, end.lat]) < 0.1:
        raise PlannerError("Choose two different locations.", "invalid_input", 400)
    key = f"routes:v1:{start.lat}:{start.lon}:{end.lat}:{end.lon}"
    hit = cache.get(key)
    if hit:
        return hit
    notes = []
    try:
        options = distinct(valhalla.routes(start, end))
    except PlannerError:
        options = [ORSClient().route(start, end)]
        notes.append("Valhalla was unavailable; routes supplied by OpenRouteService.")
    if not options:
        raise PlannerError("No truck route connects these locations.", "no_route", 422)
    if len(options) < 3 and settings.ORS_API_KEY:
        base = options[0]
        mid = interpolate(
            base["_miles"], base["geometry"]["coordinates"], base["distance_miles"] / 2
        )
        a, b = base["geometry"]["coordinates"][0], base["geometry"]["coordinates"][-1]
        scale = max(0.15, cos(radians(mid[1])))
        dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
        length = (dx * dx + dy * dy) ** 0.5 or 1
        offset = max(15, 0.08 * base["distance_miles"]) / 69
        vias = [
            [
                mid[0] + sign * (-dy / length) * offset / scale,
                mid[1] + sign * (dx / length) * offset,
            ]
            for sign in (-1, 1)
        ]

        def extra(via):
            try:
                return ORSClient().route(start, end, via)
            except PlannerError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            options = distinct(options + [r for r in pool.map(extra, vias) if r])
    if len(options) < 3:
        notes.append(
            f"Found {len(options)} distinct truck route(s). Additional options were unavailable, too similar, or over 40% longer."
        )
    for i, r in enumerate(options):
        r["id"] = chr(65 + i)
    result = (options, notes)
    cache.set(key, result, 1800)
    return result
