"""
Virtual account service — business logic for envelope budgeting.

Combines service and repository layers into a single class since Django
views call the service directly. The virtual_account_allocations pivot table
links transactions to virtual accounts, similar to Laravel's attach/detach on
BelongsToMany.

KEY INVARIANT: After every allocation/deallocation, the virtual account's cached
current_balance is recalculated from SUM(allocations). This denormalization trades
write complexity for read speed (dashboard reads are frequent, allocations are rare).
"""

import logging
import uuid as uuid_mod
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz

from transactions.models import VirtualAccountAllocation
from virtual_accounts.models import VirtualAccount

logger = logging.getLogger(__name__)

# Fields returned by .values() queries for virtual accounts
_VA_FIELDS = (
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
)


def _row_to_va(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a .values() dict to a virtual account dict.

    Includes computed progress_pct: (current_balance / target_amount) * 100.
    """
    target = float(row["target_amount"]) if row["target_amount"] is not None else None
    balance = float(row["current_balance"])
    progress_pct = 0.0
    if target and target > 0:
        progress_pct = balance / target * 100

    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "target_amount": target,
        "current_balance": balance,
        "icon": row["icon"] or "",
        "color": row["color"] or "",
        "is_archived": row["is_archived"],
        "exclude_from_net_worth": row["exclude_from_net_worth"],
        "display_order": row["display_order"],
        "account_id": str(row["account_id"]) if row["account_id"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "progress_pct": progress_pct,
    }


def _instance_to_va(inst: VirtualAccount) -> dict[str, Any]:
    """Convert a VirtualAccount model instance to a dict with progress_pct."""
    target = float(inst.target_amount) if inst.target_amount is not None else None
    balance = float(inst.current_balance)
    progress_pct = 0.0
    if target and target > 0:
        progress_pct = balance / target * 100

    return {
        "id": str(inst.id),
        "user_id": str(inst.user_id),
        "name": inst.name,
        "target_amount": target,
        "current_balance": balance,
        "icon": inst.icon or "",
        "color": inst.color or "",
        "is_archived": inst.is_archived,
        "exclude_from_net_worth": inst.exclude_from_net_worth,
        "display_order": inst.display_order,
        "account_id": str(inst.account_id) if inst.account_id else None,
        "created_at": inst.created_at,
        "updated_at": inst.updated_at,
        "progress_pct": progress_pct,
    }


class VirtualAccountService:
    """Handles virtual account CRUD, allocations, and balance management.

    All queries are scoped to the authenticated user via user_id.
    """

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return VirtualAccount.objects.for_user(self.user_id)

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """Return all active (non-archived) virtual accounts."""
        rows = (
            self._qs()
            .filter(is_archived=False)
            .order_by("display_order", "created_at")
            .values(*_VA_FIELDS)
        )
        return [_row_to_va(row) for row in rows]

    def get_by_id(self, va_id: str) -> dict[str, Any] | None:
        """Return a single virtual account by ID, or None if not found."""
        row = self._qs().filter(id=va_id).values(*_VA_FIELDS).first()
        if not row:
            return None
        return _row_to_va(row)

    def get_by_account_id(self, account_id: str) -> list[dict[str, Any]]:
        """Return non-archived virtual accounts linked to a specific bank account."""
        rows = (
            self._qs()
            .filter(account_id=account_id, is_archived=False)
            .order_by("display_order", "created_at")
            .values(*_VA_FIELDS)
        )
        return [_row_to_va(row) for row in rows]

    def get_allocations(self, va_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return allocation records for a virtual account (direct + tx-linked).

        Ordered by COALESCE(transaction date, allocated_at) to merge tx-linked
        and direct allocations into a single timeline.
        """
        qs = (
            VirtualAccountAllocation.objects.filter(
                virtual_account_id=uuid_mod.UUID(va_id),
                virtual_account__user_id=uuid_mod.UUID(self.user_id),
            )
            .select_related("transaction")
            .order_by(
                Coalesce("transaction__date", "allocated_at").desc(),
                "-created_at",
            )
        )
        if limit > 0:
            qs = qs[:limit]
        return [
            {
                "id": str(a.id),
                "transaction_id": str(a.transaction_id) if a.transaction_id else None,
                "virtual_account_id": str(a.virtual_account_id),
                "amount": float(a.amount),
                "note": a.note,
                "allocated_at": a.allocated_at,
                "created_at": a.created_at,
            }
            for a in qs
        ]

    def get_transactions(self, va_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return transactions allocated to a virtual account.

        Queries via VirtualAccountAllocation since the FK from Transaction to
        VirtualAccountAllocation has related_name="+" (no reverse accessor).
        """
        qs = (
            VirtualAccountAllocation.objects.filter(
                virtual_account_id=uuid_mod.UUID(va_id),
                virtual_account__user_id=uuid_mod.UUID(self.user_id),
                transaction__isnull=False,
            )
            .select_related("transaction")
            .order_by("-transaction__date", "-transaction__created_at")
        )
        if limit > 0:
            qs = qs[:limit]
        result = []
        for a in qs:
            assert (
                a.transaction is not None
            )  # guaranteed by transaction__isnull=False filter
            result.append(
                {
                    "id": str(a.transaction.id),
                    "type": a.transaction.type,
                    "amount": float(a.transaction.amount),
                    "currency": a.transaction.currency,
                    "note": a.transaction.note,
                    "date": a.transaction.date,
                }
            )
        return result

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

        Validates name is required, defaults color to teal (#0d9488).

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            raise ValueError("Virtual account name is required")
        if not color:
            color = "#0d9488"

        va = VirtualAccount.objects.create(
            user_id=self.user_id,
            name=name.strip(),
            target_amount=target_amount,
            icon=icon,
            color=color,
            account_id=account_id,
            exclude_from_net_worth=exclude_from_net_worth,
        )

        logger.info("virtual_account.created name=%s user=%s", name, self.user_id)
        return _instance_to_va(va)

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

        Returns True if updated, False if not found.

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            raise ValueError("Virtual account name is required")

        count = (
            self._qs()
            .filter(id=va_id)
            .update(
                name=name.strip(),
                target_amount=target_amount,
                icon=icon,
                color=color,
                account_id=account_id,
                exclude_from_net_worth=exclude_from_net_worth,
                updated_at=django_tz.now(),
            )
        )
        updated = bool(count > 0)

        if updated:
            logger.info("virtual_account.updated id=%s user=%s", va_id, self.user_id)
        return updated

    def archive(self, va_id: str) -> bool:
        """Archive (soft-delete) a virtual account.

        Returns True if archived, False if not found.
        """
        count = (
            self._qs()
            .filter(id=va_id)
            .update(is_archived=True, updated_at=django_tz.now())
        )
        archived = bool(count > 0)

        if archived:
            logger.info("virtual_account.archived id=%s user=%s", va_id, self.user_id)
        return archived

    def toggle_exclude(self, va_id: str) -> bool:
        """Toggle the exclude_from_net_worth flag.

        Returns True if toggled, False if VA not found.
        """
        va = self.get_by_id(va_id)
        if not va:
            return False

        new_value = not va["exclude_from_net_worth"]
        count = (
            self._qs()
            .filter(id=va_id)
            .update(exclude_from_net_worth=new_value, updated_at=django_tz.now())
        )
        return bool(count > 0)

    def direct_allocate(
        self,
        va_id: str,
        amount: float,
        note: str,
        allocated_at: datetime | date,
    ) -> None:
        """Allocate funds directly (no transaction) to a virtual account.

        Creates an allocation record and recalculates the cached balance atomically.
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
            VirtualAccountAllocation.objects.create(
                virtual_account_id=va_id,
                amount=amount,
                note=note_val,
                allocated_at=alloc_date,
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

        Called after adding/removing allocations to keep the cached balance in sync.
        Aggregates SUM(amount) from virtual_account_allocations then updates the VA.
        """
        total = VirtualAccountAllocation.objects.filter(
            virtual_account_id=uuid_mod.UUID(va_id)
        ).aggregate(total=Coalesce(Sum("amount"), Decimal(0)))["total"]

        self._qs().filter(id=va_id).update(
            current_balance=total, updated_at=django_tz.now()
        )
