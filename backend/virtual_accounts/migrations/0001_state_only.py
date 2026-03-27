"""State-only migration: register VirtualAccount in virtual_accounts app.

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
    """Register VirtualAccount in virtual_accounts (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("core", "0014_delete_person"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="VirtualAccount",
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
                        (
                            "target_amount",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                null=True,
                                blank=True,
                            ),
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
                            "icon",
                            models.CharField(
                                max_length=10,
                                default="",
                                null=True,
                                blank=True,
                                db_default="",
                            ),
                        ),
                        (
                            "color",
                            models.CharField(
                                max_length=20,
                                default="",
                                null=True,
                                blank=True,
                                db_default="#0d9488",
                            ),
                        ),
                        (
                            "is_archived",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "exclude_from_net_worth",
                            models.BooleanField(default=False, db_default=False),
                        ),
                        (
                            "display_order",
                            models.IntegerField(default=0, db_default=0),
                        ),
                        (
                            "account",
                            models.ForeignKey(
                                blank=True,
                                db_column="account_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="core.account",
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
                        "db_table": "virtual_accounts",
                    },
                ),
            ],
        ),
    ]
