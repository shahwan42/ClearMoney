"""Transactions models — moved from core.models (Phase 3 migration)."""

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

# SQL-level default for UUID primary keys (gen_random_uuid())
GEN_UUID = Func(function="gen_random_uuid")


class Transaction(models.Model):
    """Central record for every money movement.

    Amount is ALWAYS positive; balance_delta holds the signed impact on the account balance.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
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
        "categories.Category",
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
