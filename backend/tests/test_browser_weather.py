from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from planner.routing.common import candidate


def raw_records(manifest):
    start = datetime.fromisoformat(manifest["start_date"]).replace(tzinfo=timezone.utc)
    hours = (
        datetime.fromisoformat(manifest["end_date"]) - start.replace(tzinfo=None)
    ).days * 24 + 24
    times = [
        (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)
    ]
    return [
        {
            "cell": cell,
            "forecast": {
                "latitude": cell[1],
                "longitude": cell[0],
                "utc_offset_seconds": 0,
                "hourly_units": {
                    "time": "iso8601",
                    "wind_speed_10m": "mp/h",
                    "wind_gusts_10m": "mp/h",
                    "rain": "inch",
                    "snowfall": "cm",
                },
                "hourly": {
                    "time": times,
                    "wind_speed_10m": [40] * hours,
                    "wind_gusts_10m": [50] * hours,
                    "rain": [0] * hours,
                    "snowfall": [0] * hours,
                },
            },
        }
        for cell in manifest["cells"]
    ]


@pytest.fixture
def pending():
    r = candidate(
        [[-87.6, 41.8], [-88, 41.5]], 40, 3600, [(0, 1, 3600)], "test", "Test"
    )
    r["id"] = "A"
    with patch("planner.services.find_routes", return_value=([r], [])), patch(
        "planner.services.fetch"
    ) as fetch:
        response = APIClient().post(
            "/api/plan/",
            {
                "origin": "Chicago, IL",
                "destination": "Dallas, TX",
                "load_lbs": 45000,
                "weather_source": "browser",
            },
            format="json",
        )
    assert response.status_code == 200
    fetch.assert_not_called()
    return response.data


def test_browser_plan_and_heatmap_pipeline(pending):
    client = APIClient()
    assert pending["status"] == "weather_required"
    assert "recommendation" not in pending
    assert "risk" not in pending["routes"][0]["checkpoints"][0]
    assert client.get(pending["heatmap_url"]).status_code == 409
    manifest = pending["forecast_request"]
    body = {"forecasts": raw_records(manifest)}
    response = client.post(manifest["submit_url"], body, format="json")
    assert response.status_code == 200
    plan = response.data
    assert plan["status"] == "complete"
    assert plan["routes"][0]["summary"]["miles_by_level"]["severe"] == 40
    assert plan["recommendation"]["route_id"] == "A"
    assert client.post(manifest["submit_url"], body, format="json").data == plan
    heat = client.get(plan["heatmap_url"]).data
    assert heat["status"] == "weather_required"
    h = heat["forecast_request"]
    result = client.post(h["submit_url"], {"forecasts": raw_records(h)}, format="json")
    assert result.status_code == 200
    assert result.data["hours"] == 49
    assert all(len(layer) == 49 for layer in result.data["layers"].values())
    assert all(v == 3 for frame in result.data["layers"]["risk"] for v in frame)
    assert client.get(plan["heatmap_url"]).data == result.data
    assert not any("weather:v1:" in str(key) for key in cache._cache)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "wrong_cell",
        "wrong_coordinates",
        "wrong_timezone",
        "wrong_units",
        "missing_hour",
        "duplicate_hour",
        "offset_time",
        "negative",
        "null",
        "string",
        "bool",
        "extra_hours",
    ],
)
def test_bad_forecasts_cannot_complete_plan(pending, mutation):
    manifest = pending["forecast_request"]
    records = raw_records(manifest)
    f = records[0]["forecast"]
    if mutation == "missing":
        records.pop()
    elif mutation == "duplicate":
        records[-1] = deepcopy(records[0])
    elif mutation == "wrong_cell":
        records[0]["cell"] = [0, 0]
    elif mutation == "wrong_coordinates":
        f["longitude"] = 0
    elif mutation == "wrong_timezone":
        f["utc_offset_seconds"] = 3600
    elif mutation == "wrong_units":
        f["hourly_units"]["wind_speed_10m"] = "km/h"
    elif mutation == "missing_hour":
        for values in f["hourly"].values():
            del values[24:]
    elif mutation == "duplicate_hour":
        f["hourly"]["time"][1] = f["hourly"]["time"][0]
    elif mutation == "offset_time":
        f["hourly"]["time"][0] += "+02:00"
    elif mutation == "extra_hours":
        f["hourly"]["time"] *= 100
    else:
        f["hourly"]["rain"][0] = {
            "negative": -1,
            "null": None,
            "string": "0",
            "bool": True,
        }[mutation]
    result = APIClient().post(
        manifest["submit_url"], {"forecasts": records}, format="json"
    )
    assert result.status_code in (400, 422)
    assert cache.get("plan:" + pending["plan_id"])["status"] == "weather_required"


def test_expired_submission_and_invalid_body(pending):
    url = pending["forecast_request"]["submit_url"]
    assert APIClient().post(url, {}, format="json").status_code == 400
    cache.delete("plan:" + pending["plan_id"])
    assert APIClient().post(url, {"forecasts": []}, format="json").status_code == 404


def test_upload_size_is_bounded(pending, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100
    response = APIClient().post(
        pending["forecast_request"]["submit_url"],
        {"forecasts": raw_records(pending["forecast_request"])},
        format="json",
    )
    assert response.status_code == 413
    assert response.data["error"] == "forecast_limit"


def test_submission_isolated_and_complete_plan_cannot_be_overwritten(pending):
    client = APIClient()
    other = deepcopy(pending)
    other["plan_id"] = "00000000-0000-0000-0000-000000000001"
    cache.set("plan:" + other["plan_id"], other, 7200)
    body = {"forecasts": raw_records(pending["forecast_request"])}
    url = pending["forecast_request"]["submit_url"]
    first = client.post(url, body, format="json").data
    for record in body["forecasts"]:
        record["forecast"]["hourly"]["wind_speed_10m"] = [0] * len(
            record["forecast"]["hourly"]["time"]
        )
    assert client.post(url, body, format="json").data == first
    assert cache.get("plan:" + other["plan_id"])["status"] == "weather_required"


def test_plan_expiry_is_not_extended_by_submission(pending):
    pending["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    cache.set("plan:" + pending["plan_id"], pending, 7200)
    response = APIClient().post(
        pending["forecast_request"]["submit_url"], {"forecasts": []}, format="json"
    )
    assert response.status_code == 404
