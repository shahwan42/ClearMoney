"""Budgets models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Budget(models.Model):
    """Monthly spending limit per category. is_active toggles without deleting."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        db_column="category_id",
        related_name="+",
    )
    monthly_limit = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, db_default="EGP")
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "budgets"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "currency"],
                name="budgets_user_category_currency_unique",
            ),
        ]


class TotalBudget(models.Model):
    """Overall monthly spending cap per currency. One per user per currency."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    monthly_limit = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, db_default="EGP")
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "total_budgets"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "currency"],
                name="uq_total_budget_user_currency",
            ),
        ]
