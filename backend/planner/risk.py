"""Assessment thresholds; load modifies sustained-wind risk only."""

LEVELS = ("low", "moderate", "high", "severe", "no_travel")


def classify(weather, load_lbs):
    wind, rain, snow = (weather[k] for k in ("wind_mph", "rain_in_hr", "snow_in_hr"))
    wind_score = sum(wind >= n for n in (25, 35, 45, 55))
    adjusted = wind_score
    if 45 <= wind < 55 and load_lbs > 30000:
        adjusted = 4
    elif 35 <= wind < 45 and load_lbs > 40000:
        adjusted = 3
    scores = {
        "wind": adjusted,
        "rain": 4 if rain > 1 else sum(rain >= n for n in (0.1, 0.25, 0.5)),
        "snow": 4 if snow > 3 else sum(snow >= n for n in (0.5, 1, 2)),
    }
    driver = max(scores, key=scores.get)
    return {
        "level": LEVELS[scores[driver]],
        "score": scores[driver],
        "driver": driver,
        "load_adjusted": adjusted != wind_score,
    }
