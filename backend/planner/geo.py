from bisect import bisect_right
from math import asin, cos, radians, sin, sqrt


def distance(a, b):
    """Great-circle miles; coordinates throughout this app are [longitude, latitude]."""
    lon1, lat1, lon2, lat2 = map(radians, (*a, *b))
    x = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    return 3958.7613 * 2 * asin(min(1, sqrt(x)))


def cumulative(coords):
    miles = [0.0]
    for a, b in zip(coords, coords[1:]):
        miles.append(miles[-1] + distance(a, b))
    return miles


def interpolate(xs, values, x):
    i = max(0, min(len(xs) - 2, bisect_right(xs, x) - 1))
    f = max(0, min(1, (x - xs[i]) / (xs[i + 1] - xs[i]) if xs[i + 1] > xs[i] else 0))
    a, b = values[i], values[i + 1]
    if isinstance(a, (list, tuple)):
        return [p + (q - p) * f for p, q in zip(a, b)]
    return a + (b - a) * f


def decode_polyline(encoded, precision=6):
    coords, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        diffs = []
        for _ in range(2):
            value, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                value |= (b & 31) << shift
                shift += 5
                if b < 32:
                    break
            diffs.append(~(value >> 1) if value & 1 else value >> 1)
        lat += diffs[0]
        lon += diffs[1]
        coords.append([lon / 10**precision, lat / 10**precision])
    return coords
