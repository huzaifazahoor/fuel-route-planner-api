# apps/fuel/urls.py
from django.urls import path

from apps.fuel.views import RoutePlanView

urlpatterns = [
    path("route/", RoutePlanView.as_view(), name="route-plan"),
]
