import logging
import threading
from urllib.parse import urlparse

import requests
from .errors import PlannerError

_local = threading.local()
log = logging.getLogger("planner.http")


def request(method, url, **kwargs):
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers["User-Agent"] = "WeatherTruckRouting/1.0"
    host = urlparse(url).netloc
    try:
        response = _local.session.request(method, url, timeout=(5, 25), **kwargs)
        if response.status_code >= 400:
            try:
                payload = response.json()
                error = payload.get("error", {})
                code = error.get("code") if isinstance(error, dict) else None
                if code in (2009, 2010) or payload.get("error_code") == 442:
                    raise PlannerError(
                        "No truck route connects these locations.", "no_route", 422
                    )
            except (ValueError, AttributeError):
                pass
            # Name the provider and status so hosted failures can be diagnosed from the
            # response and the server log (the generic message hid which one failed).
            body = (getattr(response, "text", "") or "")[:300]
            log.warning("%s %s returned HTTP %s: %s", method, host, response.status_code, body)
            if response.status_code == 429:
                raise PlannerError(
                    f"The provider {host} is rate-limiting requests right now. Please retry in a minute.",
                    "provider_rate_limited",
                    503,
                )
            raise PlannerError(
                f"The provider {host} returned HTTP {response.status_code}. Please retry."
            )
        return response.json()
    except requests.Timeout as exc:
        log.warning("%s %s timed out", method, host)
        raise PlannerError(
            f"The provider {host} timed out. Please retry.",
            "upstream_timeout",
            504,
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        log.warning("%s %s failed: %s", method, host, exc)
        raise PlannerError(
            f"The provider {host} is unavailable. Please retry."
        ) from exc
