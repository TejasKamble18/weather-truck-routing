"""Validate untrusted browser forecasts without writing the provider weather cache."""

from datetime import datetime, timedelta, timezone
from math import isfinite

from .errors import PlannerError
from .weather import FIELDS, forecast_days, parse_series

MAX_CELLS = 1000
MAX_HOURS = 17 * 24


def manifest(cells, end, now, submit_url):
    cells = sorted(set(cells))
    if not cells or len(cells) > MAX_CELLS:
        raise PlannerError(
            "This trip needs too many forecast cells. Use a larger checkpoint interval.",
            "forecast_limit",
            422,
        )
    days = forecast_days(end, now)
    return {
        "cells": [list(c) for c in cells],
        # Absolute dates keep requests and validation stable across midnight.
        "start_date": (now.date() - timedelta(days=1)).isoformat(),
        "end_date": (now.date() + timedelta(days=days - 1)).isoformat(),
        "hourly": list(FIELDS.values()),
        "submit_url": submit_url,
    }


def validate(records, specification):
    def invalid():
        raise PlannerError(
            "The submitted forecasts do not match this plan or contain invalid weather. Fetch the weather again.",
            "invalid_forecast",
            400,
        )

    expected = {tuple(c) for c in specification["cells"]}
    if not isinstance(records, list) or len(records) != len(expected):
        invalid()
    first = datetime.fromisoformat(specification["start_date"]).replace(
        tzinfo=timezone.utc
    )
    end = datetime.fromisoformat(specification["end_date"]).replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1)
    expected_times = [
        int((first + timedelta(hours=i)).timestamp())
        for i in range(int((end - first).total_seconds() / 3600))
    ]
    result = {}
    try:
        for record in records:
            cell = tuple(record["cell"])
            if cell not in expected or cell in result:
                invalid()
            data = record["forecast"]
            # Open-Meteo returns model grid coordinates, not necessarily the requested point.
            for value, target in (
                (data["longitude"], cell[0]),
                (data["latitude"], cell[1]),
            ):
                if (
                    type(value) not in (int, float)
                    or not isfinite(value)
                    or abs(value - target) > 0.25
                ):
                    invalid()
            if (
                data["utc_offset_seconds"] != 0
                or data["hourly_units"]["time"] != "iso8601"
            ):
                invalid()
            hourly = data["hourly"]
            times = hourly["time"]
            if (
                not isinstance(times, list)
                or len(times) != len(expected_times)
                or len(times) > MAX_HOURS
            ):
                invalid()
            stamps = []
            for value in times:
                moment = datetime.fromisoformat(value)
                if moment.tzinfo is not None and moment.utcoffset() != timedelta(0):
                    invalid()
                stamps.append(int(moment.replace(tzinfo=timezone.utc).timestamp()))
                if moment.minute or moment.second or moment.microsecond:
                    invalid()
            if stamps != expected_times:
                invalid()
            for field in FIELDS.values():
                values = hourly[field]
                if not isinstance(values, list) or len(values) != len(times):
                    invalid()
                if any(
                    type(v) not in (int, float) or not isfinite(v) or v < 0
                    for v in values
                ):
                    invalid()
            result[cell] = parse_series(data)
    except (KeyError, TypeError, ValueError, OverflowError, PlannerError):
        invalid()
    return result
