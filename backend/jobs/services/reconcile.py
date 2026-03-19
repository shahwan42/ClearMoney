"""
Reconcile service — verifies account balances match transaction history.

Port of Go's ReconcileBalances() (internal/jobs/reconcile.go). Like Laravel's
`php artisan reconcile:balances` or a Django management command that audits
denormalized data. The core formula:

    expected_balance = initial_balance + SUM(balance_delta)
    discrepancy = expected_balance - current_balance

Uses a correlated subquery — the inner SELECT references the outer table (a.id).
COALESCE handles accounts with zero transactions (SUM returns NULL for empty sets).

Tolerance: 0.005 to avoid floating-point noise on NUMERIC(15,2) values.
"""

import logging
from typing import NamedTuple

from django.db import connection

logger = logging.getLogger(__name__)

# Match Go's tolerance for floating-point comparison
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

    Port of Go's ReconcileBalances(ctx, db, autoFix). Queries all accounts
    globally (no user_id filter — matches Go's behavior).
    """

    def reconcile(self, auto_fix: bool = False) -> list[Discrepancy]:
        """Run balance reconciliation across all accounts.

        Args:
            auto_fix: If True, UPDATE current_balance to match computed value.

        Returns:
            List of discrepancies found (may be empty if all balances match).
        """
        discrepancies: list[Discrepancy] = []

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.id,
                    a.name,
                    a.current_balance,
                    a.initial_balance + COALESCE((
                        SELECT SUM(t.balance_delta)
                        FROM transactions t
                        WHERE t.account_id = a.id
                    ), 0) AS expected_balance
                FROM accounts a
                ORDER BY a.name
            """)

            for row in cursor.fetchall():
                account_id = str(row[0])
                account_name = row[1]
                cached = float(row[2])
                expected = float(row[3])
                diff = expected - cached

                if abs(diff) > TOLERANCE:
                    discrepancies.append(
                        Discrepancy(
                            account_id=account_id,
                            account_name=account_name,
                            cached_balance=cached,
                            expected_balance=expected,
                            difference=diff,
                        )
                    )

            if auto_fix and discrepancies:
                for d in discrepancies:
                    try:
                        cursor.execute(
                            "UPDATE accounts SET current_balance = %s, updated_at = NOW() WHERE id = %s",
                            [d.expected_balance, d.account_id],
                        )
                        logger.info(
                            "reconcile.fixed account=%s from=%.2f to=%.2f",
                            d.account_name,
                            d.cached_balance,
                            d.expected_balance,
                        )
                    except Exception:
                        logger.exception(
                            "reconcile.fix_failed account=%s", d.account_name
                        )

        return discrepancies
