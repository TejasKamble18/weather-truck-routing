from datetime import datetime, timezone
import pytest
from planner.geo import decode_polyline
from planner.routing.common import candidate
from planner.routing.routes import distinct
from planner.checkpoints import sample
from planner.ranking import summarize, rank
from planner.risk import LEVELS


def route():
    return candidate(
        [[-90, 40], [-89, 40], [-88, 40]],
        100,
        10800,
        [(0, 1, 7200), (1, 2, 3600)],
        "test",
        "Test route",
    )


def test_polyline_reference():
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", 5) == [
        [-120.2, 38.5],
        [-120.95, 40.7],
        [-126.453, 43.252],
    ]


def test_checkpoints_follow_maneuver_time_not_average_speed():
    departure = datetime(2026, 10, 12, tzinfo=timezone.utc)
    points = sample(route(), 25, departure)
    assert [p["mile"] for p in points] == [0, 25, 50, 75, 100]
    assert points[2]["eta"] == "2026-10-12T02:00:00+00:00"
    assert points[-1]["eta"] == "2026-10-12T03:00:00+00:00"


def test_short_route_has_both_endpoints():
    r = route()
    r["distance_miles"] = 4
    r["_miles"] = [0, 2, 4]
    assert [p["mile"] for p in sample(r, 50, datetime.now(timezone.utc))] == [0, 4]


def test_summary_covers_all_miles_with_midpoint_attribution():
    points = [
        {"mile": m, "risk": {"level": level}}
        for m, level in [(0, "low"), (25, "high"), (40, "severe")]
    ]
    s = summarize(points, 40)
    assert s["miles_by_level"] == dict(
        low=12.5, moderate=0, high=20, severe=7.5, no_travel=0
    )
    assert s["average_risk"] == pytest.approx((20 * 2 + 7.5 * 3) / 40)


@pytest.mark.parametrize(
    "dimension", ["no_travel", "severe", "high", "average", "time"]
)
def test_lexicographic_ranking(dimension):
    def r(id):
        return {
            "id": id,
            "duration_hours": 1,
            "summary": {
                "miles_by_level": dict.fromkeys(LEVELS, 0),
                "average_risk": 0,
                "no_travel_warning": False,
            },
        }

    a, b = r("A"), r("B")
    if dimension in LEVELS:
        a["summary"]["miles_by_level"][dimension] = 1
        b["duration_hours"] = 100
    elif dimension == "average":
        a["summary"]["average_risk"] = 0.1
        b["duration_hours"] = 100
    else:
        a["duration_hours"] = 2
    assert rank([a, b])["route_id"] == "B"


def test_duplicate_routes_removed():
    assert len(distinct([route(), route()])) == 1


def test_non_monotonic_timing_rejected():
    with pytest.raises(ValueError):
        candidate(
            [[-90, 40], [-89, 40], [-88, 40]],
            100,
            60,
            [(0, 2, 40), (0, 1, 20)],
            "test",
            "Test",
        )


def _ranked(id, *, avg=0.0, hours=1.0, severe=0.0):
    miles = dict.fromkeys(LEVELS, 0.0)
    miles["severe"] = severe
    return {
        "id": id,
        "duration_hours": hours,
        "summary": {
            "miles_by_level": miles,
            "average_risk": avg,
            "no_travel_warning": False,
        },
    }


def test_reason_shows_a_visible_difference_for_close_average_risk():
    # Live Denver → Salt Lake City produced "Lowest average risk: 0.02 vs 0.02".
    reason = rank([_ranked("A", avg=0.0199), _ranked("C", avg=0.0186)])["reason"]
    assert "0.019" in reason and "0.020" in reason


def test_reason_uses_readable_units():
    assert (
        "14h 49m vs 14h 55m"
        in rank([_ranked("A", hours=14.81), _ranked("B", hours=14.92)])["reason"]
    )
    assert (
        "12.0 vs 30.5 mi"
        in rank([_ranked("A", severe=12), _ranked("B", severe=30.5)])["reason"]
    )


@pytest.mark.parametrize(
    "field,a,b,comparison",
    [
        ("severe", 0.011, 0.049, "0.01 vs 0.05 mi"),
        ("avg", 0.010001, 0.010002, "0.010001 vs 0.010002"),
        ("hours", 1.001, 1.002, "1h 00m 04s vs 1h 00m 07s"),
        ("hours", 1.00001, 1.00002, "less than 1 s difference"),
        ("severe", 0.01000001, 0.01000002, "less than 0.000001 mi difference"),
        ("avg", 0.01000001, 0.01000002, "less than 0.000001 difference"),
    ],
)
def test_reason_never_displays_unequal_values_as_a_tie(field, a, b, comparison):
    result = rank([_ranked("B", **{field: b}), _ranked("A", **{field: a})])
    assert result["route_id"] == "A"
    assert comparison in result["reason"]


def test_actual_tie_still_has_a_tie_explanation():
    result = rank([_ranked("A"), _ranked("B")])
    assert result["reason"] == "Equal risk and travel time; route order breaks the tie."
