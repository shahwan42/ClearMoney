"""Investments models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Investment(models.Model):
    """Fund holding on a platform like Thndr. Value = units * last_unit_price."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    platform = models.CharField(max_length=100, db_default="Thndr")
    fund_name = models.CharField(max_length=100)
    units = models.DecimalField(max_digits=15, decimal_places=4, db_default=0)
    last_unit_price = models.DecimalField(max_digits=15, decimal_places=4, db_default=0)
    currency = models.CharField(max_length=3, db_default="EGP")
    last_updated = models.DateTimeField(db_default=Now())
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "investments"

    def __str__(self) -> str:
        return f"{self.platform} — {self.fund_name}"
