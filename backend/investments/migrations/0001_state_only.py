"""State-only migration: register Investment in investments app.

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
    """Register Investment in investments (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0011_delete_institution"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Investment",
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
                        (
                            "user",
                            models.ForeignKey(
                                db_column="user_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                to="core.user",
                            ),
                        ),
                        (
                            "platform",
                            models.CharField(max_length=100, db_default="Thndr"),
                        ),
                        ("fund_name", models.CharField(max_length=100)),
                        (
                            "units",
                            models.DecimalField(
                                max_digits=15, decimal_places=4, db_default=0
                            ),
                        ),
                        (
                            "last_unit_price",
                            models.DecimalField(
                                max_digits=15, decimal_places=4, db_default=0
                            ),
                        ),
                        (
                            "currency",
                            models.CharField(max_length=3, db_default="EGP"),
                        ),
                        (
                            "last_updated",
                            models.DateTimeField(
                                db_default=django.db.models.functions.datetime.Now()
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                        (
                            "updated_at",
                            models.DateTimeField(
                                auto_now=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "investments",
                    },
                ),
            ],
        ),
    ]
