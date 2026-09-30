# apps/fuel/services/locations.py
import csv
from functools import lru_cache

from django.conf import settings

from apps.fuel.exceptions import LocationNotFound

CITIES_FILE = settings.BASE_DIR / "data" / "uscities.csv"

# Make "St. Louis" and "Saint Louis" match, same for Mt/Ft.
CITY_WORDS = {"st": "saint", "ste": "sainte", "mt": "mount", "ft": "fort"}


def normalize_city(name):
    words = name.strip().lower().replace(".", "").replace("-", " ").split()
    return "".join(CITY_WORDS.get(word, word) for word in words)


def load_city_coords(path):
    """Map (city, state) -> (lat, lng). If a name repeats, keep the biggest city."""
    coords = {}
    best_population = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (normalize_city(row["city_ascii"]), row["state_id"].strip().upper())
            population = float(row["population"] or 0)
            if population >= best_population.get(key, -1):
                best_population[key] = population
                coords[key] = (float(row["lat"]), float(row["lng"]))
    return coords


@lru_cache(maxsize=1)
def get_city_coords():
    return load_city_coords(CITIES_FILE)


def find_city(text):
    """Turn "Dallas, TX" into (lat, lng) with no outside API call."""
    city, state = [part.strip() for part in text.split(",")]
    point = get_city_coords().get((normalize_city(city), state.upper()))
    if point is None:
        raise LocationNotFound(f'Could not find "{text}" in the US cities list.')
    return point
