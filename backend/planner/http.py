import threading
import requests
from .errors import PlannerError

_local = threading.local()


def request(method, url, **kwargs):
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
        _local.session.headers["User-Agent"] = "WeatherTruckRouting/1.0"
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
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise PlannerError(
            "A routing or weather provider timed out. Please retry.",
            "upstream_timeout",
            504,
        ) from exc
    except (requests.RequestException, ValueError) as exc:
        raise PlannerError(
            "A routing or weather provider is unavailable. Please retry."
        ) from exc
