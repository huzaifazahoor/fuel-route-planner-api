# apps/fuel/management/commands/try_planner.py
import json

from django.core.management.base import BaseCommand

from apps.fuel.services.fuel_planner import plan_fuel_stops
from apps.fuel.services.locations import find_city


def straight_line(start, finish, steps=1000):
    """Fake route for testing: evenly spaced points between two cities."""
    (lat1, lng1), (lat2, lng2) = start, finish
    return [
        (lat1 + (lat2 - lat1) * i / steps, lng1 + (lng2 - lng1) * i / steps)
        for i in range(steps + 1)
    ]


class Command(BaseCommand):
    help = "Test the fuel planner on a straight-line route (no routing API needed)."

    def add_arguments(self, parser):
        parser.add_argument("--start", default="Dallas, TX")
        parser.add_argument("--finish", default="Chicago, IL")
        parser.add_argument("--fuel", type=float, default=0.0)

    def handle(self, *args, **options):
        points = straight_line(
            find_city(options["start"]), find_city(options["finish"])
        )
        result = plan_fuel_stops(points, options["fuel"])
        self.stdout.write(json.dumps(result, indent=2))
