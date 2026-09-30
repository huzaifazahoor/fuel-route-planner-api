# apps/fuel/services/planner.py
from apps.fuel.services.fuel_planner import plan_fuel_stops
from apps.fuel.services.locations import find_city
from apps.fuel.services.routing import get_route


def plan_trip(start, finish, start_fuel_gallons=0):
    """Find both cities, get one route from ORS, then pick the fuel stops."""
    start_point = find_city(start)
    finish_point = find_city(finish)

    route = get_route(start_point, finish_point)
    plan = plan_fuel_stops(route["points"], start_fuel_gallons)

    return {
        "start": {"name": start, "lat": start_point[0], "lng": start_point[1]},
        "finish": {"name": finish, "lat": finish_point[0], "lng": finish_point[1]},
        "duration_hours": round(route["duration_hours"], 1),
        **plan,
        # GeoJSON uses [lng, lat], so any map library can draw this line directly.
        "route": {
            "type": "LineString",
            "coordinates": [[lng, lat] for lat, lng in route["points"]],
        },
    }
