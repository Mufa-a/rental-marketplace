from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("properties", "0005_unit_availability_confirmed_at")]

    operations = [
        migrations.AddField(
            model_name="unit",
            name="moderation_hold",
            field=models.BooleanField(default=False),
        ),
    ]
