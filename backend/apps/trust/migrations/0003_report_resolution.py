import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def resolve_existing_duplicates(apps, schema_editor):
    """Keep the oldest open report per (reporter, listing); close the rest as duplicates
    so the unique constraint in 0004 can be added to a database that already has some."""
    Report = apps.get_model("trust", "Report")
    seen = set()
    for report in Report.objects.filter(resolved_at__isnull=True, listing__isnull=False).order_by("id"):
        key = (report.reporter_id, report.listing_id)
        if key in seen:
            report.resolved_at = timezone.now()
            report.resolution = "duplicate"
            report.save(update_fields=["resolved_at", "resolution"])
        else:
            seen.add(key)


class Migration(migrations.Migration):
    dependencies = [
        ("trust", "0002_dispute_one_dispute_per_viewing"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="resolution",
            field=models.CharField(blank=True, choices=[("actioned", "Actioned"), ("dismissed", "Dismissed"), ("duplicate", "Duplicate")], max_length=10),
        ),
        migrations.AddField(
            model_name="report",
            name="resolved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reports_resolved", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(resolve_existing_duplicates, migrations.RunPython.noop),
    ]
