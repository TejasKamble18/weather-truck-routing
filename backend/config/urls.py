from django.urls import path
from planner.views import health, plan, heatmap, plan_weather, heatmap_weather

urlpatterns = [
    path("api/health/", health),
    path("api/plan/", plan),
    path("api/plan/<uuid:plan_id>/heatmap/", heatmap),
    path("api/plan/<uuid:plan_id>/weather/", plan_weather),
    path("api/plan/<uuid:plan_id>/heatmap/weather/", heatmap_weather),
]
