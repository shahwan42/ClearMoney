"""State-only migration: register Category in categories app.

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
    """Register Category in categories (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0008_delete_exchangeratelog"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Category",
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
                        ("name", models.CharField(max_length=100)),
                        ("type", models.CharField(max_length=20)),
                        (
                            "icon",
                            models.CharField(max_length=10, null=True, blank=True),
                        ),
                        (
                            "is_system",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "is_archived",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "display_order",
                            models.IntegerField(default=0, db_default=0),
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
                        "db_table": "categories",
                    },
                ),
            ],
        ),
    ]
