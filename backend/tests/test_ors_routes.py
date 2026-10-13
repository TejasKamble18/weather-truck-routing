from types import SimpleNamespace
from unittest.mock import patch

from planner.routing.ors import ORSClient

START = SimpleNamespace(lat=32.78, lon=-96.80)
END = SimpleNamespace(lat=29.76, lon=-95.37)
ORS_RESPONSE = {
    "features": [{
        "geometry": {"coordinates": [[-96.80, 32.78], [-96.30, 31.20], [-95.37, 29.76]]},
        "properties": {
            "summary": {"distance": 468000.0, "duration": 18000.0},
            "segments": [
                {"steps": [{"distance": 230000, "duration": 9000, "way_points": [0, 1], "name": "I 45"},
                           {"distance": 0, "duration": 0, "way_points": [1, 1], "name": "-"}]},
                {"steps": [{"distance": 238000, "duration": 9000, "way_points": [1, 2], "name": "US 287"},
                           {"distance": 0, "duration": 0, "way_points": [2, 2], "name": "-"}]},
            ],
        },
    }]
}


def test_via_route_lets_points_snap_to_the_nearest_road(settings):
    # A via point offset from the main route usually lands in open country; with ORS's
    # default 350 m snapping radius it fails with "no routable point" (seen live on Dallas → Houston).
    settings.ORS_API_KEY = "test-key"
    with patch("planner.routing.ors.request", return_value=ORS_RESPONSE) as request:
        route = ORSClient().route(START, END, [-96.30, 31.20])
    body = request.call_args.kwargs["json"]
    assert body["radiuses"] == [-1, -1, -1]
    assert route["distance_miles"] > 290
