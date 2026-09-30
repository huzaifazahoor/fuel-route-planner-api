# apps/fuel/views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fuel.exceptions import LocationNotFound, PlanningError, RoutingError
from apps.fuel.serializers import RoutePlanRequestSerializer
from apps.fuel.services.planner import plan_trip


class RoutePlanView(APIView):
    def post(self, request):
        serializer = RoutePlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = plan_trip(**serializer.validated_data)
        except LocationNotFound as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except PlanningError as error:
            return Response(
                {"error": str(error)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except RoutingError as error:
            return Response({"error": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(result, status=status.HTTP_200_OK)
