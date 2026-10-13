"""Offline data preparation: clean the fuel CSV and attach coordinates."""

import csv
import re

from .us_states import US_STATES

_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|metro government|"
    r"unified government|urban county|city|town|township|village|borough|municipality|cdp|"
    r"plantation|corporation)$"
)
_ABBREVIATIONS = {"st": "saint", "ste": "sainte", "mt": "mount", "ft": "fort"}


def normalise_place(name: str, *, census: bool = False) -> str:
    """Comparable form of a place name. census=True also drops Census place-type suffixes."""
    s = name.strip().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[-/]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if census:
        s = _SUFFIX.sub("", s)
    s = " ".join(_ABBREVIATIONS.get(w, w) for w in s.split())
    return re.sub(r"\bmc (\w)", r"mc\1", s)


def read_places(path) -> dict[tuple[str, str], tuple[float, float]]:
    with open(path, newline="", encoding="utf-8") as f:
        return {
            (r["state"], r["name"]): (float(r["lat"]), float(r["lon"]))
            for r in csv.DictReader(f)
        }
