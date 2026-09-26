from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("payments", "0001_initial"),
        ("viewings", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment", name="fee",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="referrals.referralfee"),
        ),
        migrations.AddField(
            model_name="payment", name="purpose",
            field=models.CharField(choices=[("referral_fee", "Landlord referral fee"), ("viewing_credits", "Tenant viewing credits")], default="referral_fee", max_length=20),
        ),
        migrations.AddField(
            model_name="payment", name="tenant_user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="viewing_credit_payments", to="accounts.user"),
        ),
        migrations.AddField(
            model_name="payment", name="credits",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ViewingCreditPurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credits_total", models.PositiveSmallIntegerField()),
                ("credits_remaining", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payment", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="credit_purchase", to="payments.payment")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="credit_purchases", to="accounts.tenantprofile")),
            ],
        ),
        migrations.CreateModel(
            name="ViewingCreditUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("reserved", "Reserved"), ("consumed", "Consumed"), ("restored", "Restored")], default="reserved", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("purchase", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="uses", to="payments.viewingcreditpurchase")),
                ("viewing_request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="credit_use", to="viewings.viewingrequest")),
            ],
        ),
    ]
