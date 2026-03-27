# Generated migration — ExchangeRateLog moved from core to exchange_rates

import uuid

from django.db import migrations, models
from django.db.models import Func
from django.db.models.functions import Now

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="ExchangeRateLog",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                db_default=GEN_UUID,
                                default=uuid.uuid4,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("date", models.DateField()),
                        (
                            "rate",
                            models.DecimalField(decimal_places=4, max_digits=10),
                        ),
                        (
                            "source",
                            models.CharField(blank=True, max_length=50, null=True),
                        ),
                        (
                            "note",
                            models.TextField(blank=True, null=True),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(auto_now_add=True, db_default=Now()),
                        ),
                    ],
                    options={
                        "db_table": "exchange_rate_log",
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
