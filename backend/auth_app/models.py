"""Auth app models — moved from core.models (Phase 3 migration).

User, Session, AuthToken are the core auth models.
UserConfig is the legacy single-user config table.
HistoricalSnapshot stores canonical per-user per-date per-currency history.
DailySnapshot remains as a compatibility projection for legacy EGP-centric reads.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class User(models.Model):
    """The users table — magic link auth, no password."""

    LANGUAGE_CHOICES = [("en", "English"), ("ar", "Arabic")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    email = models.CharField(max_length=255, unique=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en")
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
    created_at = models.DateTimeField(
        auto_now_add=True, null=True, blank=True, db_default=Now()
    )
    updated_at = models.DateTimeField(
        auto_now=True, null=True, blank=True, db_default=Now()
    )

    class Meta:
        db_table = "user_config"


class Currency(models.Model):
    """Supported currency registry used by forms and display preferences.

    `name` is a JSONField holding bilingual values: `{"en": ..., "ar": ...}`.
    Use `get_display_name(lang)` for resolved per-locale strings.
    """

    code = models.CharField(max_length=3, primary_key=True)
    name = models.JSONField(default=dict)
    symbol = models.CharField(max_length=8, blank=True, default="")
    is_enabled = models.BooleanField(default=True, db_default=True)
    display_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "currencies"
        ordering = ["display_order", "code"]

    def get_display_name(self, lang: str | None = None) -> str:
        """Return name for the requested language. Falls back to en, then code."""
        from django.utils.translation import get_language

        if not isinstance(self.name, dict):
            return str(self.name) if self.name else self.code
        lang = lang or get_language() or "en"
        lang_code = lang.split("-")[0]
        if lang_code in self.name and self.name[lang_code]:
            return str(self.name[lang_code])
        if "en" in self.name and self.name["en"]:
            return str(self.name["en"])
        if self.name:
            for v in self.name.values():
                if v:
                    return str(v)
        return self.code

    def __str__(self) -> str:
        return self.code


class UserCurrencyPreference(models.Model):
    """Per-user active currencies and selected display currency."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        primary_key=True,
        related_name="currency_preferences",
    )
    active_currency_codes = models.JSONField(default=list, db_default="[]")
    selected_display_currency = models.CharField(
        max_length=3,
        default="EGP",
        db_default="EGP",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "user_currency_preferences"


class HistoricalSnapshot(models.Model):
    """Canonical per-currency daily financial state."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    date = models.DateField(db_index=True)
    currency = models.CharField(max_length=3, db_index=True)
    net_worth = models.DecimalField(max_digits=15, decimal_places=2, db_default=0)
    daily_spending = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    daily_income = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "historical_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "currency"],
                name="historical_snapshots_user_date_currency_unique",
            ),
        ]
