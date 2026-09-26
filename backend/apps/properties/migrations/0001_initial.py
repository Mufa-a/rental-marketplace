# Generated for Phase 3 listings.
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Amenity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=90, unique=True)),
                ("icon", models.CharField(blank=True, max_length=50)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Property",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("address_line", models.CharField(max_length=255)),
                ("area", models.CharField(max_length=100)),
                ("city", models.CharField(max_length=100)),
                ("county", models.CharField(max_length=100)),
                ("country", models.CharField(default="KE", max_length=2)),
                ("verification_status", models.CharField(choices=[("unverified", "Unverified"), ("pending", "Verification pending"), ("verified", "Verified"), ("rejected", "Rejected")], default="unverified", max_length=12)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("landlord", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="properties", to="accounts.landlordprofile")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="Unit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unit_number", models.CharField(max_length=50)),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("unit_type", models.CharField(choices=[("bedsitter", "Bedsitter"), ("studio", "Studio"), ("apartment", "Apartment"), ("house", "House"), ("maisonette", "Maisonette"), ("room", "Room")], max_length=15)),
                ("monthly_rent", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("security_deposit", models.PositiveIntegerField(default=0)),
                ("bedrooms", models.PositiveSmallIntegerField(default=0)),
                ("bathrooms", models.DecimalField(decimal_places=1, default=1, max_digits=3)),
                ("floor_area_sqm", models.PositiveIntegerField(blank=True, null=True)),
                ("furnishing", models.CharField(choices=[("unfurnished", "Unfurnished"), ("semi_furnished", "Semi-furnished"), ("furnished", "Furnished")], default="unfurnished", max_length=16)),
                ("available", models.BooleanField(default=True)),
                ("available_from", models.DateField(blank=True, null=True)),
                ("is_published", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amenities", models.ManyToManyField(blank=True, related_name="units", to="properties.amenity")),
                ("property", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="units", to="properties.property")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="PropertyMedia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_key", models.CharField(max_length=500, unique=True)),
                ("media_type", models.CharField(choices=[("exterior", "Exterior"), ("living_room", "Living room"), ("bedroom", "Bedroom"), ("kitchen", "Kitchen"), ("bathroom", "Bathroom"), ("other", "Other")], default="other", max_length=20)),
                ("alt_text", models.CharField(blank=True, max_length=180)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="media", to="properties.unit")),
            ],
            options={"ordering": ("sort_order", "created_at")},
        ),
        migrations.AddIndex(model_name="property", index=models.Index(fields=["city", "area", "is_active"], name="properties__city_26452e_idx")),
        migrations.AddIndex(model_name="unit", index=models.Index(fields=["available", "is_published"], name="properties__availab_9610c6_idx")),
        migrations.AddIndex(model_name="unit", index=models.Index(fields=["monthly_rent", "bedrooms"], name="properties__monthly_66e9ee_idx")),
        migrations.AddConstraint(model_name="unit", constraint=models.UniqueConstraint(fields=("property", "unit_number"), name="unique_unit_number_per_property")),
    ]
