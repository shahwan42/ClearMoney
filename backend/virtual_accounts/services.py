"""
Virtual account service — business logic for envelope budgeting.

Port of Go's VirtualAccountService (internal/service/virtual_account.go) and
VirtualAccountRepo (internal/repository/virtual_account.go). Combines both
layers into a single service since Django views call the service directly.

Like Laravel's VirtualAccountService with a polymorphic many-to-many
relationship (virtual_account_allocations pivot table). The Allocate/Deallocate
methods manage this pivot, similar to Laravel's attach/detach on BelongsToMany.

Django analogy: a through model (VirtualAccountAllocation) on a ManyToManyField
between Transaction and VirtualAccount, with extra amount data on the through table.

KEY INVARIANT: After every allocation/deallocation, the virtual account's cached
current_balance is recalculated from SUM(allocations). This denormalization trades
write complexity for read speed (dashboard reads are frequent, allocations are rare).
"""

import logging
from datetime import date, datetime
from typing import Any

from django.db import connection, transaction

logger = logging.getLogger(__name__)

# Columns returned by virtual_accounts SELECT queries
_VA_COLS = [
    "id",
    "user_id",
    "name",
    "target_amount",
    "current_balance",
    "icon",
    "color",
    "is_archived",
    "exclude_from_net_worth",
    "display_order",
    "account_id",
    "created_at",
    "updated_at",
]

# Columns returned by allocation SELECT queries
_ALLOC_COLS = [
    "id",
    "transaction_id",
    "virtual_account_id",
    "amount",
    "note",
    "allocated_at",
    "created_at",
]

# Columns returned by transaction SELECT queries (for VA history)
_TX_COLS = [
    "id",
    "type",
    "amount",
    "currency",
    "note",
    "date",
]


