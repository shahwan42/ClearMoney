"""Accounts models — moved from core.models (Phase 3 migration).

Institution is moved in batch 4. Account (depends on Institution) follows in batch 10.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Institution(models.Model):
    """Groups accounts under a bank/fintech/wallet (e.g., HSBC, Telda, Cash)."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey("core.User", on_delete=models.CASCADE, db_column="user_id")
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20, db_default="bank"
    )  # 'bank', 'fintech', 'wallet'
    color = models.CharField(max_length=20, null=True, blank=True)
    icon = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "institutions"

    def __str__(self) -> str:
        return self.name
