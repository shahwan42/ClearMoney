"""State-only migration: register UserConfig in auth_app.

Uses SeparateDatabaseAndState with no database_operations — the table
already exists. This just tells Django's migration state that the model
lives here now.
"""

import uuid

import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register UserConfig in auth_app (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0009_delete_category"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="UserConfig",
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
                        ("pin_hash", models.TextField()),
                        ("session_key", models.TextField()),
                        (
                            "failed_attempts",
                            models.IntegerField(default=0, db_default=0),
                        ),
                        (
                            "locked_until",
                            models.DateTimeField(null=True, blank=True),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                null=True,
                                blank=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                        (
                            "updated_at",
                            models.DateTimeField(
                                auto_now=True,
                                null=True,
                                blank=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "user_config",
                    },
                ),
            ],
        ),
    ]
