from django.urls import path
from planner.views import health, plan, heatmap

urlpatterns = [
    path("api/health/", health),
    path("api/plan/", plan),
    path("api/plan/<uuid:plan_id>/heatmap/", heatmap),
]
