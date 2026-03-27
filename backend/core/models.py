"""
Core models — Django representations of the ClearMoney PostgreSQL schema.

All models map to existing tables. Django manages migrations natively.

Like Laravel's Eloquent models with $table, or Django's standard models
with explicit db_table to match the existing schema naming convention.
"""

import uuid

from django.contrib.postgres.fields import ArrayField
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
from core.managers import UserScopedManager

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


class Transaction(models.Model):
    """Central record for every money movement.

    Amount is ALWAYS positive; balance_delta holds the signed impact on the account balance.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    type = models.CharField(
        max_length=30
    )  # expense/income/transfer/exchange/loan_out/loan_in/loan_repayment
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # always positive
    currency = models.CharField(max_length=3)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        db_column="account_id",
        db_index=True,
        related_name="transactions",
    )
    counter_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="counter_account_id",
        related_name="+",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="category_id",
        db_index=True,
        related_name="+",
    )
    date = models.DateField(db_index=True, db_default=Now())
    time = models.TimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    exchange_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    counter_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    fee_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    fee_account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="fee_account_id",
        related_name="+",
    )
    person = models.ForeignKey(
        "people.Person",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="person_id",
        related_name="+",
    )
    linked_transaction = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="linked_transaction_id",
        related_name="+",
    )
    recurring_rule = models.ForeignKey(
        "recurring.RecurringRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="recurring_rule_id",
        related_name="+",
    )
    balance_delta = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "transactions"


class VirtualAccountAllocation(models.Model):
    """Pivot table linking transactions to virtual accounts.

    transaction is nullable for direct (non-transaction) allocations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column="transaction_id",
        related_name="+",
    )
    virtual_account = models.ForeignKey(
        "virtual_accounts.VirtualAccount",
        on_delete=models.CASCADE,
        db_column="virtual_account_id",
        related_name="allocations",
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2
    )  # positive=contribution, negative=withdrawal
    note = models.TextField(null=True, blank=True)
    allocated_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "virtual_account_allocations"


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
from virtual_accounts.models import VirtualAccount as VirtualAccount  # noqa: E402
