"""Auth app models — moved from core.models (Phase 3 migration).

Note: User, Session, and AuthToken will be moved here in batch 13.
UserConfig is moved first as it has no dependencies on other models.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class UserConfig(models.Model):
    """Legacy single-user config table. Kept for backward compat (brute-force protection)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    pin_hash = models.TextField()
    session_key = models.TextField()
    failed_attempts = models.IntegerField(default=0, db_default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True, null=True, blank=True, db_default=Now()
    )
    updated_at = models.DateTimeField(
        auto_now=True, null=True, blank=True, db_default=Now()
    )

    class Meta:
        db_table = "user_config"
