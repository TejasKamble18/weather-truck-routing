from django.core.cache import cache
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from .serializers import PlanInput
from .services import create_plan, score_plan
from .heatmap import build, corridor
from .browser_weather import manifest, validate
from .errors import PlannerError


@api_view(["GET"])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def plan(request):
    inputs = PlanInput(data=request.data)
    inputs.is_valid(raise_exception=True)
    return Response(create_plan(inputs.validated_data))


@api_view(["GET"])
def heatmap(request, plan_id):
    saved = saved_plan(plan_id)
    if saved.get("status") == "weather_required":
        raise PlannerError(
            "Complete the checkpoint weather first.", "weather_required", 409
        )
    result = cache.get("heatmap:" + str(plan_id))
    if result is None:
        if saved.get("weather_source") == "browser":
            return Response(
                {
                    "status": "weather_required",
                    "forecast_request": heatmap_manifest(saved),
                }
            )
        result = build(saved)
        cache.set("heatmap:" + str(plan_id), result, 1800)
    return Response(result)


def saved_plan(plan_id):
    saved = cache.get("plan:" + str(plan_id))
    if saved is None or (
        "expires_at" in saved
        and datetime.fromisoformat(saved["expires_at"]) <= timezone.now()
    ):
        raise PlannerError(
            "This plan expired. Plan the trip again.", "plan_expired", 404
        )
    return saved


def remaining(plan):
    return max(
        1,
        int(
            (
                datetime.fromisoformat(plan["expires_at"]) - timezone.now()
            ).total_seconds()
        ),
    )


def heatmap_manifest(plan):
    start = datetime.fromisoformat(plan["forecast_start"])
    return manifest(
        corridor(plan["routes"]),
        start + timedelta(hours=48),
        start,
        f"/api/plan/{plan['plan_id']}/heatmap/weather/",
    )


def submitted_forecasts(request):
    try:
        if len(request.body) > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            raise RequestDataTooBig()
    except RequestDataTooBig:
        raise PlannerError("The forecast upload is too large.", "forecast_limit", 413)
    if not isinstance(request.data, dict) or set(request.data) != {"forecasts"}:
        raise PlannerError("Submit a forecasts array only.", "invalid_forecast", 400)
    return request.data["forecasts"]


@api_view(["POST"])
def plan_weather(request, plan_id):
    saved = saved_plan(plan_id)
    if saved.get("weather_source") != "browser":
        raise PlannerError("This plan uses server weather.", "invalid_input", 409)
    if saved["status"] == "complete":
        return Response(saved)
    series = validate(submitted_forecasts(request), saved["forecast_request"])
    result = score_plan(saved, series)
    cache.set("plan:" + str(plan_id), result, remaining(saved))
    return Response(result)


@api_view(["POST"])
def heatmap_weather(request, plan_id):
    saved = saved_plan(plan_id)
    if saved.get("weather_source") != "browser" or saved.get("status") != "complete":
        raise PlannerError(
            "Complete the browser weather plan first.", "weather_required", 409
        )
    result = cache.get("heatmap:" + str(plan_id))
    if result is None:
        series = validate(submitted_forecasts(request), heatmap_manifest(saved))
        result = build(saved, series)
        cache.set("heatmap:" + str(plan_id), result, min(1800, remaining(saved)))
    return Response(result)
