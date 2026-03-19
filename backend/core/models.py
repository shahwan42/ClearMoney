"""
Core models — Django representations of the existing Go/PostgreSQL schema.

All models use managed = False because Go owns the schema via golang-migrate.
Django is a read/write consumer, never a schema owner.

Like Laravel's Eloquent models with $table and $guarded, or Django's
standard models but with Meta.managed = False to prevent migration generation.
"""

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models


class User(models.Model):
    """Maps to the 'users' table created by Go migration 000027."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self) -> str:
        return self.email


class Session(models.Model):
    """Maps to the 'sessions' table created by Go migration 000027."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id")
    token = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "sessions"


class AuthToken(models.Model):
    """Maps to the 'auth_tokens' table created by Go migration 000027.

    Short-lived, single-use magic link tokens. Like Laravel's password_resets table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.CharField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    purpose = models.CharField(max_length=20, default="login")  # 'login' or 'registration'
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "auth_tokens"


class UserConfig(models.Model):
    """Maps to the 'user_config' table (migration 000008 + 000023).

    Legacy single-user config table. Kept for backward compat — Go still uses
    this for failed_attempts / locked_until brute-force protection.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    pin_hash = models.TextField()
    session_key = models.TextField()
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "user_config"


class Institution(models.Model):
    """Maps to the 'institutions' table (migration 000001).

    Groups accounts under a bank/fintech/wallet (e.g., HSBC, Telda, Cash).
    Like a parent BelongsTo model in Laravel or a ForeignKey target in Django.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20)  # 'bank', 'fintech', 'wallet'
    color = models.CharField(max_length=20, null=True, blank=True)  # hex color e.g. '#0d9488'
    icon = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "institutions"

    def __str__(self) -> str:
        return self.name


class Account(models.Model):
    """Maps to the 'accounts' table (migration 000002 + subsequent).

    One financial account (bank account, credit card, cash wallet).
    current_balance is cached and updated atomically on every transaction.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    institution_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit', 'cash'
    currency = models.CharField(max_length=3)  # 'EGP' or 'USD'
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_column="current_balance"
    )
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    is_dormant = models.BooleanField(default=False)
    role_tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)  # PostgreSQL text[]
    display_order = models.IntegerField(default=0)
    metadata = models.JSONField(null=True, blank=True)       # JSONB: billing cycle, etc.
    health_config = models.JSONField(null=True, blank=True)  # JSONB: min_balance, min_monthly_deposit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "accounts"

    def __str__(self) -> str:
        return self.name

    def is_credit_type(self) -> bool:
        """Like Go's Account.IsCreditType() — true for credit cards and credit limits."""
        return self.type in ("credit_card", "credit_limit")


class Category(models.Model):
    """Maps to the 'categories' table (migration 000003)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20)  # 'expense' or 'income'
    icon = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "categories"

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    """Maps to the 'transactions' table (migration 000005 + subsequent).

    Central record for every money movement. Amount is ALWAYS positive;
    BalanceDelta holds the signed impact on the account balance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    type = models.CharField(max_length=30)  # expense/income/transfer/exchange/loan_out/loan_in/loan_repayment
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # always positive
    currency = models.CharField(max_length=3)
    account_id = models.UUIDField()
    counter_account_id = models.UUIDField(null=True, blank=True)   # set for transfers/exchanges
    category_id = models.UUIDField(null=True, blank=True)
    date = models.DateField()
    time = models.CharField(max_length=10, null=True, blank=True)  # optional HH:MM string
    note = models.TextField(null=True, blank=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)  # PostgreSQL text[]
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    counter_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fee_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fee_account_id = models.UUIDField(null=True, blank=True)
    person_id = models.UUIDField(null=True, blank=True)
    linked_transaction_id = models.UUIDField(null=True, blank=True)  # other half of a transfer pair
    recurring_rule_id = models.UUIDField(null=True, blank=True)
    balance_delta = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # signed impact
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "transactions"


class Person(models.Model):
    """Maps to the 'persons' table (migration 000004 + 000024).

    Tracks someone you lend money to or borrow from.
    net_balance_egp / net_balance_usd are cached running totals (denormalized).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    name = models.CharField(max_length=100)
    note = models.TextField(null=True, blank=True)
    net_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)      # legacy
    net_balance_egp = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_balance_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "persons"

    def __str__(self) -> str:
        return self.name


class VirtualAccount(models.Model):
    """Maps to the 'virtual_accounts' table (migration 000015, renamed 000022, extended 000025-000026).

    Envelope budgeting — earmarks money for goals (Emergency Fund, Vacation, etc.)
    without moving money between actual bank accounts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    icon = models.CharField(max_length=20, default="")
    color = models.CharField(max_length=20, default="")
    is_archived = models.BooleanField(default=False)
    exclude_from_net_worth = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    account_id = models.UUIDField(null=True, blank=True)  # optional linked bank account
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "virtual_accounts"

    def __str__(self) -> str:
        return self.name

    def progress_pct(self) -> float:
        """Like Go's VirtualAccount.ProgressPct() — percentage of target reached."""
        if not self.target_amount:
            return 0.0
        return float(self.current_balance) / float(self.target_amount) * 100


