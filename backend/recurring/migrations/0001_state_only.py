"""State-only migration: register RecurringRule in recurring app.

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
    """Register RecurringRule in recurring (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0015_delete_virtualaccount"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="RecurringRule",
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
                        ("template_transaction", models.JSONField()),
                        ("frequency", models.CharField(max_length=20)),
                        ("day_of_month", models.IntegerField(null=True, blank=True)),
                        ("next_due_date", models.DateField()),
                        (
                            "is_active",
                            models.BooleanField(default=True, db_default=True),
                        ),
                        (
                            "auto_confirm",
                            models.BooleanField(default=False, db_default=False),
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
                        "db_table": "recurring_rules",
                    },
                ),
            ],
        ),
    ]
