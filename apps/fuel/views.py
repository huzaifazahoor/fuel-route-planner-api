# apps/fuel/views.py
from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fuel.exceptions import LocationNotFound, PlanningError, RoutingError
from apps.fuel.serializers import RoutePlanRequestSerializer
from apps.fuel.services.planner import plan_trip

ERROR_STATUS = {
    LocationNotFound: status.HTTP_400_BAD_REQUEST,
    PlanningError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    RoutingError: status.HTTP_502_BAD_GATEWAY,
}


def run_plan(data):
    """Validate input and plan the trip. Returns (result, error, status_code)."""
    serializer = RoutePlanRequestSerializer(data=data)
    if not serializer.is_valid():
        return None, serializer.errors, status.HTTP_400_BAD_REQUEST
    try:
        return plan_trip(**serializer.validated_data), None, status.HTTP_200_OK
    except (LocationNotFound, PlanningError, RoutingError) as error:
        return None, {"error": str(error)}, ERROR_STATUS[type(error)]


class RoutePlanView(APIView):
    def post(self, request):
        result, error, code = run_plan(request.data)
        if error:
            return Response(error, status=code)

        query = urlencode(
            {
                "start": result["start"]["name"],
                "finish": result["finish"]["name"],
                "start_fuel_gallons": request.data.get("start_fuel_gallons", 0),
            }
        )
        result["map_url"] = request.build_absolute_uri(
            f"{reverse('route-map')}?{query}"
        )
        return Response(result, status=code)


class RouteMapView(View):
    """Same plan as the API, drawn on a Leaflet map. Uses the cached route."""

    def get(self, request):
        result, error, code = run_plan(request.GET.dict())
        return render(
            request,
            "fuel/route_map.html",
            {"plan": result, "error": error},
            status=code,
        )
