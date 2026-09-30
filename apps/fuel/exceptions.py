# app/fuel/exceptions.py
class LocationNotFound(Exception):
    """The start or finish city is not in our US cities list."""


class RoutingError(Exception):
    """The outside routing API failed or returned no route."""


class PlanningError(Exception):
    """No valid set of fuel stops exists for this route."""