def _row_to_va(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a virtual_accounts SQL row to a dict.

    Includes computed progress_pct matching Go's VirtualAccount.ProgressPct().
    """
    target = float(row[3]) if row[3] is not None else None
    balance = float(row[4])
    progress_pct = 0.0
    if target and target > 0:
        progress_pct = balance / target * 100

    return {
        "id": str(row[0]),
        "user_id": str(row[1]),
        "name": row[2],
        "target_amount": target,
        "current_balance": balance,
        "icon": row[5] or "",
        "color": row[6] or "",
        "is_archived": row[7],
        "exclude_from_net_worth": row[8],
        "display_order": row[9],
        "account_id": str(row[10]) if row[10] else None,
        "created_at": row[11],
        "updated_at": row[12],
        "progress_pct": progress_pct,
    }


def _row_to_allocation(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a virtual_account_allocations SQL row to a dict."""
    return {
        "id": str(row[0]),
        "transaction_id": str(row[1]) if row[1] else None,
        "virtual_account_id": str(row[2]),
        "amount": float(row[3]),
        "note": row[4],
        "allocated_at": row[5],
        "created_at": row[6],
    }


def _row_to_transaction(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a transaction SQL row (VA history subset) to a dict."""
    return {
        "id": str(row[0]),
        "type": row[1],
        "amount": float(row[2]),
        "currency": row[3],
        "note": row[4],
        "date": row[5],
    }


class VirtualAccountService:
    """Handles virtual account CRUD, allocations, and balance management.

    Like Go's VirtualAccountService + VirtualAccountRepo combined.
    All queries are scoped to the authenticated user via user_id.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """Return all active (non-archived) virtual accounts.

        Port of Go's VirtualAccountRepo.GetAll().
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, name, target_amount, current_balance,
                       icon, color, is_archived, exclude_from_net_worth,
                       display_order, account_id, created_at, updated_at
                FROM virtual_accounts
                WHERE is_archived = false AND user_id = %s
                ORDER BY display_order, created_at
                """,
                [self.user_id],
            )
            return [_row_to_va(row) for row in cursor.fetchall()]

    def get_by_id(self, va_id: str) -> dict[str, Any] | None:
        """Return a single virtual account by ID, or None if not found.

        Port of Go's VirtualAccountRepo.GetByID().
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, name, target_amount, current_balance,
                       icon, color, is_archived, exclude_from_net_worth,
                       display_order, account_id, created_at, updated_at
                FROM virtual_accounts
                WHERE id = %s AND user_id = %s
                """,
                [va_id, self.user_id],
            )
            row = cursor.fetchone()
            return _row_to_va(row) if row else None

    def get_by_account_id(self, account_id: str) -> list[dict[str, Any]]:
        """Return non-archived virtual accounts linked to a specific bank account.

        Port of Go's VirtualAccountRepo.GetByAccountID().
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, name, target_amount, current_balance,
                       icon, color, is_archived, exclude_from_net_worth,
                       display_order, account_id, created_at, updated_at
                FROM virtual_accounts
                WHERE account_id = %s AND is_archived = false AND user_id = %s
                ORDER BY display_order, created_at
                """,
                [account_id, self.user_id],
            )
            return [_row_to_va(row) for row in cursor.fetchall()]

    def get_allocations(self, va_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return allocation records for a virtual account (direct + tx-linked).

        Port of Go's VirtualAccountRepo.GetAllocationsForAccount().
        Uses LEFT JOIN so both transaction-linked and direct allocations appear.
        """
        sql = """
            SELECT a.id, a.transaction_id, a.virtual_account_id, a.amount,
                   a.note, a.allocated_at, a.created_at
            FROM virtual_account_allocations a
            LEFT JOIN transactions t ON a.transaction_id = t.id
            JOIN virtual_accounts va ON a.virtual_account_id = va.id
            WHERE a.virtual_account_id = %s AND va.user_id = %s
            ORDER BY COALESCE(t.date, a.allocated_at) DESC, a.created_at DESC
        """
        params: list[Any] = [va_id, self.user_id]
        if limit > 0:
            sql += " LIMIT %s"
            params.append(limit)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [_row_to_allocation(row) for row in cursor.fetchall()]

    def get_transactions(self, va_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return transactions allocated to a virtual account.

        Port of Go's VirtualAccountRepo.GetTransactionsForAccount().
        Returns a subset of transaction fields needed for the history display.
        """
        sql = """
            SELECT t.id, t.type, t.amount, t.currency, t.note, t.date
            FROM transactions t
            JOIN virtual_account_allocations a ON t.id = a.transaction_id
            JOIN virtual_accounts va ON a.virtual_account_id = va.id
            WHERE a.virtual_account_id = %s AND va.user_id = %s
            ORDER BY t.date DESC, t.created_at DESC
        """
        params: list[Any] = [va_id, self.user_id]
        if limit > 0:
            sql += " LIMIT %s"
            params.append(limit)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [_row_to_transaction(row) for row in cursor.fetchall()]

    # -----------------------------------------------------------------------
    # Write operations
    # -----------------------------------------------------------------------

    def create(
        self,
        name: str,
        target_amount: float | None = None,
        icon: str = "",
        color: str = "",
        account_id: str | None = None,
        exclude_from_net_worth: bool = False,
    ) -> dict[str, Any]:
        """Create a new virtual account with validation.

        Port of Go's VirtualAccountService.Create(). Validates name is required,
        defaults color to teal (#0d9488).

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            raise ValueError("Virtual account name is required")
        if not color:
            color = "#0d9488"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO virtual_accounts
                    (user_id, name, target_amount, icon, color, account_id,
                     exclude_from_net_worth)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, name, target_amount, current_balance,
                          icon, color, is_archived, exclude_from_net_worth,
                          display_order, account_id, created_at, updated_at
                """,
                [
                    self.user_id,
                    name.strip(),
                    target_amount,
                    icon,
                    color,
                    account_id,
                    exclude_from_net_worth,
                ],
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError("Failed to create virtual account")

        logger.info("virtual_account.created name=%s user=%s", name, self.user_id)
        return _row_to_va(row)

    def update(
        self,
        va_id: str,
        name: str,
        target_amount: float | None = None,
        icon: str = "",
        color: str = "",
        account_id: str | None = None,
        exclude_from_net_worth: bool = False,
    ) -> bool:
        """Update an existing virtual account.

        Port of Go's VirtualAccountService.Update(). Validates name is required.

        Returns True if updated, False if not found.

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            raise ValueError("Virtual account name is required")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE virtual_accounts
                SET name = %s, target_amount = %s, icon = %s, color = %s,
                    account_id = %s, exclude_from_net_worth = %s,
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                [
                    name.strip(),
                    target_amount,
                    icon,
                    color,
                    account_id,
                    exclude_from_net_worth,
                    va_id,
                    self.user_id,
                ],
            )
            updated: bool = cursor.rowcount > 0

        if updated:
            logger.info("virtual_account.updated id=%s user=%s", va_id, self.user_id)
        return updated

    def archive(self, va_id: str) -> bool:
        """Archive (soft-delete) a virtual account.

        Port of Go's VirtualAccountService.Archive().
        Returns True if archived, False if not found.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE virtual_accounts
                SET is_archived = true, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                [va_id, self.user_id],
            )
            archived: bool = cursor.rowcount > 0

        if archived:
            logger.info("virtual_account.archived id=%s user=%s", va_id, self.user_id)
        return archived

    def toggle_exclude(self, va_id: str) -> bool:
        """Toggle the exclude_from_net_worth flag.

        Port of Go's VirtualAccountToggleExclude handler logic.
        Returns True if toggled, False if VA not found.
        """
        va = self.get_by_id(va_id)
        if not va:
            return False

        new_value = not va["exclude_from_net_worth"]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE virtual_accounts
                SET exclude_from_net_worth = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                [new_value, va_id, self.user_id],
            )
            return bool(cursor.rowcount > 0)

    def direct_allocate(
        self,
        va_id: str,
        amount: float,
        note: str,
        allocated_at: datetime | date,
    ) -> None:
        """Allocate funds directly (no transaction) to a virtual account.

        Port of Go's VirtualAccountService.DirectAllocate(). Creates an allocation
        record and recalculates the cached balance atomically.

        Amount should be positive for contributions, negative for withdrawals.

        Raises:
            ValueError: If amount is zero.
        """
        if amount == 0:
            raise ValueError("Allocation amount cannot be zero")

        alloc_date = (
            allocated_at.date() if isinstance(allocated_at, datetime) else allocated_at
        )
        note_val = note if note else None

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO virtual_account_allocations
                        (virtual_account_id, amount, note, allocated_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [va_id, amount, note_val, alloc_date],
                )
            self._recalculate_balance(va_id)

        logger.info(
            "virtual_account.direct_allocated virtual_account_id=%s user=%s",
            va_id,
            self.user_id,
        )

    # -----------------------------------------------------------------------
    # Balance recalculation
    # -----------------------------------------------------------------------

    def _recalculate_balance(self, va_id: str) -> None:
        """Recompute a virtual account's balance from its allocations.

        Port of Go's VirtualAccountRepo.RecalculateBalance().
        Called after adding/removing allocations to keep the cached balance in sync.
        Uses a correlated subquery — same PostgreSQL pattern as Go.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE virtual_accounts
                SET current_balance = COALESCE((
                    SELECT SUM(amount)
                    FROM virtual_account_allocations
                    WHERE virtual_account_id = %s
                ), 0),
                updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                [va_id, va_id, self.user_id],
            )
