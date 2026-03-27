# Generated migration — ExchangeRateLog moved to exchange_rates.models

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_add_system_categories"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name="ExchangeRateLog",
                ),
            ],
            database_operations=[],
        ),
    ]
