"""Categories models — moved from core.models (Phase 3 migration)."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Category(models.Model):
    """Expense or income category. is_system marks auto-seeded categories."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'expense' or 'income'
    icon = models.CharField(max_length=10, null=True, blank=True)
    is_system = models.BooleanField(default=False, db_default=False)
    is_archived = models.BooleanField(default=False, db_default=False)
    display_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "categories"

    def __str__(self) -> str:
        return self.name
