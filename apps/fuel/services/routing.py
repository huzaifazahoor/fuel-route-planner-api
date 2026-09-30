# apps/fuel/services/routing.py
import os

import requests
from django.core.cache import cache

from apps.fuel.exceptions import RoutingError
from apps.fuel.services.stations import haversine_miles

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
METERS_PER_MILE = 1609.344
TIMEOUT_SECONDS = 15
CACHE_SECONDS = 60 * 60 * 24  # routes rarely change, so reuse them for a day


def thin_points(points, min_step_miles=0.5):
    kept = [points[0]]
    for point in points[1:-1]:
        if haversine_miles(*kept[-1], *point) >= min_step_miles:
            kept.append(point)
    kept.append(points[-1])
    return kept


def get_route(start, finish):
    """
    One call to OpenRouteService for a truck route.

    start, finish: (lat, lng)
    Returns {"points": [(lat, lng), ...], "distance_miles": float, "duration_hours": float}
    """
    cache_key = f"route:{start[0]:.4f},{start[1]:.4f}:{finish[0]:.4f},{finish[1]:.4f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        raise RoutingError("ORS_API_KEY is not set.")

    # ORS wants [lng, lat], not [lat, lng].
    body = {"coordinates": [[start[1], start[0]], [finish[1], finish[0]]]}

    try:
        response = requests.post(
            ORS_URL,
            json=body,
            headers={"Authorization": api_key},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise RoutingError(f"Could not reach the routing service: {error}") from error

    if response.status_code != 200:
        raise RoutingError(
            f"Routing service error {response.status_code}: {response.text[:200]}"
        )

    try:
        feature = response.json()["features"][0]
        coordinates = feature["geometry"]["coordinates"]
        summary = feature["properties"]["summary"]
    except (KeyError, IndexError, ValueError) as error:
        raise RoutingError(
            "Routing service returned an unexpected response."
        ) from error

    route = {
        "points": thin_points([(lat, lng) for lng, lat in coordinates]),
        "distance_miles": summary["distance"] / METERS_PER_MILE,
        "duration_hours": summary.get("duration", 0) / 3600,
    }
    cache.set(cache_key, route, CACHE_SECONDS)
    return route
