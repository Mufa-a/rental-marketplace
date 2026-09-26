from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
 initial=True
 dependencies=[("referrals","0001_initial")]
 operations=[migrations.CreateModel(name="Payment",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("amount",models.PositiveIntegerField()),("phone_number",models.CharField(max_length=20)),("provider_reference",models.CharField(max_length=100,unique=True)),("status",models.CharField(choices=[("pending","Pending"),("successful","Successful"),("failed","Failed"),("refunded","Refunded"),("disputed","Disputed")],default="pending",max_length=12)),("idempotency_key",models.CharField(max_length=100,unique=True)),("provider_payload",models.JSONField(blank=True,default=dict)),("created_at",models.DateTimeField(auto_now_add=True)),("updated_at",models.DateTimeField(auto_now=True)),("fee",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="payments",to="referrals.referralfee"))])]
