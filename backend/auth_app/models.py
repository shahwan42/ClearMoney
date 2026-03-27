"""Auth app models — moved from core.models (Phase 3 migration).

User, Session, AuthToken are the core auth models.
UserConfig is the legacy single-user config table.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class User(models.Model):
    """The users table — magic link auth, no password."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    email = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email


class Session(models.Model):
    """Server-side sessions — validated by GoSessionAuthMiddleware."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "sessions"


class AuthToken(models.Model):
    """Short-lived, single-use magic link tokens. Like Laravel's password_resets table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    email = models.CharField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    purpose = models.CharField(
        max_length=20, default="login", db_default="login"
    )  # 'login' or 'registration'
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False, db_default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "auth_tokens"


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
