import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.fuel.models import FuelStation
from apps.fuel.services.locations import load_city_coords, normalize_city

CANADIAN_PROVINCES = {"AB", "BC", "MB", "NB", "NS", "ON", "QC", "SK", "YT"}


class Command(BaseCommand):
    help = "Load fuel stations from the CSV and add lat/long from an offline US cities file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prices",
            default=str(settings.BASE_DIR / "fuel-prices-for-be-assessment.csv"),
        )
        parser.add_argument(
            "--cities",
            default=str(settings.BASE_DIR / "data" / "uscities.csv"),
        )

    def handle(self, *args, **options):
        prices_path = Path(options["prices"])
        cities_path = Path(options["cities"])
        for path in (prices_path, cities_path):
            if not path.exists():
                raise CommandError(f"File not found: {path}")

        coords = load_city_coords(cities_path)
        stations, skipped = self.load_cheapest_stations(prices_path)

        objects = []
        unmatched = 0
        for opis_id, row in stations.items():
            key = (normalize_city(row["City"]), row["State"].strip().upper())
            point = coords.get(key)
            if point is None:
                unmatched += 1
            lat, lng = point if point else (None, None)

            objects.append(
                FuelStation(
                    opis_id=opis_id,
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=row["State"].strip().upper(),
                    rack_id=int(row["Rack ID"]),
                    retail_price=row["price"],
                    latitude=lat,
                    longitude=lng,
                )
            )

        # Delete and reload, so running the command twice gives the same result.
        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(objects, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f"Saved {len(objects)} stations."))
        self.stdout.write(f"Skipped rows (Canada or bad data): {skipped}")
        self.stdout.write(f"Stations with no city match (no lat/long): {unmatched}")

    def load_cheapest_stations(self, path):
        """Keep only US rows, and only the cheapest row for each station ID."""
        cheapest = {}
        skipped = 0
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["State"].strip().upper() in CANADIAN_PROVINCES:
                    skipped += 1
                    continue
                try:
                    opis_id = int(row["OPIS Truckstop ID"])
                    row["price"] = Decimal(row["Retail Price"].strip())
                except (ValueError, InvalidOperation):
                    skipped += 1
                    continue

                current = cheapest.get(opis_id)
                if current is None or row["price"] < current["price"]:
                    cheapest[opis_id] = row
        return cheapest, skipped
