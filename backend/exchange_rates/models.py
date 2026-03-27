"""Exchange rates models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class ExchangeRateLog(models.Model):
    """Append-only daily USD/EGP rate history. No user — global data.

    Rate = EGP per 1 USD (e.g., 50.5 means 1 USD = 50.5 EGP).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    date = models.DateField()
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    source = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "exchange_rate_log"
