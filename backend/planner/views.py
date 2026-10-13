from django.core.cache import cache
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from .serializers import PlanInput
from .services import create_plan
from .heatmap import build
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
    result = cache.get("heatmap:" + str(plan_id))
    if result is None:
        saved = cache.get("plan:" + str(plan_id))
        if saved is None:
            raise PlannerError(
                "This plan expired. Plan the trip again.", "plan_expired", 404
            )
        result = build(saved)
        cache.set("heatmap:" + str(plan_id), result, 1800)
    return Response(result)
