"""Fee Preset models — user-configurable fee templates."""

import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

GEN_UUID = Func(function="gen_random_uuid")

CALC_TYPE_FLAT = "flat"
CALC_TYPE_PERCENT = "percent"
CALC_TYPE_CHOICES = [
    (CALC_TYPE_FLAT, "Flat"),
    (CALC_TYPE_PERCENT, "Percent"),
]


class FeePreset(models.Model):
    """User-defined fee template (e.g., InstaPay percent, ATM flat).

    Scoped per (user, currency). For percent calc, value is a fraction
    (0.001 = 0.1%) optionally clamped by min_fee / max_fee.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    name = models.CharField(max_length=50)
    currency = models.CharField(max_length=3)
    calc_type = models.CharField(max_length=10, choices=CALC_TYPE_CHOICES)
    value = models.DecimalField(max_digits=15, decimal_places=4)
    min_fee = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    max_fee = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    archived = models.BooleanField(default=False, db_default=False)
    sort_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "fee_presets"
        unique_together = ("user", "name", "currency")

    def __str__(self) -> str:
        return f"{self.name} ({self.currency})"

    def compute(self, amount: Decimal | float | int) -> Decimal:
        """Return the fee for a given transaction amount, clamped if percent."""
        return compute_fee(self, amount)


def compute_fee(preset: FeePreset, amount: Decimal | float | int) -> Decimal:
    """Compute the fee for a transaction amount under a preset.

    - flat: returns ``preset.value`` (rounded to 2dp)
    - percent: returns ``amount * value``, clamped to [min_fee, max_fee]

    Negative amounts are treated as their absolute value.
    """
    amt = abs(Decimal(str(amount)))
    if preset.calc_type == CALC_TYPE_FLAT:
        return Decimal(preset.value).quantize(Decimal("0.01"))
    raw = (amt * Decimal(preset.value)).quantize(Decimal("0.01"))
    if preset.min_fee is not None and raw < preset.min_fee:
        raw = Decimal(preset.min_fee)
    if preset.max_fee is not None and raw > preset.max_fee:
        raw = Decimal(preset.max_fee)
    return raw
