"""Development only: create demo landlords, tenants and listings across Kenya.

    python manage.py seed_demo

Refuses to run unless DEBUG=True. Phone numbers use the reserved +2547000xxxxx range.
"""
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import LandlordProfile, TenantProfile, User
from apps.properties.fields import GeographicPoint
from apps.properties.models import Amenity, Property, Unit

AMENITIES = ["Borehole water", "Backup generator", "Parking", "Wi-Fi ready", "CCTV", "Lift", "Gym", "Swimming pool",
             "Balcony", "Garden", "Pet friendly", "Servant quarter", "Gated community", "Prepaid electricity"]

PLACES = [  # county, town, estate, lat, lng, rent band
    ("Nairobi", "Nairobi", "Kilimani", -1.2901, 36.7834, (25000, 85000)),
    ("Nairobi", "Nairobi", "Westlands", -1.2676, 36.8108, (30000, 120000)),
    ("Nairobi", "Nairobi", "Kileleshwa", -1.2797, 36.7845, (28000, 90000)),
    ("Nairobi", "Nairobi", "Kasarani", -1.2210, 36.8977, (8000, 30000)),
    ("Nairobi", "Nairobi", "South B", -1.3101, 36.8392, (12000, 40000)),
    ("Kiambu", "Ruaka", "Ruaka", -1.2063, 36.7790, (10000, 45000)),
    ("Kiambu", "Thika", "Section 9", -1.0396, 37.0834, (6000, 25000)),
    ("Machakos", "Syokimau", "Syokimau", -1.3627, 36.9420, (12000, 45000)),
    ("Mombasa", "Mombasa", "Nyali", -4.0435, 39.7069, (20000, 95000)),
    ("Mombasa", "Mombasa", "Bamburi", -3.9800, 39.7240, (9000, 35000)),
    ("Kisumu", "Kisumu", "Milimani", -0.0975, 34.7617, (15000, 60000)),
    ("Nakuru", "Nakuru", "Milimani", -0.2833, 36.0667, (10000, 45000)),
    ("Uasin Gishu", "Eldoret", "Elgon View", 0.5143, 35.2698, (12000, 50000)),
]

LAYOUTS = [  # unit_type, bedrooms, bathrooms, title
    ("bedsitter", 0, 1, "Bright bedsitter"), ("studio", 0, 1, "Modern studio"), ("apartment", 1, 1, "One bedroom apartment"),
    ("apartment", 2, 2, "Two bedroom apartment, master en-suite"), ("apartment", 3, 2, "Three bedroom family apartment"),
    ("maisonette", 3, 3, "Three bedroom maisonette"), ("house", 4, 3, "Four bedroom house with garden"),
]


class Command(BaseCommand):
    help = "Development only: seed demo listings, landlords and tenants."

    def add_arguments(self, parser):
        parser.add_argument("--listings", type=int, default=60)

    @transaction.atomic
    def handle(self, *args, listings=60, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG=True.")
        rng = random.Random(42)
        amenities = [Amenity.objects.get_or_create(name=name)[0] for name in AMENITIES]
        landlords = []
        for n in range(8):
            user, _ = User.objects.get_or_create(phone_number=f"+254700000{100 + n}", defaults={
                "username": f"+254700000{100 + n}", "role": User.Role.LANDLORD, "phone_verified": True, "is_active": True,
                "first_name": ["Wanjiru", "Otieno", "Achieng", "Kamau", "Mwangi", "Njeri", "Kiptoo", "Amina"][n]})
            landlords.append(LandlordProfile.objects.get_or_create(user=user, defaults={"verification_tier": "standard" if n % 3 == 0 else "basic"})[0])
        for n in range(3):
            user, _ = User.objects.get_or_create(phone_number=f"+254700000{200 + n}", defaults={
                "username": f"+254700000{200 + n}", "role": User.Role.TENANT, "phone_verified": True, "is_active": True})
            TenantProfile.objects.get_or_create(user=user)
        created = 0
        for index in range(listings):
            county, town, estate, lat, lng, (low, high) = PLACES[index % len(PLACES)]
            landlord = landlords[index % len(landlords)]
            prop, _ = Property.objects.get_or_create(
                landlord=landlord, name=f"{estate} {['Court', 'Heights', 'Gardens', 'Residences', 'Place'][index % 5]}",
                defaults={"address_line": f"{rng.randint(1, 120)} {estate} Road", "area": estate, "city": town, "county": county,
                          "location": GeographicPoint(lng + rng.uniform(-0.01, 0.01), lat + rng.uniform(-0.01, 0.01)),
                          "verification_status": "verified" if index % 4 == 0 else "unverified",
                          "description": f"Well-kept building in {estate}, close to shops and public transport."})
            unit_type, bedrooms, bathrooms, title = LAYOUTS[index % len(LAYOUTS)]
            rent = round(rng.randint(low, high) / 500) * 500
            unit, was_created = Unit.objects.get_or_create(property=prop, unit_number=f"{chr(65 + index % 6)}{index}", defaults={
                "title": f"{title} in {estate}", "unit_type": unit_type, "bedrooms": bedrooms, "bathrooms": bathrooms,
                "monthly_rent": rent, "security_deposit": rent, "furnishing": rng.choice(["unfurnished", "unfurnished", "semi_furnished", "furnished"]),
                "floor_area_sqm": 25 + bedrooms * 30, "is_published": True,
                "description": f"{title} with good natural light, tiled floors and a fitted kitchen. Water and security on site. "
                               f"About 10 minutes from {town} town centre."})
            if was_created:
                unit.amenities.set(rng.sample(amenities, rng.randint(3, 7)))
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} listings. Landlords sign in as +254700000100…107, tenants +254700000200…202 (OTP prints to the console)."))
