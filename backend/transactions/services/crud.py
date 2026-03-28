"""Core CRUD operations for the transaction service.

Contains TransactionServiceBase — the foundation class with __init__, private
helpers, and all create/read/update/delete methods. Mixins in other modules
inherit from this to access self.user_id, self.tz, self._get_account(), etc.

Methods converted to Django ORM: create, get_by_id, _get_account, update, delete.
Methods kept as raw SQL: get_by_id_enriched, get_filtered_enriched,
get_recent_enriched, get_by_account_enriched (window functions).
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone as django_tz

from accounts.models import Account
from categories.models import Category
from transactions.models import Transaction

from .utils import CREDIT_ACCOUNT_TYPES, VALID_TX_TYPES, _parse_tags, _to_str

logger = logging.getLogger(__name__)


def _tx_instance_to_dict(tx: Transaction) -> dict[str, Any]:
    """Convert a Transaction model instance to the dict format views expect.

    Monetary values are returned as strings to preserve decimal precision.
    JavaScript clients parse these with Decimal.js library.
    """
    return {
        "id": str(tx.id),
        "user_id": str(tx.user_id),
        "type": tx.type,
        "amount": str(tx.amount),
        "currency": tx.currency,
        "account_id": str(tx.account_id),
        "counter_account_id": str(tx.counter_account_id)
        if tx.counter_account_id
        else None,
        "category_id": str(tx.category_id) if tx.category_id else None,
        "date": tx.date,
        "time": tx.time,
        "note": tx.note,
        "tags": tx.tags or [],
        "exchange_rate": str(tx.exchange_rate)
        if tx.exchange_rate is not None
        else None,
        "counter_amount": str(tx.counter_amount)
        if tx.counter_amount is not None
        else None,
        "fee_amount": str(tx.fee_amount) if tx.fee_amount is not None else None,
        "fee_account_id": str(tx.fee_account_id) if tx.fee_account_id else None,
        "person_id": str(tx.person_id) if tx.person_id else None,
        "linked_transaction_id": (
            str(tx.linked_transaction_id) if tx.linked_transaction_id else None
        ),
        "recurring_rule_id": (
            str(tx.recurring_rule_id) if tx.recurring_rule_id else None
        ),
        "balance_delta": str(tx.balance_delta),
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
    }


class TransactionServiceBase:
    """Like Laravel's TransactionService — validates input, executes atomic SQL,
    logs mutations. Takes user_id and tz in __init__ (same as AccountService).
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _balance_delta(self, tx_type: str, amount: Decimal) -> Decimal:
        """Calculate signed balance impact for a transaction type."""
        if tx_type == "expense":
            return -amount
        if tx_type == "income":
            return amount
        return Decimal(0)  # transfers/exchanges handle their own deltas

    def _get_account(self, account_id: str) -> dict[str, Any]:
        """Fetch account record via ORM. Raises ValueError if not found.

        Returns current_balance and credit_limit as Decimal to preserve precision
        during calculations.
        """
        acc = (
            Account.objects.for_user(self.user_id)
            .filter(id=account_id)
            .values("id", "name", "currency", "current_balance", "type", "credit_limit")
            .first()
        )
        if not acc:
            raise ValueError(f"Account not found: {account_id}")
        return {
            "id": str(acc["id"]),
            "name": acc["name"],
            "currency": acc["currency"],
            "current_balance": Decimal(str(acc["current_balance"])),
            "type": acc["type"],
            "credit_limit": Decimal(str(acc["credit_limit"]))
            if acc["credit_limit"] is not None
            else None,
        }

    def _validate_basic(self, amount: Decimal, account_id: str, tx_type: str) -> None:
        """Validate basic transaction fields."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not account_id:
            raise ValueError("account_id is required")
        if tx_type not in VALID_TX_TYPES:
            raise ValueError(f"Invalid transaction type: {tx_type}")

    def _scan_tx_row(self, row: tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
        """Convert a DB row tuple to a transaction dict.

        Still needed for the raw SQL enriched methods (window functions).
        Monetary values are returned as strings to preserve decimal precision.
        """
        d: dict[str, Any] = {}
        for i, col in enumerate(columns):
            val = row[i]
            if col == "tags":
                val = _parse_tags(val)
            elif col in (
                "id",
                "user_id",
                "account_id",
                "counter_account_id",
                "category_id",
                "fee_account_id",
                "person_id",
                "linked_transaction_id",
                "recurring_rule_id",
            ):
                val = str(val) if val is not None else None
            elif col in (
                "amount",
                "balance_delta",
                "exchange_rate",
                "counter_amount",
                "fee_amount",
                "running_balance",
                "current_balance",
                "credit_limit",
            ):
                val = str(val) if val is not None else None
            elif isinstance(val, Decimal):
                val = str(val)
            d[col] = val
        return d

    # -------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Create a transaction and atomically update the account balance.

        CRITICAL: Currency is overridden from the account record.
        Returns (created_tx_dict, new_balance_str).
        new_balance is returned as a string to preserve decimal precision.
        """
        tx_type = data.get("type", "")
        amount_raw = data.get("amount", 0)
        if not amount_raw or amount_raw == "":
            amount_raw = 0
        amount = Decimal(str(amount_raw))
        account_id = data.get("account_id", "")

        self._validate_basic(amount, account_id, tx_type)

        # Override currency from account (NEVER trust form)
        acc = self._get_account(account_id)
        currency = acc["currency"]

        delta = self._balance_delta(tx_type, amount)

        # Credit card limit check
        if delta < 0 and acc["type"] in CREDIT_ACCOUNT_TYPES and acc["credit_limit"]:
            new_balance = acc["current_balance"] + delta
            if new_balance < -acc["credit_limit"]:
                available = acc["credit_limit"] + acc["current_balance"]
                raise ValueError(
                    f"Would exceed credit limit (available: {available:.2f})"
                )

        tx_id = uuid.uuid4()
        tx_date = data.get("date") or date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        # Validate transaction date is not in the future
        if tx_date > date.today():
            raise ValueError("Transaction date cannot be in the future")

        category_id = _to_str(data.get("category_id"))
        note = _to_str(data.get("note"))
        recurring_rule_id = _to_str(data.get("recurring_rule_id"))
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        with transaction.atomic():
            tx_obj = Transaction.objects.create(
                id=tx_id,
                user_id=self.user_id,
                type=tx_type,
                amount=amount,
                currency=currency,
                account_id=account_id,
                category_id=category_id,
                date=tx_date,
                note=note,
                tags=tags,
                balance_delta=delta,
                recurring_rule_id=recurring_rule_id,
            )

            # Atomic F() update — DB-level add avoids read-modify-write race conditions
            Account.objects.for_user(self.user_id).filter(id=account_id).update(
                current_balance=F("current_balance") + delta,
                updated_at=django_tz.now(),
            )

        created = _tx_instance_to_dict(tx_obj)
        new_balance = acc["current_balance"] + delta

        logger.info(
            "transaction.created type=%s currency=%s account_id=%s user=%s",
            tx_type,
            currency,
            account_id,
            self.user_id,
        )
        return created, str(new_balance)

    def create_fee_for_transaction(
        self,
        parent_tx: dict[str, Any],
        fee_amount: float,
        tx_date: date | str | None,
    ) -> dict[str, Any]:
        """Create a linked fee transaction (expense) for a regular transaction.

        Follows the same pattern as transfer fees (transfers.py): creates a
        separate expense auto-categorized as "Fees & Charges", linked to the
        parent transaction via linked_transaction_id.
        """
        fee = Decimal(str(fee_amount))
        if fee <= 0:
            raise ValueError("Fee must be greater than zero")

        account_id = parent_tx["account_id"]
        currency = parent_tx["currency"]

        fees_cat = (
            Category.objects.for_user(self.user_id)
            .filter(name="Fees & Charges")
            .first()
        )

        resolved_date = tx_date or date.today()
        if isinstance(resolved_date, str):
            resolved_date = datetime.strptime(
                resolved_date.split("T")[0], "%Y-%m-%d"
            ).date()

        with transaction.atomic():
            fee_tx = Transaction.objects.create(
                id=uuid.uuid4(),
                user_id=self.user_id,
                type="expense",
                amount=fee,
                currency=currency,
                account_id=account_id,
                category_id=fees_cat.id if fees_cat else None,
                note="Transaction fee",
                date=resolved_date,
                balance_delta=-fee,
                linked_transaction_id=parent_tx["id"],
            )
            Account.objects.for_user(self.user_id).filter(id=account_id).update(
                current_balance=F("current_balance") - fee,
                updated_at=django_tz.now(),
            )

        logger.info(
            "transaction.fee_created parent=%s fee=%s user=%s",
            parent_tx["id"],
            fee,
            self.user_id,
        )
        return _tx_instance_to_dict(fee_tx)

    def update_fee_for_transaction(
        self,
        tx_id: str,
        fee_amount: float | None,
        tx_date: date | str | None,
    ) -> None:
        """Add, change, or remove the fee linked to a transaction.

        Logic:
        - No old fee + no new fee → no-op
        - No old fee + new fee > 0 → create fee
        - Old fee + new fee is None/0 → delete old fee, reverse balance
        - Old fee + new fee > 0 and different → delete old, create new
        - Old fee + same amount → no-op
        """
        existing_fee = (
            Transaction.objects.for_user(self.user_id)
            .filter(linked_transaction_id=tx_id, note="Transaction fee")
            .first()
        )

        new_fee = Decimal(str(fee_amount)) if fee_amount else None
        if new_fee is not None and new_fee <= 0:
            new_fee = None

        old_fee = Decimal(str(existing_fee.amount)) if existing_fee else None

        # No-op cases
        if old_fee is None and new_fee is None:
            return
        if old_fee == new_fee:
            return

        # Remove old fee if it exists
        if existing_fee:
            now = django_tz.now()
            with transaction.atomic():
                Account.objects.for_user(self.user_id).filter(
                    id=existing_fee.account_id
                ).update(
                    current_balance=F("current_balance")
                    + Decimal(str(existing_fee.amount)),
                    updated_at=now,
                )
                existing_fee.delete()
            logger.info(
                "transaction.fee_removed parent=%s old_fee=%s user=%s",
                tx_id,
                old_fee,
                self.user_id,
            )

        # Create new fee if requested
        if new_fee:
            parent_tx = self.get_by_id(tx_id)
            if not parent_tx:
                raise ValueError("Parent transaction not found")
            self.create_fee_for_transaction(
                parent_tx=parent_tx,
                fee_amount=float(new_fee),
                tx_date=tx_date,
            )

    def get_by_id(self, tx_id: str) -> dict[str, Any] | None:
        """Fetch a single transaction by ID via ORM."""
        tx_obj = Transaction.objects.for_user(self.user_id).filter(id=tx_id).first()
        if not tx_obj:
            return None
        return _tx_instance_to_dict(tx_obj)

    def get_by_id_enriched(self, tx_id: str) -> dict[str, Any] | None:
        """Fetch a single transaction with account_name and running_balance.

        Kept as raw SQL — uses window functions for running balance.
        """
        # Raw SQL — window function computes running balance by subtracting
        # cumulative balance_deltas from current_balance (same pattern as accounts)
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT sub.* FROM (
                    SELECT t.id, t.type, t.amount, t.currency, t.account_id,
                        t.counter_account_id, t.category_id, t.date, t.time, t.note,
                        t.tags, t.exchange_rate, t.counter_amount, t.fee_amount,
                        t.fee_account_id, t.person_id, t.linked_transaction_id,
                        t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
                        a.name AS account_name,
                        c.name AS category_name,
                        c.icon AS category_icon,
                        a.current_balance - COALESCE(
                            SUM(t.balance_delta) OVER (
                                PARTITION BY t.account_id
                                ORDER BY t.date DESC, t.created_at DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                            ), 0
                        ) AS running_balance
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    LEFT JOIN categories c ON c.id = t.category_id
                    WHERE t.user_id = %s
                ) sub WHERE sub.id = %s""",
                [self.user_id, tx_id],
            )
            row = cursor.fetchone()
        if not row:
            return None
        cols = [
            "id",
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
            "account_name",
            "category_name",
            "category_icon",
            "running_balance",
        ]
        return self._scan_tx_row(row, cols)

    def get_filtered_enriched(
        self, filters: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Fetch filtered transactions with account_name & running_balance.

        Running balance is computed on the INNER query over ALL transactions,
        then filters applied on the OUTER query.
        Kept as raw SQL — uses window functions for running balance.
        Returns (transactions, has_more).
        """
        # Inner subquery: window function over ALL user transactions for correct
        # running balance. Outer query: applies filters without breaking the window.
        query = """
            SELECT sub.id, sub.type, sub.amount, sub.currency, sub.account_id,
                sub.counter_account_id, sub.category_id, sub.date, sub.time, sub.note,
                sub.tags, sub.exchange_rate, sub.counter_amount, sub.fee_amount,
                sub.fee_account_id, sub.person_id, sub.linked_transaction_id,
                sub.recurring_rule_id, sub.balance_delta, sub.created_at, sub.updated_at,
                sub.account_name, sub.category_name, sub.category_icon, sub.running_balance
            FROM (
                SELECT t.id, t.type, t.amount, t.currency, t.account_id,
                    t.counter_account_id, t.category_id, t.date, t.time, t.note,
                    t.tags, t.exchange_rate, t.counter_amount, t.fee_amount,
                    t.fee_account_id, t.person_id, t.linked_transaction_id,
                    t.recurring_rule_id, t.balance_delta, t.created_at, t.updated_at,
                    a.name AS account_name,
                    c.name AS category_name,
                    c.icon AS category_icon,
                    a.current_balance - COALESCE(
                        SUM(t.balance_delta) OVER (
                            PARTITION BY t.account_id
                            ORDER BY t.date DESC, t.created_at DESC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                        ), 0
                    ) AS running_balance
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                LEFT JOIN categories c ON c.id = t.category_id
                WHERE t.user_id = %s
            ) sub WHERE 1=1"""

        params: list[Any] = [self.user_id]

        account_id = filters.get("account_id")
        if account_id:
            query += " AND sub.account_id = %s"
            params.append(account_id)

        category_id = filters.get("category_id")
        if category_id:
            query += " AND sub.category_id = %s"
            params.append(category_id)

        tx_type = filters.get("type")
        if tx_type:
            query += " AND sub.type = %s"
            params.append(tx_type)

        date_from = filters.get("date_from")
        if date_from:
            query += " AND sub.date >= %s"
            params.append(date_from)

        date_to = filters.get("date_to")
        if date_to:
            query += " AND sub.date <= %s"
            params.append(date_to)

        search = filters.get("search")
        if search:
            query += " AND sub.note ILIKE %s"
            params.append(f"%{search}%")

        query += " ORDER BY sub.date DESC, sub.created_at DESC"

        limit = int(filters.get("limit", 50))
        if limit <= 0:
            limit = 50
        # Fetch limit+1 to determine has_more
        query += " LIMIT %s"
        params.append(limit + 1)

        offset = int(filters.get("offset", 0))
        if offset > 0:
            query += " OFFSET %s"
            params.append(offset)

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        cols = [
            "id",
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
            "account_name",
            "category_name",
            "category_icon",
            "running_balance",
        ]

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        transactions = [self._scan_tx_row(row, cols) for row in rows]
        return transactions, has_more

    def get_recent_enriched(
        self, limit: int = 15, offset: int = 0
    ) -> tuple[list[dict[str, Any]], bool]:
        """Fetch recent transactions with account_name & running_balance.

        Kept as raw SQL — delegates to get_filtered_enriched (window functions).
        Returns (transactions, has_more).
        """
        if limit <= 0:
            limit = 15
        return self.get_filtered_enriched({"limit": limit, "offset": offset})

    def get_by_account_enriched(
        self, account_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], bool]:
        """Fetch transactions for a specific account, enriched.

        Kept as raw SQL — delegates to get_filtered_enriched (window functions).
        Returns (transactions, has_more).
        """
        return self.get_filtered_enriched(
            {
                "account_id": account_id,
                "limit": limit,
                "offset": offset,
            }
        )

    def get_paginated(
        self, limit: int = 15, offset: int = 0, account_id: str = ""
    ) -> dict[str, Any]:
        """Fetch paginated transactions with metadata.

        Returns dict with 'results', 'total_count', 'has_next', 'has_previous'.
        """
        if limit <= 0:
            limit = 15
        if offset < 0:
            offset = 0

        if account_id:
            txs, has_more = self.get_by_account_enriched(account_id, limit, offset)
        else:
            txs, has_more = self.get_recent_enriched(limit, offset)

        # Get total count for the filtered set
        filters: dict[str, Any] = {}
        if account_id:
            filters["account_id"] = account_id
        filters["limit"] = 999999  # Large number to get total
        filters["offset"] = 0
        all_txs, _ = self.get_filtered_enriched(filters)
        total_count = len(all_txs)

        return {
            "results": txs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_next": has_more,
            "has_previous": offset > 0,
        }

    def update(self, tx_id: str, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """Update a transaction and recalculate balance delta.

        Balance adjustment = newDelta - oldDelta.
        Returns new_balance as string to preserve decimal precision.
        """
        old = self.get_by_id(tx_id)
        if not old:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx_type = data.get("type", old["type"])
        amount_raw = data.get("amount", old["amount"])
        if not amount_raw or amount_raw == "":
            amount_raw = old["amount"]
        amount = Decimal(str(amount_raw))
        self._validate_basic(amount, old["account_id"], tx_type)

        # Override currency from account
        acc = self._get_account(old["account_id"])
        currency = acc["currency"]

        old_delta = self._balance_delta(old["type"], Decimal(str(old["amount"])))
        new_delta = self._balance_delta(tx_type, amount)
        balance_adjustment = new_delta - old_delta

        category_id = data.get("category_id", old["category_id"])
        if category_id == "":
            category_id = None
        note = data.get("note", old["note"])
        if note == "":
            note = None
        tx_date = data.get("date", old["date"])
        if isinstance(tx_date, str) and tx_date:
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()

        # Validate transaction date is not in the future
        if tx_date > date.today():
            raise ValueError("Transaction date cannot be in the future")

        now = django_tz.now()

        with transaction.atomic():
            # Update transaction fields via ORM
            updated_count = (
                Transaction.objects.for_user(self.user_id)
                .filter(id=tx_id)
                .update(
                    type=tx_type,
                    amount=amount,
                    currency=currency,
                    category_id=category_id,
                    note=note,
                    date=tx_date,
                    balance_delta=new_delta,
                    updated_at=now,
                )
            )
            if updated_count == 0:
                raise ValueError(f"Transaction not found: {tx_id}")

            # Atomic F() update — only adjusts by the difference (newDelta - oldDelta)
            if balance_adjustment != 0:
                Account.objects.for_user(self.user_id).filter(
                    id=old["account_id"]
                ).update(
                    current_balance=F("current_balance") + balance_adjustment,
                    updated_at=now,
                )

        # Re-fetch the updated transaction to return the full dict
        tx_obj = Transaction.objects.for_user(self.user_id).filter(id=tx_id).first()
        assert tx_obj is not None
        updated = _tx_instance_to_dict(tx_obj)
        new_balance = acc["current_balance"] + balance_adjustment

        logger.info("transaction.updated id=%s user=%s", tx_id, self.user_id)
        return updated, str(new_balance)

    def delete(self, tx_id: str) -> None:
        """Delete a transaction and reverse its balance impact.

        For linked transactions (transfers/exchanges), deletes both legs.
        """
        tx = self.get_by_id(tx_id)
        if not tx:
            raise ValueError(f"Transaction not found: {tx_id}")

        is_linked = tx["linked_transaction_id"] is not None
        now = django_tz.now()

        # Collect linked fee transactions BEFORE any deletions
        # (FK is SET_NULL on cascade, so fees lose their link after parent delete)
        fee_parent_ids = [tx_id]
        if is_linked and tx.get("linked_transaction_id"):
            fee_parent_ids.append(tx["linked_transaction_id"])
        fee_txs = list(
            Transaction.objects.for_user(self.user_id)
            .filter(
                linked_transaction_id__in=fee_parent_ids,
                note__in=["Transaction fee", "Transfer fee"],
            )
            .values("id", "amount", "account_id")
        )

        with transaction.atomic():
            # Delete this transaction
            Transaction.objects.for_user(self.user_id).filter(id=tx_id).delete()

            if is_linked:
                # Transfer/exchange: F() atomically reverses the source debit
                amount_decimal = Decimal(str(tx["amount"]))
                Account.objects.for_user(self.user_id).filter(
                    id=tx["account_id"]
                ).update(
                    current_balance=F("current_balance") + amount_decimal,
                    updated_at=now,
                )

                # Fetch linked transaction details before deleting
                linked_id = tx["linked_transaction_id"]
                linked_obj = (
                    Transaction.objects.for_user(self.user_id)
                    .filter(id=linked_id)
                    .values("amount", "account_id")
                    .first()
                )
                if linked_obj:
                    linked_amount = Decimal(str(linked_obj["amount"]))
                    linked_account_id = str(linked_obj["account_id"])

                    Transaction.objects.for_user(self.user_id).filter(
                        id=linked_id
                    ).delete()

                    # F() atomically reverses the destination credit
                    Account.objects.for_user(self.user_id).filter(
                        id=linked_account_id
                    ).update(
                        current_balance=F("current_balance") - linked_amount,
                        updated_at=now,
                    )
            else:
                # Simple expense/income: F() atomically reverses balance delta
                reverse_delta = -self._balance_delta(
                    tx["type"], Decimal(str(tx["amount"]))
                )
                Account.objects.for_user(self.user_id).filter(
                    id=tx["account_id"]
                ).update(
                    current_balance=F("current_balance") + reverse_delta,
                    updated_at=now,
                )

            # Delete fee transactions and reverse their balance impact
            for fee in fee_txs:
                fee_amount = Decimal(str(fee["amount"]))
                Account.objects.for_user(self.user_id).filter(
                    id=fee["account_id"]
                ).update(
                    current_balance=F("current_balance") + fee_amount,
                    updated_at=now,
                )
            if fee_txs:
                Transaction.objects.for_user(self.user_id).filter(
                    id__in=[f["id"] for f in fee_txs]
                ).delete()

        logger.info("transaction.deleted id=%s user=%s", tx_id, self.user_id)
