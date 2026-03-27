"""State-only migration: register Budget and TotalBudget in budgets app.

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
    """Register Budget and TotalBudget in budgets (state only, no DB ops)."""

    initial = True

    dependencies = [
        ("categories", "0001_state_only"),
        ("core", "0012_delete_investment"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Budget",
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
                            "category",
                            models.ForeignKey(
                                db_column="category_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="+",
                                to="categories.category",
                            ),
                        ),
                        (
                            "monthly_limit",
                            models.DecimalField(max_digits=15, decimal_places=2),
                        ),
                        (
                            "currency",
                            models.CharField(max_length=3, db_default="EGP"),
                        ),
                        (
                            "is_active",
                            models.BooleanField(default=True, db_default=True),
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
                        "db_table": "budgets",
                    },
                ),
                migrations.AddConstraint(
                    model_name="budget",
                    constraint=models.UniqueConstraint(
                        fields=["user", "category", "currency"],
                        name="budgets_user_category_currency_unique",
                    ),
                ),
                migrations.CreateModel(
                    name="TotalBudget",
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
                            "monthly_limit",
                            models.DecimalField(max_digits=15, decimal_places=2),
                        ),
                        (
                            "currency",
                            models.CharField(max_length=3, db_default="EGP"),
                        ),
                        (
                            "is_active",
                            models.BooleanField(default=True, db_default=True),
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
                        "db_table": "total_budgets",
                    },
                ),
                migrations.AddConstraint(
                    model_name="totalbudget",
                    constraint=models.UniqueConstraint(
                        fields=["user", "currency"],
                        name="uq_total_budget_user_currency",
                    ),
                ),
            ],
        ),
    ]
