"""Accounts models — moved from core.models (Phase 3 migration).

Institution moved in batch 4. Account (depends on Institution) moved in batch 10.
AccountSnapshot moved from jobs app (Phase 3 Cleanup) — per-account snapshot data
belongs in the accounts domain.
SystemBank added in ticket #507 — admin-curated registry of banks/fintechs/wallets.
"""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now
from django.utils.translation import get_language

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class SystemBank(models.Model):
    """Admin-curated registry of banks/fintechs/wallets with bilingual names."""

    BANK_TYPE_CHOICES = [
        ("bank", "Bank"),
        ("fintech", "Fintech"),
        ("wallet", "Wallet"),
    ]

    name = models.JSONField(default=dict)
    short_name = models.CharField(max_length=20)
    svg_path = models.CharField(max_length=200, blank=True, default="")
    brand_color = models.CharField(max_length=7, blank=True, default="")
    country = models.CharField(max_length=2, default="EG")
    bank_type = models.CharField(
        max_length=20, choices=BANK_TYPE_CHOICES, default="bank"
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "system_banks"
        ordering = ["display_order", "short_name"]

    def get_display_name(self, lang: str | None = None) -> str:
        """Return bilingual name. Falls back to en, then short_name."""
        if not isinstance(self.name, dict):
            return str(self.name) if self.name else self.short_name
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
        return self.short_name

    def __str__(self) -> str:
        return f"{self.short_name} ({self.country})"


class Institution(models.Model):
    """Groups accounts under a bank/fintech/wallet (e.g., HSBC, Telda, Cash)."""

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    name = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20, db_default="bank"
    )  # 'bank', 'fintech', 'wallet'
    color = models.CharField(max_length=20, null=True, blank=True)
    icon = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.IntegerField(default=0, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "institutions"

    def __str__(self) -> str:
        return self.name


class Account(models.Model):
    """One financial account (bank account, credit card, cash wallet).

    current_balance is cached and updated atomically on every transaction.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        db_column="institution_id",
        db_index=True,
        related_name="accounts",
    )
    name = models.CharField(max_length=100)
    type = models.CharField(
        max_length=20
    )  # 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit', 'cash'
    currency = models.CharField(max_length=3, db_default="EGP")  # 'EGP' or 'USD'
    current_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    initial_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, db_default=0
    )
    credit_limit = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    is_dormant = models.BooleanField(default=False, db_default=False)
    display_order = models.IntegerField(default=0, db_default=0)

    ROUNDUP_CHOICES = [(5, "5"), (10, "10"), (20, "20"), (50, "50"), (100, "100")]
    roundup_increment = models.SmallIntegerField(
        null=True, blank=True, choices=ROUNDUP_CHOICES
    )
    roundup_target_account = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="roundup_target_account_id",
        related_name="roundup_sources",
    )

    metadata = models.JSONField(null=True, blank=True)  # JSONB: billing cycle, etc.
    health_config = models.JSONField(
        null=True, blank=True
    )  # JSONB: min_balance, min_monthly_deposit
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    last_balance_check_at = models.DateTimeField(null=True, blank=True)
    last_checked_balance = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    last_balance_check_diff = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    last_balance_check_status = models.CharField(
        max_length=20, null=True, blank=True
    )  # 'matched' | 'mismatch'
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "accounts"

    def __str__(self) -> str:
        return self.name

    def is_credit_type(self) -> bool:
        """True for credit cards and credit limits."""
        return self.type in ("credit_card", "credit_limit")


class AccountSnapshot(models.Model):
    """Per-account daily balance. Append-only — one row per (user, date, account).

    Powers per-account sparklines on the accounts page and dashboard.
    Moved from jobs app (Phase 3 Cleanup) since this is accounts domain data.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id"
    )
    date = models.DateField()
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        db_column="account_id",
        related_name="+",
    )
    balance = models.DecimalField(max_digits=15, decimal_places=2, db_default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "account_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "account"],
                name="account_snapshots_user_date_account_unique",
            ),
        ]
