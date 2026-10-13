from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers


class PlanInput(serializers.Serializer):
    weather_source = serializers.ChoiceField(
        choices=["server", "browser"], default="server"
    )
    origin = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    departure = serializers.DateTimeField(default=timezone.now)
    load_lbs = serializers.IntegerField(min_value=0, max_value=80000, default=35000)
    interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)

    def validate_departure(self, value):
        now = timezone.now()
        if not now - timedelta(hours=1) <= value <= now + timedelta(days=7):
            raise serializers.ValidationError(
                "Departure must be from one hour ago to seven days ahead."
            )
        return value