class VirtualAccountAllocation(models.Model):
    """Maps to 'virtual_account_allocations' (migration 000015, fixed 000025).

    Pivot table linking transactions to virtual accounts.
    transaction_id is nullable for direct (non-transaction) allocations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    transaction_id = models.UUIDField(null=True, blank=True)  # nullable for direct allocations
    virtual_account_id = models.UUIDField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)  # positive=contribution, negative=withdrawal
    note = models.TextField(null=True, blank=True)
    allocated_at = models.DateField(null=True, blank=True)  # set for direct allocations
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "virtual_account_allocations"


class Budget(models.Model):
    """Maps to the 'budgets' table (migration 000016).

    Monthly spending limit per category. is_active toggles without deleting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    category_id = models.UUIDField()
    monthly_limit = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3)  # 'EGP' or 'USD'
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "budgets"


class RecurringRule(models.Model):
    """Maps to the 'recurring_rules' table (migration 000009).

    Schedules recurring transactions (salary, Netflix, etc.).
    template_transaction is a JSONB blob — parse it when needed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    template_transaction = models.JSONField()  # JSONB — parsed into TransactionTemplate on demand
    frequency = models.CharField(max_length=20)  # 'monthly' or 'weekly'
    day_of_month = models.IntegerField(null=True, blank=True)  # set for monthly rules
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    auto_confirm = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "recurring_rules"


class Investment(models.Model):
    """Maps to the 'investments' table (migration 000010).

    Fund holding on a platform like Thndr. Value = units * last_unit_price.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    platform = models.CharField(max_length=100)
    fund_name = models.CharField(max_length=255)
    units = models.DecimalField(max_digits=20, decimal_places=6)
    last_unit_price = models.DecimalField(max_digits=15, decimal_places=6)
    currency = models.CharField(max_length=3)
    last_updated = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "investments"

    def __str__(self) -> str:
        return f"{self.platform} — {self.fund_name}"

    def valuation(self) -> float:
        """Like Go's Investment.Valuation() — units * last_unit_price."""
        return float(self.units) * float(self.last_unit_price)


class InstallmentPlan(models.Model):
    """Maps to the 'installment_plans' table (migration 000011).

    Purchase split into monthly payments (e.g., E£24,000 / 12 months).
    remaining_installments is decremented by the service layer each month.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    account_id = models.UUIDField()  # typically a credit card
    description = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    num_installments = models.IntegerField()
    monthly_amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateField()
    remaining_installments = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "installment_plans"

    def is_complete(self) -> bool:
        """Like Go's InstallmentPlan.IsComplete() — all payments made."""
        return self.remaining_installments <= 0

    def paid_installments(self) -> int:
        """Like Go's InstallmentPlan.PaidInstallments()."""
        return self.num_installments - self.remaining_installments


class DailySnapshot(models.Model):
    """Maps to the 'daily_snapshots' table (migration 000014).

    Append-only daily financial state. Used for sparklines and MoM comparisons.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    date = models.DateField()
    net_worth_egp = models.DecimalField(max_digits=15, decimal_places=2)
    net_worth_raw = models.DecimalField(max_digits=15, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4)
    daily_spending = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    daily_income = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # No updated_at — append-only (immutable log)

    class Meta:
        managed = False
        db_table = "daily_snapshots"


class AccountSnapshot(models.Model):
    """Maps to the 'account_snapshots' table (migration 000014).

    Per-account daily balance. Used for per-account sparklines.
    Append-only — one row per (date, account_id).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user_id = models.UUIDField()
    date = models.DateField()
    account_id = models.UUIDField()
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    # No updated_at — append-only (immutable log)

    class Meta:
        managed = False
        db_table = "account_snapshots"


class ExchangeRateLog(models.Model):
    """Maps to the 'exchange_rate_log' table (migration 000006).

    Append-only daily USD/EGP rate history. No user_id — global data.
    Rate = EGP per 1 USD (e.g., 50.5 means 1 USD = 50.5 EGP).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    date = models.DateField()
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    source = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'CBE', 'manual'
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # No updated_at — append-only (immutable log)

    class Meta:
        managed = False
        db_table = "exchange_rate_log"
