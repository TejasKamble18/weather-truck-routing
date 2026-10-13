from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from rest_framework.test import APIClient
from planner.errors import PlannerError
from planner.weather import parse_series, at, snap, fetch
from planner.heatmap import corridor
from planner.services import create_plan
from planner.routing.common import candidate


def forecast(value=2.54):
    return {
        "hourly": {
            "time": ["2026-10-12T00:00"],
            "wind_speed_10m": [20],
            "wind_gusts_10m": [30],
            "rain": [0],
            "snowfall": [value],
        },
        "hourly_units": {
            "wind_speed_10m": "mp/h",
            "wind_gusts_10m": "mp/h",
            "rain": "inch",
            "snowfall": "cm",
        },
    }


def test_snow_unit_conversion():
    series = parse_series(forecast())
    assert at(series, datetime(2026, 10, 12, tzinfo=timezone.utc))["snow_in_hr"] == 1


@pytest.mark.parametrize("value", [None, float("nan"), -1])
def test_missing_or_invalid_forecast_never_means_low_risk(value):
    with pytest.raises(PlannerError):
        at(parse_series(forecast(value)), datetime(2026, 10, 12, tzinfo=timezone.utc))


def test_nearest_hour_and_horizon():
    series = parse_series(forecast())
    assert (
        at(series, datetime(2026, 10, 12, 0, 29, tzinfo=timezone.utc))["wind_mph"] == 20
    )
    with pytest.raises(PlannerError):
        at(series, datetime(2026, 10, 12, 0, 31, tzinfo=timezone.utc))


def test_weather_deduplicates_and_caches():
    date = datetime(2026, 10, 12, tzinfo=timezone.utc)
    with patch("planner.weather.request", return_value=forecast()) as http:
        fetch([(-90, 40), (-90, 40)], date, now=date)
        fetch([(-90, 40)], date, now=date)
        assert http.call_count == 1
    assert snap(-90.1, 40.1) == (-90, 40)


def test_heatmap_grid_is_bounded():
    routes = [
        {"checkpoints": [{"lon": -124 + i, "lat": 35 + i * 0.15} for i in range(55)]}
    ]
    assert 0 < len(corridor(routes)) <= 250


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"origin": "Chicago, IL", "destination": "Dallas, TX", "load_lbs": 80001},
        {"origin": "Chicago, IL", "destination": "Dallas, TX", "interval_miles": 11},
        {"origin": "Chicago, IL", "destination": "Dallas, TX", "departure": "wrong"},
        {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure": (datetime.now(timezone.utc) + timedelta(days=8)).isoformat(),
        },
    ],
)
def test_validation_returns_json(body):
    response = APIClient().post("/api/plan/", body, format="json")
    assert response.status_code == 400
    assert response.data["error"] == "invalid_input"


def test_health_and_expired_plan():
    client = APIClient()
    assert client.get("/api/health/").data == {"status": "ok"}
    response = client.get("/api/plan/00000000-0000-0000-0000-000000000000/heatmap/")
    assert response.status_code == 404
    assert response.data["error"] == "plan_expired"


def test_provider_failure_is_json():
    with patch("planner.views.create_plan", side_effect=PlannerError("Unavailable")):
        r = APIClient().post(
            "/api/plan/",
            {"origin": "Chicago, IL", "destination": "Dallas, TX"},
            format="json",
        )
    assert r.status_code == 502 and r.data["error"] == "upstream_error"


@pytest.mark.parametrize(
    "payload",
    [{"error": {"code": 2009}}, {"error": {"code": 2010}}, {"error_code": 442}],
)
def test_unroutable_provider_response_is_422(payload):
    from unittest.mock import Mock
    from planner import http

    response = Mock(status_code=400)
    response.json.return_value = payload
    session = Mock()
    session.request.return_value = response
    with (
        patch.object(http._local, "session", session, create=True),
        pytest.raises(PlannerError) as error,
    ):
        http.request("POST", "https://provider.example/route")
    assert error.value.status_code == 422
    assert error.value.error_code == "no_route"


def test_plan_pipeline_and_cached_heatmap():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    r = candidate(
        [[-87.6, 41.8], [-96.8, 32.8]], 900, 36000, [(0, 1, 36000)], "test", "Test"
    )
    r["id"] = "A"

    def weather(cells, end):
        return {
            c: {
                int((now + timedelta(hours=i)).timestamp()): {
                    "wind_mph": 40,
                    "gust_mph": 50,
                    "rain_in_hr": 0,
                    "snow_in_hr": 0,
                }
                for i in range(50)
            }
            for c in cells
        }

    with (
        patch("planner.services.find_routes", return_value=([r], [])),
        patch("planner.services.fetch", side_effect=weather),
    ):
        p = create_plan(
            {
                "origin": "Chicago, IL",
                "destination": "Dallas, TX",
                "departure": now,
                "load_lbs": 45000,
                "interval_miles": 25,
            }
        )
    route = p["routes"][0]
    assert route["summary"]["miles_by_level"]["severe"] == 900
    assert route["summary"]["average_risk"] == 3
    assert len(route["vertex_seconds"]) == len(route["geometry"]["coordinates"])
    with patch("planner.views.build", return_value={"hours": 49, "cells": []}) as build:
        assert APIClient().get(p["heatmap_url"]).status_code == 200
        assert APIClient().get(p["heatmap_url"]).status_code == 200
        assert build.call_count == 1
