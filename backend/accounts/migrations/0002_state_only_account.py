"""State-only migration: register Account in accounts app.

Uses SeparateDatabaseAndState with no database_operations — the table
already exists. This just tells Django's migration state that the model
lives here now.
"""

import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register Account in accounts (state only, no DB ops)."""

    dependencies = [
        ("accounts", "0001_state_only"),
        ("core", "0016_delete_recurringrule"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Account",
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
                                db_index=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                to="core.user",
                            ),
                        ),
                        (
                            "institution",
                            models.ForeignKey(
                                db_column="institution_id",
                                db_index=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="accounts",
                                to="accounts.institution",
                            ),
                        ),
                        ("name", models.CharField(max_length=100)),
                        ("type", models.CharField(max_length=20)),
                        (
                            "currency",
                            models.CharField(max_length=3, db_default="EGP"),
                        ),
                        (
                            "current_balance",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                default=0,
                                db_default=0,
                            ),
                        ),
                        (
                            "initial_balance",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                default=0,
                                db_default=0,
                            ),
                        ),
                        (
                            "credit_limit",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                null=True,
                                blank=True,
                            ),
                        ),
                        (
                            "is_dormant",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "role_tags",
                            django.contrib.postgres.fields.ArrayField(
                                base_field=models.CharField(max_length=100),
                                blank=True,
                                default=list,
                                null=True,
                                size=None,
                            ),
                        ),
                        (
                            "display_order",
                            models.IntegerField(default=0, db_default=0),
                        ),
                        ("metadata", models.JSONField(null=True, blank=True)),
                        ("health_config", models.JSONField(null=True, blank=True)),
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
                        "db_table": "accounts",
                    },
                ),
            ],
        ),
    ]
