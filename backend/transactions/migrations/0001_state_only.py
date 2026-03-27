"""State-only migration: register Transaction and VirtualAccountAllocation in transactions app.

Uses SeparateDatabaseAndState with no database_operations — the tables
already exist. This just tells Django's migration state that the models
live here now.
"""

import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models
from django.db.models import Func


class Migration(migrations.Migration):
    """Register Transaction and VirtualAccountAllocation in transactions (state only)."""

    initial = True

    dependencies = [
        ("accounts", "0002_state_only_account"),
        ("categories", "0001_state_only"),
        ("core", "0018_delete_dailysnapshot_accountsnapshot"),
        ("people", "0001_state_only"),
        ("recurring", "0001_state_only"),
        ("virtual_accounts", "0002_retarget_account_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Transaction",
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
                        ("type", models.CharField(max_length=30)),
                        (
                            "amount",
                            models.DecimalField(max_digits=15, decimal_places=2),
                        ),
                        ("currency", models.CharField(max_length=3)),
                        (
                            "account",
                            models.ForeignKey(
                                db_column="account_id",
                                db_index=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="transactions",
                                to="accounts.account",
                            ),
                        ),
                        (
                            "counter_account",
                            models.ForeignKey(
                                blank=True,
                                db_column="counter_account_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="accounts.account",
                            ),
                        ),
                        (
                            "category",
                            models.ForeignKey(
                                blank=True,
                                db_column="category_id",
                                db_index=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="categories.category",
                            ),
                        ),
                        (
                            "date",
                            models.DateField(
                                db_index=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                        ("time", models.TimeField(null=True, blank=True)),
                        ("note", models.TextField(null=True, blank=True)),
                        (
                            "tags",
                            django.contrib.postgres.fields.ArrayField(
                                base_field=models.CharField(max_length=100),
                                blank=True,
                                default=list,
                                size=None,
                            ),
                        ),
                        (
                            "exchange_rate",
                            models.DecimalField(
                                max_digits=10,
                                decimal_places=4,
                                null=True,
                                blank=True,
                            ),
                        ),
                        (
                            "counter_amount",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                null=True,
                                blank=True,
                            ),
                        ),
                        (
                            "fee_amount",
                            models.DecimalField(
                                max_digits=15,
                                decimal_places=2,
                                null=True,
                                blank=True,
                            ),
                        ),
                        (
                            "fee_account",
                            models.ForeignKey(
                                blank=True,
                                db_column="fee_account_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="accounts.account",
                            ),
                        ),
                        (
                            "person",
                            models.ForeignKey(
                                blank=True,
                                db_column="person_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="people.person",
                            ),
                        ),
                        (
                            "linked_transaction",
                            models.ForeignKey(
                                blank=True,
                                db_column="linked_transaction_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="transactions.transaction",
                            ),
                        ),
                        (
                            "recurring_rule",
                            models.ForeignKey(
                                blank=True,
                                db_column="recurring_rule_id",
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="recurring.recurringrule",
                            ),
                        ),
                        (
                            "balance_delta",
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
                        (
                            "updated_at",
                            models.DateTimeField(
                                auto_now=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "transactions",
                    },
                ),
                migrations.CreateModel(
                    name="VirtualAccountAllocation",
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
                            "transaction",
                            models.ForeignKey(
                                blank=True,
                                db_column="transaction_id",
                                null=True,
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="+",
                                to="transactions.transaction",
                            ),
                        ),
                        (
                            "virtual_account",
                            models.ForeignKey(
                                db_column="virtual_account_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="allocations",
                                to="virtual_accounts.virtualaccount",
                            ),
                        ),
                        (
                            "amount",
                            models.DecimalField(max_digits=15, decimal_places=2),
                        ),
                        ("note", models.TextField(null=True, blank=True)),
                        ("allocated_at", models.DateField(null=True, blank=True)),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_default=django.db.models.functions.datetime.Now(),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "virtual_account_allocations",
                    },
                ),
            ],
        ),
    ]
