"""Jobs models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class DailySnapshot(models.Model):
    """Append-only daily financial state. Used for sparklines and MoM comparisons."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    date = models.DateField(db_index=True)
    net_worth_egp = models.DecimalField(max_digits=15, decimal_places=2, db_default=0)
    net_worth_raw = models.DecimalField(max_digits=15, decimal_places=2, db_default=0)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, db_default=0)
    daily_spending = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    daily_income = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "daily_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="daily_snapshots_user_date_unique",
            ),
        ]


class AccountSnapshot(models.Model):
    """Per-account daily balance. Append-only — one row per (user, date, account)."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey("core.User", on_delete=models.CASCADE, db_column="user_id")
    date = models.DateField()
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        db_column="account_id",
        related_name="+",
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "account_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "account"],
                name="account_snapshots_user_date_account_unique",
            ),
        ]
