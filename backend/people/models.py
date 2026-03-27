"""People models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Person(models.Model):
    """Tracks someone you lend money to or borrow from.

    net_balance_egp / net_balance_usd are cached running totals (denormalized).
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    name = models.CharField(max_length=100)
    note = models.TextField(null=True, blank=True)
    net_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )  # legacy
    net_balance_egp = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    net_balance_usd = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "persons"

    def __str__(self) -> str:
        return self.name
