"""State-only migration: move DailySnapshot from jobs app to auth_app.

Uses SeparateDatabaseAndState with no database_operations — the table already
exists. This just tells Django's migration state that DailySnapshot lives in
auth_app, resolving import-linter contract violations (dashboard is an aggregator
and must not import from jobs, another aggregator).
"""

import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Move DailySnapshot state from jobs app to auth_app."""

    dependencies = [
        ("auth_app", "0002_state_only_user_session_authtoken"),
        ("jobs", "0002_retarget_user_fk"),
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
                                to="auth_app.user",
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
            ],
        ),
    ]
