"""Helper methods: batch create, smart defaults, VA allocation, dropdowns.

HelperMixin is mixed into TransactionService and relies on methods from
TransactionServiceBase (self.create, self.get_by_id, self.user_id, etc.).
"""

import logging
import uuid
from typing import Any

from django.db import connection, transaction

logger = logging.getLogger(__name__)


class HelperMixin:
    """Mixin providing batch, smart defaults, VA allocation, and dropdown queries."""

    # -------------------------------------------------------------------
    # Batch
    # -------------------------------------------------------------------

    def batch_create(self, items: list[dict[str, Any]]) -> tuple[int, int]:
        """Create multiple transactions. Returns (created_count, failed_count).

        Port of Go's batch handler logic. Each item is processed independently;
        failures don't roll back successes.
        """
        created = 0
        failed = 0
        for item in items:
            try:
                self.create(item)  # type: ignore[attr-defined]
                created += 1
            except (ValueError, Exception) as e:
                logger.warning("batch item failed: %s", e)
                failed += 1
        return created, failed

    # -------------------------------------------------------------------
    # Smart Defaults
    # -------------------------------------------------------------------

    def get_smart_defaults(self, tx_type: str = "expense") -> dict[str, Any]:
        """Compute smart defaults for the entry form.

        Port of Go's TransactionService.GetSmartDefaults.
        Non-critical — returns empty defaults on error.
        """
        defaults: dict[str, Any] = {
            "last_account_id": "",
            "auto_category_id": "",
            "recent_category_ids": [],
        }
        try:
            with connection.cursor() as cursor:
                # Last used account
                cursor.execute(
                    """SELECT account_id FROM transactions
                       WHERE user_id = %s AND type IN ('expense', 'income')
                       ORDER BY created_at DESC LIMIT 1""",
                    [self.user_id],  # type: ignore[attr-defined]
                )
                row = cursor.fetchone()
                if row:
                    defaults["last_account_id"] = str(row[0])

                # Recent categories by frequency
                cursor.execute(
                    """SELECT category_id, COUNT(*) AS cnt
                       FROM transactions
                       WHERE user_id = %s AND type = %s AND category_id IS NOT NULL
                       GROUP BY category_id ORDER BY cnt DESC LIMIT 20""",
                    [self.user_id, tx_type],  # type: ignore[attr-defined]
                )
                defaults["recent_category_ids"] = [str(r[0]) for r in cursor.fetchall()]

                # Auto category (3+ consecutive)
                cursor.execute(
                    """SELECT category_id FROM transactions
                       WHERE user_id = %s AND type = %s AND category_id IS NOT NULL
                       ORDER BY created_at DESC LIMIT 3""",
                    [self.user_id, tx_type],  # type: ignore[attr-defined]
                )
                rows = cursor.fetchall()
                if len(rows) == 3:
                    ids = [str(r[0]) for r in rows]
                    if ids[0] == ids[1] == ids[2]:
                        defaults["auto_category_id"] = ids[0]
        except Exception:
            logger.debug("smart defaults failed (non-critical)", exc_info=True)

        return defaults

    # -------------------------------------------------------------------
    # Category Suggestion
    # -------------------------------------------------------------------

    def suggest_category(self, note_keyword: str) -> str | None:
        """Suggest a category based on note keyword frequency.

        Port of Go's TransactionService.SuggestCategory.
        """
        if not note_keyword or not note_keyword.strip():
            return None
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT category_id, COUNT(*) AS cnt
                   FROM transactions
                   WHERE user_id = %s AND note ILIKE %s AND category_id IS NOT NULL
                   GROUP BY category_id ORDER BY cnt DESC LIMIT 1""",
                [self.user_id, f"%{note_keyword}%"],  # type: ignore[attr-defined]
            )
            row = cursor.fetchone()
        return str(row[0]) if row else None

    # -------------------------------------------------------------------
    # Virtual Account Allocation
    # -------------------------------------------------------------------

    def allocate_to_virtual_account(
        self, tx_id: str, va_id: str, amount: float
    ) -> None:
        """Allocate a transaction to a virtual account.

        Validates that the VA's account_id is null (any account) or matches
        the transaction's account.
        """
        with connection.cursor() as cursor:
            # Validate VA ownership and account linkage
            cursor.execute(
                """SELECT id, account_id, current_balance FROM virtual_accounts
                   WHERE id = %s AND user_id = %s""",
                [va_id, self.user_id],  # type: ignore[attr-defined]
            )
            va = cursor.fetchone()
            if not va:
                raise ValueError(f"Virtual account not found: {va_id}")

            va_account_id = str(va[1]) if va[1] else None
            tx = self.get_by_id(tx_id)  # type: ignore[attr-defined]
            if not tx:
                raise ValueError(f"Transaction not found: {tx_id}")

            if va_account_id and va_account_id != tx["account_id"]:
                raise ValueError("Virtual account is linked to a different account")

            with transaction.atomic():
                cursor.execute(
                    """INSERT INTO virtual_account_allocations
                       (id, virtual_account_id, transaction_id, amount, created_at)
                       VALUES (%s, %s, %s, %s, NOW())""",
                    [str(uuid.uuid4()), va_id, tx_id, amount],
                )
                cursor.execute(
                    """UPDATE virtual_accounts
                       SET current_balance = current_balance + %s, updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [amount, va_id, self.user_id],  # type: ignore[attr-defined]
                )

    def deallocate_from_virtual_accounts(self, tx_id: str) -> None:
        """Remove all virtual account allocations for a transaction."""
        with connection.cursor() as cursor:
            # Get all allocations for this transaction
            cursor.execute(
                """SELECT va.id, vaa.amount
                   FROM virtual_account_allocations vaa
                   JOIN virtual_accounts va ON va.id = vaa.virtual_account_id
                   WHERE vaa.transaction_id = %s AND va.user_id = %s""",
                [tx_id, self.user_id],  # type: ignore[attr-defined]
            )
            allocations = cursor.fetchall()

            if allocations:
                with transaction.atomic():
                    for va_id, alloc_amount in allocations:
                        cursor.execute(
                            """UPDATE virtual_accounts
                               SET current_balance = current_balance - %s, updated_at = NOW()
                               WHERE id = %s AND user_id = %s""",
                            [float(alloc_amount), str(va_id), self.user_id],  # type: ignore[attr-defined]
                        )
                    cursor.execute(
                        "DELETE FROM virtual_account_allocations WHERE transaction_id = %s",
                        [tx_id],
                    )

    def get_allocation_for_tx(self, tx_id: str) -> str | None:
        """Get the virtual account ID allocated to a transaction, if any."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT virtual_account_id FROM virtual_account_allocations
                   WHERE transaction_id = %s LIMIT 1""",
                [tx_id],
            )
            row = cursor.fetchone()
        return str(row[0]) if row else None

    # -------------------------------------------------------------------
    # Helpers for views
    # -------------------------------------------------------------------

    def get_accounts(self) -> list[dict[str, Any]]:
        """Get all non-dormant accounts for dropdowns."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, currency, current_balance, type
                   FROM accounts
                   WHERE user_id = %s AND is_dormant = FALSE
                   ORDER BY display_order, name""",
                [self.user_id],  # type: ignore[attr-defined]
            )
            cols = ["id", "name", "currency", "current_balance", "type"]
            return [
                {
                    col: (
                        str(row[i])
                        if col == "id"
                        else float(row[i])
                        if col == "current_balance"
                        else row[i]
                    )
                    for i, col in enumerate(cols)
                }
                for row in cursor.fetchall()
            ]

    def get_categories(self, cat_type: str | None = None) -> list[dict[str, Any]]:
        """Get categories, optionally filtered by type."""
        query = """SELECT id, name, type, icon FROM categories
                   WHERE user_id = %s"""
        params: list[Any] = [self.user_id]  # type: ignore[attr-defined]
        if cat_type:
            query += " AND type = %s"
            params.append(cat_type)
        query += " ORDER BY name"
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return [
                {"id": str(r[0]), "name": r[1], "type": r[2], "icon": r[3]}
                for r in cursor.fetchall()
            ]

    def get_virtual_accounts(self) -> list[dict[str, Any]]:
        """Get non-archived virtual accounts for allocation dropdown."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, account_id, target_amount, current_balance
                   FROM virtual_accounts
                   WHERE user_id = %s AND is_archived = FALSE
                   ORDER BY name""",
                [self.user_id],  # type: ignore[attr-defined]
            )
            return [
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "account_id": str(r[2]) if r[2] else None,
                    "target_amount": float(r[3]) if r[3] else 0,
                    "current_balance": float(r[4]) if r[4] else 0,
                }
                for r in cursor.fetchall()
            ]

    def get_fees_category_id(self) -> str | None:
        """Look up the 'Fees & Charges' category ID."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM categories
                   WHERE user_id = %s AND name = 'Fees & Charges' LIMIT 1""",
                [self.user_id],  # type: ignore[attr-defined]
            )
            row = cursor.fetchone()
        return str(row[0]) if row else None

    # -------------------------------------------------------------------
    # JSON API — bare transaction lists
    # -------------------------------------------------------------------

    _BARE_TX_COLS = [
        "id",
        "user_id",
        "type",
        "amount",
        "currency",
        "account_id",
        "counter_account_id",
        "category_id",
        "date",
        "time",
        "note",
        "tags",
        "exchange_rate",
        "counter_amount",
        "fee_amount",
        "fee_account_id",
        "person_id",
        "linked_transaction_id",
        "recurring_rule_id",
        "balance_delta",
        "created_at",
        "updated_at",
    ]

    def get_recent(self, limit: int = 15) -> list[dict[str, Any]]:
        """Bare transaction list (not enriched), for JSON API.

        Port of Go's TransactionHandler.List — returns transactions ordered
        by date DESC, created_at DESC.
        """
        if limit <= 0:
            limit = 15
        cols = ", ".join(self._BARE_TX_COLS)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {cols} FROM transactions "
                "WHERE user_id = %s "
                "ORDER BY date DESC, created_at DESC "
                "LIMIT %s",
                [self.user_id, limit],  # type: ignore[attr-defined]
            )
            return [
                self._scan_tx_row(row, self._BARE_TX_COLS)  # type: ignore[attr-defined]
                for row in cursor.fetchall()
            ]

    def get_by_account(self, account_id: str, limit: int = 15) -> list[dict[str, Any]]:
        """Bare transactions for an account, for JSON API."""
        if limit <= 0:
            limit = 15
        cols = ", ".join(self._BARE_TX_COLS)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {cols} FROM transactions "
                "WHERE user_id = %s AND account_id = %s "
                "ORDER BY date DESC, created_at DESC "
                "LIMIT %s",
                [self.user_id, account_id, limit],  # type: ignore[attr-defined]
            )
            return [
                self._scan_tx_row(row, self._BARE_TX_COLS)  # type: ignore[attr-defined]
                for row in cursor.fetchall()
            ]
