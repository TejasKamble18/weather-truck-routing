from dataclasses import asdict
from datetime import datetime, timedelta
from uuid import uuid4
from django.core.cache import cache
from django.utils import timezone
from .geocoding import geocode, get_place_index, GeocodingError
from .routing.ors import ORSClient
from .routing.routes import find_routes
from .checkpoints import sample
from .weather import snap, fetch, at
from .risk import classify
from .ranking import summarize, rank
from .errors import PlannerError
from .browser_weather import manifest


def create_plan(data):
    places, client = get_place_index(), ORSClient()
    try:
        start = geocode(data["origin"], places=places, client=client)
        end = geocode(data["destination"], places=places, client=client)
    except GeocodingError as exc:
        raise PlannerError(str(exc), exc.code, 404) from exc
    routes, notes = find_routes(start, end)
    departure = data["departure"]
    for route in routes:
        route["checkpoints"] = sample(route, data["interval_miles"], departure)
        route["arrival"] = (
            departure + timedelta(hours=route["duration_hours"])
        ).isoformat()
    points = [p for r in routes for p in r["checkpoints"]]
    end_time = max(datetime.fromisoformat(p["eta"]) for p in points)
    for route in routes:
        # Send a compact timing profile with the geometry for accurate animated truck positions.
        route["vertex_seconds"] = [round(t, 2) for t in route.pop("_seconds")]
        route.pop("_miles")
    plan_id = str(uuid4())
    result = {
        "plan_id": plan_id,
        "origin": asdict(start),
        "destination": asdict(end),
        "departure": departure.isoformat(),
        "load_lbs": data["load_lbs"],
        "interval_miles": data["interval_miles"],
        "forecast_start": timezone.now()
        .replace(minute=0, second=0, microsecond=0)
        .isoformat(),
        "routes": routes,
        "notes": notes,
        "heatmap_url": f"/api/plan/{plan_id}/heatmap/",
    }
    if data.get("weather_source") == "browser":
        result["status"] = "weather_required"
        result["weather_source"] = "browser"
        result["expires_at"] = (timezone.now() + timedelta(hours=2)).isoformat()
        result["forecast_request"] = manifest(
            [snap(p["lon"], p["lat"]) for p in points],
            end_time,
            timezone.now(),
            f"/api/plan/{plan_id}/weather/",
        )
    else:
        series = fetch([snap(p["lon"], p["lat"]) for p in points], end_time)
        score_plan(result, series)
    cache.set("plan:" + plan_id, result, 7200)
    return result


def score_plan(plan, series):
    for route in plan["routes"]:
        for p in route["checkpoints"]:
            p["weather"] = at(
                series[snap(p["lon"], p["lat"])], datetime.fromisoformat(p["eta"])
            )
            p["risk"] = classify(p["weather"], plan["load_lbs"])
        route["summary"] = summarize(route["checkpoints"], route["distance_miles"])
    plan["recommendation"] = rank(plan["routes"])
    plan["status"] = "complete"
    plan.pop("forecast_request", None)
    return plan
