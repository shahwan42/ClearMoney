"""Virtual accounts models — moved from core.models (Phase 3 migration).

VirtualAccount is moved in batch 8.
VirtualAccountAllocation (depends on Transaction) follows in batch 12.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class VirtualAccount(models.Model):
    """Envelope budgeting — earmarks money for goals without moving actual funds."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    icon = models.CharField(
        max_length=10, default="", null=True, blank=True, db_default=""
    )
    color = models.CharField(
        max_length=20, default="", null=True, blank=True, db_default="#0d9488"
    )
    is_archived = models.BooleanField(default=False, db_default=False)
    exclude_from_net_worth = models.BooleanField(default=False, db_default=False)
    display_order = models.IntegerField(default=0, db_default=0)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="account_id",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "virtual_accounts"

    def __str__(self) -> str:
        return self.name

    def progress_pct(self) -> float:
        """Percentage of target reached."""
        if not self.target_amount:
            return 0.0
        return float(self.current_balance) / float(self.target_amount) * 100
