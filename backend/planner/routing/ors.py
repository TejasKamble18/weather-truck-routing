from types import SimpleNamespace
from django.conf import settings
from ..http import request
from ..errors import PlannerError
from .common import candidate


class ORSClient:
    def call(self, method, path, **kwargs):
        if not settings.ORS_API_KEY:
            raise PlannerError(
                "This location or route needs OpenRouteService. Configure ORS_API_KEY, or try a US city and state.",
                "provider_not_configured",
                503,
            )
        return request(
            method,
            settings.ORS_BASE_URL + path,
            headers={"Authorization": settings.ORS_API_KEY},
            **kwargs,
        )

    def geocode(self, text):
        data = self.call("GET", "/pelias/v1/search", params={"text": text, "size": 1})
        try:
            features = data["features"]
            if not features:
                return None
            f = features[0]
            lon, lat = f["geometry"]["coordinates"][:2]
            p = f["properties"]
            return SimpleNamespace(
                lat=lat,
                lon=lon,
                label=p.get("label", text),
                country_code=(p.get("country_a") or p.get("country_code", "")).upper(),
            )
        except (KeyError, TypeError, IndexError) as exc:
            raise PlannerError("The geocoder returned an incomplete location.") from exc

    def reverse_country(self, lat, lon):
        data = self.call(
            "GET",
            "/pelias/v1/reverse",
            params={"point.lat": lat, "point.lon": lon, "layers": "country", "size": 1},
        )
        try:
            features = data["features"]
            if not features:
                return None
            p = features[0]["properties"]
            return (p.get("country_a") or p.get("country_code", "")).upper()
        except (KeyError, TypeError, IndexError) as exc:
            raise PlannerError("The geocoder could not verify the country.") from exc

    def route(self, start, end, via=None):
        coords = (
            [[start.lon, start.lat]] + ([via] if via else []) + [[end.lon, end.lat]]
        )
        data = self.call(
            "POST",
            "/openrouteservice/v2/directions/driving-hgv/geojson",
            json={"coordinates": coords, "instructions": True},
        )
        try:
            f = data["features"][0]
            p = f["properties"]
            steps = [s for seg in p["segments"] for s in seg["steps"]]
            names = list(
                dict.fromkeys(
                    s["name"]
                    for s in sorted(steps, key=lambda s: s["distance"], reverse=True)
                    if s.get("name") and s["name"] != "-"
                )
            )[:2]
            return candidate(
                f["geometry"]["coordinates"],
                p["summary"]["distance"] / 1609.344,
                p["summary"]["duration"],
                [
                    (s["way_points"][0], s["way_points"][1], s["duration"])
                    for s in steps
                ],
                "openrouteservice",
                "via " + " / ".join(names),
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise PlannerError(
                "OpenRouteService returned an incomplete route."
            ) from exc
