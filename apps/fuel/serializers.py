# apps/fuel/serializers.py
from rest_framework import serializers

MAX_TANK_GALLONS = 50  # 500 miles range / 10 mpg


class RoutePlanRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=100)
    finish = serializers.CharField(max_length=100)
    start_fuel_gallons = serializers.FloatField(
        required=False, default=0, min_value=0, max_value=MAX_TANK_GALLONS
    )

    def _validate_city_state(self, value):
        # Expect "City, ST", for example "Dallas, TX".
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 2 or not parts[0] or len(parts[1]) != 2:
            raise serializers.ValidationError(
                'Use the format "City, ST", like "Dallas, TX".'
            )
        return f"{parts[0]}, {parts[1].upper()}"

    def validate_start(self, value):
        return self._validate_city_state(value)

    def validate_finish(self, value):
        return self._validate_city_state(value)
