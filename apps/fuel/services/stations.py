# app/fuel/services/stations.py
import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from apps.fuel.models import FuelStation

CELL_SIZE_DEG = 0.5
EARTH_RADIUS_MILES = 3958.8

# A 0.5 degree cell is at least ~24 miles wide in the lower 48 states,
# so the 3x3 block around a point safely covers anything within this distance.
MAX_SEARCH_MILES = 20


@dataclass(frozen=True, slots=True)
class Station:
    id: int
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lng: float


@dataclass(frozen=True, slots=True)
class NearbyStation:
    station: Station
    point_index: int  # index of the closest route point
    distance_miles: float  # how far the station is from the route


def haversine_miles(lat1, lng1, lat2, lng2):
    """Straight-line distance between two points on Earth, in miles."""
    lat1, lng1, lat2, lng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def cell_for(lat, lng):
    return (math.floor(lat / CELL_SIZE_DEG), math.floor(lng / CELL_SIZE_DEG))


def neighbor_cells(cell):
    row, col = cell
    return [(row + dr, col + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


@lru_cache(maxsize=1)
def get_station_grid():
    """Load all stations once and group them by grid cell. Reused on every request."""
    grid = defaultdict(list)
    rows = FuelStation.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).values_list(
        "opis_id",
        "name",
        "address",
        "city",
        "state",
        "retail_price",
        "latitude",
        "longitude",
    )

    for opis_id, name, address, city, state, price, lat, lng in rows:
        station = Station(opis_id, name, address, city, state, float(price), lat, lng)
        grid[cell_for(lat, lng)].append(station)
    return dict(grid)


def stations_near(points, max_miles=10):
    """
    Find stations within max_miles of the route.

    points: list of (lat, lng) route points, in order from start to finish.
    Returns one NearbyStation per station, tied to its closest route point.
    """
    if max_miles > MAX_SEARCH_MILES:
        raise ValueError(f"max_miles must be {MAX_SEARCH_MILES} or less.")

    grid = get_station_grid()

    # Group route points by cell, so each station only checks points close to it.
    points_by_cell = defaultdict(list)
    for index, (lat, lng) in enumerate(points):
        points_by_cell[cell_for(lat, lng)].append(index)

    # Only cells touching the route can hold nearby stations.
    candidate_cells = set()
    for cell in points_by_cell:
        candidate_cells.update(neighbor_cells(cell))

    results = []
    for cell in candidate_cells:
        for station in grid.get(cell, ()):
            best_index, best_distance = None, max_miles
            for near_cell in neighbor_cells(cell):
                for index in points_by_cell.get(near_cell, ()):
                    lat, lng = points[index]
                    distance = haversine_miles(station.lat, station.lng, lat, lng)
                    if distance <= best_distance:
                        best_index, best_distance = index, distance
            if best_index is not None:
                results.append(NearbyStation(station, best_index, best_distance))
    return results
