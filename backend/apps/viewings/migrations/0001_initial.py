from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0001_initial"), ("properties", "0001_initial"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="ViewingRequest", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("preferred_times", models.JSONField(blank=True, default=list)), ("note", models.CharField(blank=True, max_length=500)),
            ("status", models.CharField(choices=[("pending_landlord", "Pending landlord"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="pending_landlord", max_length=20)),
            ("landlord_note", models.CharField(blank=True, max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="viewing_requests", to="accounts.tenantprofile")), ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viewing_requests", to="properties.unit")),
        ], options={"ordering": ("-created_at",)}),
        migrations.CreateModel(name="Viewing", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("scheduled_at", models.DateTimeField()),
            ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("completed", "Completed"), ("outcome_pending", "Outcome pending"), ("rented", "Rented"), ("did_not_rent", "Did not rent"), ("still_deciding", "Still deciding"), ("disputed", "Disputed"), ("rescheduled", "Rescheduled"), ("no_show", "No show")], default="scheduled", max_length=20)),
            ("meeting_note", models.CharField(blank=True, max_length=500)), ("completed_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="viewing", to="viewings.viewingrequest")),
        ]),
        migrations.CreateModel(name="Outcome", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("choice", models.CharField(choices=[("rented", "Rented"), ("did_not_rent", "Did not rent"), ("still_deciding", "Still deciding"), ("no_show", "No show"), ("disputed", "Disputed")], max_length=20)), ("note", models.CharField(blank=True, max_length=500)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="viewing_outcomes", to=settings.AUTH_USER_MODEL)), ("viewing", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outcomes", to="viewings.viewing")),
        ]),
        migrations.AddIndex(model_name="viewingrequest", index=models.Index(fields=["tenant", "status"], name="viewings_vi_tenant__d5ce61_idx")),
        migrations.AddIndex(model_name="viewingrequest", index=models.Index(fields=["unit", "status"], name="viewings_vi_unit_id_08380c_idx")),
        migrations.AddConstraint(model_name="outcome", constraint=models.UniqueConstraint(fields=("viewing", "reporter"), name="one_outcome_per_reporter")),
    ]
