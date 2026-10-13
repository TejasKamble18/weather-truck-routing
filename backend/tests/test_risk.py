import pytest
from planner.risk import classify


@pytest.mark.parametrize(
    "field,value,score",
    [
        ("wind_mph", 24.99, 0),
        ("wind_mph", 25, 1),
        ("wind_mph", 34.99, 1),
        ("wind_mph", 35, 2),
        ("wind_mph", 44.99, 2),
        ("wind_mph", 45, 3),
        ("wind_mph", 54.99, 3),
        ("wind_mph", 55, 4),
        ("rain_in_hr", 0.099, 0),
        ("rain_in_hr", 0.1, 1),
        ("rain_in_hr", 0.249, 1),
        ("rain_in_hr", 0.25, 2),
        ("rain_in_hr", 0.499, 2),
        ("rain_in_hr", 0.5, 3),
        ("rain_in_hr", 1, 3),
        ("rain_in_hr", 1.001, 4),
        ("snow_in_hr", 0.499, 0),
        ("snow_in_hr", 0.5, 1),
        ("snow_in_hr", 0.999, 1),
        ("snow_in_hr", 1, 2),
        ("snow_in_hr", 1.999, 2),
        ("snow_in_hr", 2, 3),
        ("snow_in_hr", 3, 3),
        ("snow_in_hr", 3.001, 4),
    ],
)
def test_all_boundaries(field, value, score):
    weather = {"wind_mph": 0, "rain_in_hr": 0, "snow_in_hr": 0, "gust_mph": 90}
    weather[field] = value
    assert classify(weather, 0)["score"] == score


@pytest.mark.parametrize(
    "wind,load,score,adjusted",
    [
        (45, 30000, 3, False),
        (45, 30001, 4, True),
        (35, 40000, 2, False),
        (35, 40001, 3, True),
        (55, 0, 4, False),
        (34, 80000, 1, False),
    ],
)
def test_load_boundaries(wind, load, score, adjusted):
    result = classify({"wind_mph": wind, "rain_in_hr": 0, "snow_in_hr": 0}, load)
    assert (result["score"], result["load_adjusted"]) == (score, adjusted)


def test_worst_condition_wins():
    assert (
        classify({"wind_mph": 35, "rain_in_hr": 1.1, "snow_in_hr": 0}, 50000)["driver"]
        == "rain"
    )
