from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_alter_dailysnapshot_date_alter_transaction_date"),
    ]

    operations = [
        migrations.DeleteModel(
            name="InstallmentPlan",
        ),
    ]
