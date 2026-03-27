"""State-only migration: move AccountSnapshot from jobs app to accounts app.

Uses SeparateDatabaseAndState with no database_operations — the table already
exists. This just tells Django's migration state that AccountSnapshot lives in
the accounts app, resolving import-linter contract violations (accounts is a
leaf module and must not import from jobs, an aggregator).
"""

import uuid

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Move AccountSnapshot state from jobs app to accounts app."""

    dependencies = [
        ("accounts", "0003_retarget_user_fk"),
        ("jobs", "0002_retarget_user_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
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
                                to="auth_app.user",
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
