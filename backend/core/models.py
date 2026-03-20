"""
Core models — Django representations of the ClearMoney PostgreSQL schema.

All models map to existing tables. Django manages migrations natively.

Like Laravel's Eloquent models with $table, or Django's standard models
with explicit db_table to match the existing schema naming convention.
"""

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(models.Model):
    """The users table — magic link auth, no password."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"

    def __str__(self) -> str:
        return self.email


class Session(models.Model):
    """Server-side sessions — validated by GoSessionAuthMiddleware."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sessions"


class AuthToken(models.Model):
    """Short-lived, single-use magic link tokens. Like Laravel's password_resets table."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    purpose = models.CharField(max_length=20, default="login")  # 'login' or 'registration'
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_tokens"


class UserConfig(models.Model):
    """Legacy single-user config table. Kept for backward compat (brute-force protection)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    pin_hash = models.TextField()
    session_key = models.TextField()
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_config"


class Institution(models.Model):
    """Groups accounts under a bank/fintech/wallet (e.g., HSBC, Telda, Cash)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20)  # 'bank', 'fintech', 'wallet'
    color = models.CharField(max_length=20, null=True, blank=True)
    icon = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "institutions"

    def __str__(self) -> str:
        return self.name


class Account(models.Model):
    """One financial account (bank account, credit card, cash wallet).

    current_balance is cached and updated atomically on every transaction.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, db_column="institution_id", related_name="accounts"
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit', 'cash'
    currency = models.CharField(max_length=3)  # 'EGP' or 'USD'
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_dormant = models.BooleanField(default=False)
    role_tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    display_order = models.IntegerField(default=0)
    metadata = models.JSONField(null=True, blank=True)       # JSONB: billing cycle, etc.
    health_config = models.JSONField(null=True, blank=True)  # JSONB: min_balance, min_monthly_deposit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"

    def __str__(self) -> str:
        return self.name

    def is_credit_type(self) -> bool:
        """True for credit cards and credit limits."""
        return self.type in ("credit_card", "credit_limit")


class Category(models.Model):
    """Expense or income category. is_system marks auto-seeded categories."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'expense' or 'income'
    icon = models.CharField(max_length=10, null=True, blank=True)
    is_system = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"

    def __str__(self) -> str:
        return self.name


class Person(models.Model):
    """Tracks someone you lend money to or borrow from.

    net_balance_egp / net_balance_usd are cached running totals (denormalized).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    name = models.CharField(max_length=100)
    note = models.TextField(null=True, blank=True)
    net_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)      # legacy
    net_balance_egp = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_balance_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "persons"

    def __str__(self) -> str:
        return self.name


class RecurringRule(models.Model):
    """Schedules recurring transactions (salary, Netflix, etc.).

    template_transaction is a JSONB blob parsed into a TransactionTemplate on demand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    template_transaction = models.JSONField()
    frequency = models.CharField(max_length=20)  # 'monthly' or 'weekly'
    day_of_month = models.IntegerField(null=True, blank=True)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_confirm = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recurring_rules"


class Transaction(models.Model):
    """Central record for every money movement.

    Amount is ALWAYS positive; balance_delta holds the signed impact on the account balance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    type = models.CharField(max_length=30)  # expense/income/transfer/exchange/loan_out/loan_in/loan_repayment
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # always positive
    currency = models.CharField(max_length=3)
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, db_column="account_id", related_name="transactions"
    )
    counter_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="counter_account_id", related_name="+"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="category_id", related_name="+"
    )
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    counter_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fee_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="fee_account_id", related_name="+"
    )
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="person_id", related_name="+"
    )
    linked_transaction = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        db_column="linked_transaction_id", related_name="+"
    )
    recurring_rule = models.ForeignKey(
        RecurringRule, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="recurring_rule_id", related_name="+"
    )
    balance_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "transactions"


class VirtualAccount(models.Model):
    """Envelope budgeting — earmarks money for goals without moving actual funds."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    icon = models.CharField(max_length=20, default="")
    color = models.CharField(max_length=20, default="")
    is_archived = models.BooleanField(default=False)
    exclude_from_net_worth = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True,
        db_column="account_id", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "virtual_accounts"

    def __str__(self) -> str:
        return self.name

    def progress_pct(self) -> float:
        """Percentage of target reached."""
        if not self.target_amount:
            return 0.0
        return float(self.current_balance) / float(self.target_amount) * 100


class VirtualAccountAllocation(models.Model):
    """Pivot table linking transactions to virtual accounts.

    transaction is nullable for direct (non-transaction) allocations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, null=True, blank=True,
        db_column="transaction_id", related_name="+"
    )
    virtual_account = models.ForeignKey(
        VirtualAccount, on_delete=models.CASCADE,
        db_column="virtual_account_id", related_name="allocations"
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # positive=contribution, negative=withdrawal
    note = models.TextField(null=True, blank=True)
    allocated_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "virtual_account_allocations"


class Budget(models.Model):
    """Monthly spending limit per category. is_active toggles without deleting."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, db_column="category_id", related_name="+"
    )
    monthly_limit = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "budgets"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "currency"],
                name="budgets_user_category_currency_unique",
            ),
        ]


class Investment(models.Model):
    """Fund holding on a platform like Thndr. Value = units * last_unit_price."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    platform = models.CharField(max_length=100)
    fund_name = models.CharField(max_length=255)
    units = models.DecimalField(max_digits=15, decimal_places=4)
    last_unit_price = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3)
    last_updated = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "investments"

    def __str__(self) -> str:
        return f"{self.platform} — {self.fund_name}"

    def valuation(self) -> float:
        """units * last_unit_price."""
        return float(self.units) * float(self.last_unit_price)


class InstallmentPlan(models.Model):
    """Purchase split into monthly payments (e.g., E24,000 / 12 months).

    remaining_installments is decremented by the service layer each month.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, db_column="account_id", related_name="+"
    )
    description = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    num_installments = models.IntegerField()
    monthly_amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateField()
    remaining_installments = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "installment_plans"

    def is_complete(self) -> bool:
        """All payments made."""
        return self.remaining_installments <= 0

    def paid_installments(self) -> int:
        return self.num_installments - self.remaining_installments


class DailySnapshot(models.Model):
    """Append-only daily financial state. Used for sparklines and MoM comparisons."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    date = models.DateField()
    net_worth_egp = models.DecimalField(max_digits=15, decimal_places=2)
    net_worth_raw = models.DecimalField(max_digits=15, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)
    daily_spending = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    daily_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="daily_snapshots_user_date_unique",
            ),
        ]


class AccountSnapshot(models.Model):
    """Per-account daily balance. Append-only — one row per (user, date, account)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    date = models.DateField()
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, db_column="account_id", related_name="+"
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "account"],
                name="account_snapshots_user_date_account_unique",
            ),
        ]


class ExchangeRateLog(models.Model):
    """Append-only daily USD/EGP rate history. No user — global data.

    Rate = EGP per 1 USD (e.g., 50.5 means 1 USD = 50.5 EGP).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    date = models.DateField()
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    source = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exchange_rate_log"
