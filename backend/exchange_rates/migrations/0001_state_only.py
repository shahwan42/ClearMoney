"""State-only migration: register ExchangeRateLog in exchange_rates app.

Uses SeparateDatabaseAndState with no database_operations — the table
already exists. This just tells Django's migration state that the model
lives here now.
"""

import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register ExchangeRateLog in exchange_rates (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0007_add_system_categories"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="ExchangeRateLog",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                primary_key=True,
                                default=uuid.uuid4,
                                db_default=Func(function="gen_random_uuid"),
                                serialize=False,
                            ),
                        ),
                        ("date", models.DateField()),
                        (
                            "rate",
                            models.DecimalField(max_digits=10, decimal_places=4),
                        ),
                        (
                            "source",
                            models.CharField(max_length=50, null=True, blank=True),
                        ),
                        ("note", models.TextField(null=True, blank=True)),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "exchange_rate_log",
                    },
                ),
            ],
        ),
    ]
