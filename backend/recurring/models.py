"""Recurring models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class RecurringRule(models.Model):
    """Schedules recurring transactions (salary, Netflix, etc.).

    template_transaction is a JSONB blob parsed into a TransactionTemplate on demand.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    template_transaction = models.JSONField()
    frequency = models.CharField(max_length=20)  # 'monthly' or 'weekly'
    day_of_month = models.IntegerField(null=True, blank=True)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True, db_default=True)
    auto_confirm = models.BooleanField(default=False, db_default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "recurring_rules"
