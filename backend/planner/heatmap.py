from datetime import datetime, timedelta
from math import ceil, cos, radians
from .geo import distance
from .weather import fetch, at
from .risk import classify


def corridor(routes):
    samples = [(p["lon"], p["lat"]) for r in routes for p in r["checkpoints"]]
    cells = set()
    for step in (0.5, 0.75, 1, 1.5, 2):
        cells = set()
        for lon, lat in samples:
            x, y = round(lon / step), round(lat / step)
            radius = ceil(40 / (69 * step * max(0.15, cos(radians(lat))))) + 1
            for i in range(x - radius, x + radius + 1):
                for j in range(y - 2, y + 3):
                    cell = (round(i * step, 4), round(j * step, 4))
                    if (
                        -180 <= cell[0] <= 180
                        and -90 <= cell[1] <= 90
                        and distance(cell, (lon, lat)) <= 40
                    ):
                        cells.add(cell)
        if len(cells) <= 250:
            break
    ordered = sorted(cells)
    if len(ordered) > 250:
        ordered = [ordered[int(i * len(ordered) / 250)] for i in range(250)]
    return ordered


def build(plan):
    start = datetime.fromisoformat(plan["forecast_start"])
    cells = corridor(plan["routes"])
    series = fetch(cells, start + timedelta(hours=48))
    layers = {k: [] for k in ("risk", "wind", "rain", "snow")}
    for hour in range(49):
        values = [at(series[c], start + timedelta(hours=hour)) for c in cells]
        layers["risk"].append([classify(w, plan["load_lbs"])["score"] for w in values])
        for layer, field in [
            ("wind", "wind_mph"),
            ("rain", "rain_in_hr"),
            ("snow", "snow_in_hr"),
        ]:
            layers[layer].append([w[field] for w in values])
    return {"start": start.isoformat(), "hours": 49, "cells": cells, "layers": layers}
