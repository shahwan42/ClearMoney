"""State-only migration: register DailySnapshot and AccountSnapshot in jobs app.

Uses SeparateDatabaseAndState with no database_operations — the tables
already exist. This just tells Django's migration state that the models
live here now.
"""

import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register DailySnapshot and AccountSnapshot in jobs (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("accounts", "0002_state_only_account"),
        ("core", "0017_delete_account"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="DailySnapshot",
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
                        ("date", models.DateField(db_index=True)),
                        (
                            "net_worth_egp",
                            models.DecimalField(
                                max_digits=15, decimal_places=2, db_default=0
                            ),
                        ),
                        (
                            "net_worth_raw",
                            models.DecimalField(
                                max_digits=15, decimal_places=2, db_default=0
                            ),
                        ),
                        (
                            "exchange_rate",
                            models.DecimalField(
                                max_digits=10, decimal_places=4, db_default=0
                            ),
                        ),
                        (
                            "daily_spending",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                default=0,
                                db_default=0,
                            ),
                        ),
                        (
                            "daily_income",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                default=0,
                                db_default=0,
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "daily_snapshots",
                    },
                ),
                migrations.AddConstraint(
                    model_name="dailysnapshot",
                    constraint=models.UniqueConstraint(
                        fields=["user", "date"],
                        name="daily_snapshots_user_date_unique",
                    ),
                ),
                migrations.CreateModel(
                    name="AccountSnapshot",
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
                        ("date", models.DateField()),
                        (
                            "account",
                            models.ForeignKey(
                                db_column="account_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="+",
                                to="accounts.account",
                            ),
                        ),
                        (
                            "balance",
                            models.DecimalField(
                                max_digits=15, decimal_places=2, db_default=0
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "account_snapshots",
                    },
                ),
                migrations.AddConstraint(
                    model_name="accountsnapshot",
                    constraint=models.UniqueConstraint(
                        fields=["user", "date", "account"],
                        name="account_snapshots_user_date_account_unique",
                    ),
                ),
            ],
        ),
    ]
