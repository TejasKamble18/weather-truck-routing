import json
from unittest.mock import Mock, patch

import pytest
import requests

from planner import http
from planner.errors import PlannerError


def _session(status, body=None):
    response = Mock(status_code=status, text=json.dumps(body) if body is not None else "")
    response.json.side_effect = ValueError if body is None else None
    if body is not None:
        response.json.return_value = body
    response.raise_for_status.side_effect = requests.HTTPError(f"{status} error")
    session = Mock()
    session.request.return_value = response
    return session


def test_rate_limit_names_the_provider_and_is_503(caplog):
    # On shared cloud IPs, free providers answer 429; the user and the logs must see which one.
    session = _session(429, {"reason": "Daily API request limit exceeded"})
    with patch.object(http._local, "session", session, create=True), pytest.raises(PlannerError) as error:
        http.request("GET", "https://api.open-meteo.com/v1/forecast")
    assert error.value.status_code == 503
    assert error.value.error_code == "provider_rate_limited"
    assert "api.open-meteo.com" in str(error.value.detail)
    assert "api.open-meteo.com" in caplog.text and "429" in caplog.text


def test_other_provider_errors_name_the_provider_and_status(caplog):
    session = _session(403, {"error": "Access to this API has been disallowed"})
    with patch.object(http._local, "session", session, create=True), pytest.raises(PlannerError) as error:
        http.request("POST", "https://api.heigit.org/openrouteservice/v2/directions/driving-hgv/geojson")
    assert error.value.status_code == 502
    assert "api.heigit.org" in str(error.value.detail) and "403" in str(error.value.detail)
    assert "disallowed" in caplog.text
