# apps/fuel/services/fuel_planner.py
from dataclasses import dataclass

from apps.fuel.exceptions import PlanningError
from apps.fuel.services.stations import haversine_miles, stations_near

MPG = 10
TANK_GALLONS = 50  # 500 miles of range at 10 mpg
MAX_OFF_ROUTE_MILES = 10
START_RADIUS_MILES = 50  # stations this close to the start count as "at the start"


@dataclass
class Candidate:
    station: object
    mile: float  # mile marker along the route
    off_route_miles: float
    real_mile: float = 0.0  # true mile marker, for display


def cumulative_miles(points):
    """Mile marker of every route point, starting at 0."""
    miles = [0.0]
    for (lat1, lng1), (lat2, lng2) in zip(points, points[1:]):
        miles.append(miles[-1] + haversine_miles(lat1, lng1, lat2, lng2))
    return miles


def route_candidates(points):
    miles = cumulative_miles(points)
    candidates = []
    for near in stations_near(points, max_miles=MAX_OFF_ROUTE_MILES):
        real_mile = miles[near.point_index]
        mile = miles[near.point_index]
        if mile <= START_RADIUS_MILES:
            mile = 0.0
        candidates.append(Candidate(near.station, mile, near.distance_miles, real_mile))
    candidates.sort(key=lambda c: c.mile)
    return candidates, miles[-1]


def choose_stops(
    candidates, total_miles, start_fuel_gallons=0.0, mpg=MPG, tank_gallons=TANK_GALLONS
):
    """
    Greedy plan:
    - At a station, if a cheaper one is within reach, buy just enough to get there.
    - If not, fill the tank and go to the cheapest station within reach.
    - Near the finish, buy only what is needed to arrive.
    """
    max_range = tank_gallons * mpg
    position = 0.0
    fuel = start_fuel_gallons
    stops = []

    # Start: use the cheapest station at the start, if there is one.
    at_start = [c for c in candidates if c.mile == 0.0]
    if at_start:
        current = min(at_start, key=lambda c: c.station.price)
    else:
        current = None

    before_first_stop = None
    if current is None and not any(c.mile <= fuel * mpg for c in candidates):
        first_mile = next((c.mile for c in candidates if c.mile <= max_range), None)
        first = (
            None
            if first_mile is None
            else min(
                (c for c in candidates if c.mile <= first_mile + 30),
                key=lambda c: c.station.price,
            )
        )
        if first is None:
            raise PlanningError(
                f"No fuel station within {max_range} miles of the start."
            )
        extra = first.mile / mpg - fuel
        fuel += extra
        before_first_stop = {
            "gallons": round(extra, 2),
            "price_per_gallon": round(first.station.price, 3),
            "cost": round(extra * first.station.price, 2),
            "note": "No station near the start, so this fuel is priced at the first stop.",
        }

    while True:
        if current is None:
            # Not at a station: drive on the fuel we have.
            reach = position + fuel * mpg
            if total_miles <= reach:
                break
            ahead = [c for c in candidates if position < c.mile <= reach]
            if not ahead:
                raise PlanningError(
                    "No fuel station in reach from the start. "
                    "Try a higher start_fuel_gallons."
                )
            nxt = min(ahead, key=lambda c: (c.station.price, -c.mile))
            fuel -= (nxt.mile - position) / mpg
            position, current = nxt.mile, nxt
            continue

        price = current.station.price
        full_reach = position + max_range
        if total_miles <= position + fuel * mpg:
            break  # enough fuel to finish

        ahead = [
            c for c in candidates if position < c.mile <= min(full_reach, total_miles)
        ]
        cheaper = next((c for c in ahead if c.station.price <= price - 0.10), None)

        if cheaper is not None:
            # Buy just enough to reach the cheaper station.
            target = cheaper.mile
            nxt = cheaper
        elif total_miles <= full_reach:
            # Nothing cheaper before the finish: buy just enough to finish.
            target = total_miles
            nxt = None
        else:
            # Fill up and go to the cheapest station in reach.
            if not ahead:
                raise PlanningError(
                    f"No fuel station within {max_range} miles after mile {position:.0f}."
                )
            far = [c for c in ahead if c.mile >= position + 200]
            if far:
                nxt = min(far, key=lambda c: (c.station.price, -c.mile))
            else:
                nxt = max(ahead, key=lambda c: c.mile)  # stop as late as possible
            target = full_reach  # "fill the tank"

        needed = (target - position) / mpg
        buy = min(max(needed - fuel, 0.0), tank_gallons - fuel)
        if buy > 1e-9:
            stops.append(_stop(current, buy))
            fuel += buy

        if nxt is None:
            break
        fuel -= (nxt.mile - position) / mpg
        position, current = nxt.mile, nxt

    extra_cost = before_first_stop["cost"] if before_first_stop else 0
    extra_gallons = before_first_stop["gallons"] if before_first_stop else 0

    total_cost = sum(stop["cost"] for stop in stops) + extra_cost
    total_gallons = sum(stop["gallons"] for stop in stops) + extra_gallons
    return {
        "total_miles": round(total_miles, 1),
        "total_gallons_bought": round(total_gallons, 2),
        "total_fuel_cost": round(total_cost, 2),
        "fuel_before_first_stop": before_first_stop,
        "stops": stops,
    }


def _stop(candidate, gallons):
    s = candidate.station
    return {
        "station_id": s.id,
        "name": s.name,
        "address": s.address,
        "city": s.city,
        "state": s.state,
        "lat": s.lat,
        "lng": s.lng,
        "mile_marker": round(candidate.real_mile, 1),
        "off_route_miles": round(candidate.off_route_miles, 1),
        "price_per_gallon": round(s.price, 3),
        "gallons": round(gallons, 2),
        "cost": round(gallons * s.price, 2),
    }


def plan_fuel_stops(points, start_fuel_gallons=0.0):
    """points: list of (lat, lng) along the route, start to finish."""
    candidates, total_miles = route_candidates(points)
    return choose_stops(candidates, total_miles, start_fuel_gallons)
