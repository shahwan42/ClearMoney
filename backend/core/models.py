"""
Core models — Django representations of the ClearMoney PostgreSQL schema.

All models map to existing tables. Django manages migrations natively.

Like Laravel's Eloquent models with $table, or Django's standard models
with explicit db_table to match the existing schema naming convention.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

# ---------------------------------------------------------------------------
# Early imports of models that have been moved to their own apps but are
# still referenced inline (as Python classes) by models defined below.
# These must come BEFORE those models are defined.
# ---------------------------------------------------------------------------
from categories.models import (
    Category as Category,  # noqa: F401 — used in Transaction/Budget FKs + re-export
)

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


# ---------------------------------------------------------------------------
# Re-export shims — models moved to their own apps (Phase 3 migration).
# Import sites continue to work unchanged via `from core.models import X`.
# ---------------------------------------------------------------------------

from accounts.models import Account as Account  # noqa: E402
from accounts.models import Institution as Institution  # noqa: E402
from auth_app.models import UserConfig as UserConfig  # noqa: E402
from budgets.models import Budget as Budget  # noqa: E402
from budgets.models import TotalBudget as TotalBudget  # noqa: E402
from exchange_rates.models import ExchangeRateLog as ExchangeRateLog  # noqa: E402
from investments.models import Investment as Investment  # noqa: E402
from jobs.models import AccountSnapshot as AccountSnapshot  # noqa: E402
from jobs.models import DailySnapshot as DailySnapshot  # noqa: E402
from people.models import Person as Person  # noqa: E402
from recurring.models import RecurringRule as RecurringRule  # noqa: E402
from transactions.models import Transaction as Transaction  # noqa: E402
from transactions.models import (  # noqa: E402
    VirtualAccountAllocation as VirtualAccountAllocation,
)
from virtual_accounts.models import VirtualAccount as VirtualAccount  # noqa: E402
