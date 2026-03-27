"""
Reconcile service — verifies account balances match transaction history.

Like Laravel's `php artisan reconcile:balances` or a Django management command that audits
denormalized data. The core formula:

    expected_balance = initial_balance + SUM(balance_delta)
    discrepancy = expected_balance - current_balance

Uses a correlated Subquery — the inner queryset references the outer Account via OuterRef('pk').
COALESCE handles accounts with zero transactions (SUM returns NULL for empty sets).

Tolerance: 0.005 to avoid floating-point noise on NUMERIC(15,2) values.
"""

import logging
from decimal import Decimal
from typing import NamedTuple

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce, Now

from accounts.models import Account
from transactions.models import Transaction

logger = logging.getLogger(__name__)

# Tolerance for floating-point comparison on NUMERIC(15,2) values
TOLERANCE = 0.005


class Discrepancy(NamedTuple):
    """A balance mismatch between cached and computed values."""

    account_id: str
    account_name: str
    cached_balance: float
    expected_balance: float
    difference: float


class ReconcileService:
    """Compares cached current_balance vs initial_balance + SUM(balance_delta).

    Queries all accounts globally (no user_id filter).
    """

    def reconcile(self, auto_fix: bool = False) -> list[Discrepancy]:
        """Run balance reconciliation across all accounts.

        Args:
            auto_fix: If True, update current_balance to match computed value.

        Returns:
            List of discrepancies found (may be empty if all balances match).
        """
        discrepancies: list[Discrepancy] = []

        # Correlated subquery: scalar SUM(balance_delta) per account.
        # .values("account_id") groups by account so the subquery returns one row,
        # then .values("s") extracts the scalar for use in the outer annotation.
        delta_sum = (
            Transaction.objects.filter(account=OuterRef("pk"))
            .values("account_id")
            .annotate(s=Sum("balance_delta"))
            .values("s")
        )

        accounts = Account.objects.annotate(
            expected_balance=F("initial_balance")
            + Coalesce(
                Subquery(
                    delta_sum,
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                Decimal("0"),
            )
        ).order_by("name")

        for account in accounts:
            cached = float(account.current_balance)
            expected = float(account.expected_balance)
            diff = expected - cached

            if abs(diff) > TOLERANCE:
                discrepancies.append(
                    Discrepancy(
                        account_id=str(account.id),
                        account_name=account.name,
                        cached_balance=cached,
                        expected_balance=expected,
                        difference=diff,
                    )
                )

        if auto_fix and discrepancies:
            for d in discrepancies:
                try:
                    Account.objects.filter(id=d.account_id).update(
                        current_balance=d.expected_balance,
                        updated_at=Now(),
                    )
                    logger.info(
                        "reconcile.fixed account=%s from=%.2f to=%.2f",
                        d.account_name,
                        d.cached_balance,
                        d.expected_balance,
                    )
                except Exception:
                    logger.exception("reconcile.fix_failed account=%s", d.account_name)

        return discrepancies
