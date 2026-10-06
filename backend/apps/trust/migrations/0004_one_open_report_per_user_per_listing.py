from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trust", "0003_report_resolution")]

    operations = [
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(condition=models.Q(("resolved_at__isnull", True)), fields=("reporter", "listing"), name="one_open_report_per_user_per_listing"),
        ),
    ]
