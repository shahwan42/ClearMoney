"""Core CRUD operations for the transaction service.

Contains TransactionServiceBase — the foundation class with __init__, private
helpers, and all create/read/update/delete methods. Mixins in other modules
inherit from this to access self.user_id, self.tz, self._get_account(), etc.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection, transaction

from .utils import CREDIT_ACCOUNT_TYPES, VALID_TX_TYPES, _parse_tags, _to_str

logger = logging.getLogger(__name__)


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

    def _balance_delta(self, tx_type: str, amount: float) -> float:
        """Calculate signed balance impact for a transaction type."""
        if tx_type == "expense":
            return -amount
        if tx_type == "income":
            return amount
        return 0  # transfers/exchanges handle their own deltas

    def _get_account(self, account_id: str) -> dict[str, Any]:
        """Fetch account record. Raises ValueError if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, currency, current_balance, type, credit_limit
                   FROM accounts WHERE id = %s AND user_id = %s""",
                [account_id, self.user_id],
            )
            row = cursor.fetchone()
        if not row:
            raise ValueError(f"Account not found: {account_id}")
        return {
            "id": str(row[0]),
            "name": row[1],
            "currency": row[2],
            "current_balance": float(row[3]),
            "type": row[4],
            "credit_limit": float(row[5]) if row[5] is not None else None,
        }

    def _validate_basic(self, amount: float, account_id: str, tx_type: str) -> None:
        """Validate basic transaction fields."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not account_id:
            raise ValueError("account_id is required")
        if tx_type not in VALID_TX_TYPES:
            raise ValueError(f"Invalid transaction type: {tx_type}")

    def _scan_tx_row(self, row: tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
        """Convert a DB row tuple to a transaction dict."""
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
                val = float(val) if val is not None else None
            elif isinstance(val, Decimal):
                val = float(val)
            d[col] = val
        return d

    # -------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Create a transaction and atomically update the account balance.

        CRITICAL: Currency is overridden from the account record.
        Returns (created_tx_dict, new_balance).
        """
        tx_type = data.get("type", "")
        amount = float(data.get("amount", 0))
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

        tx_id = str(uuid.uuid4())
        tx_date = data.get("date") or date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        category_id = _to_str(data.get("category_id"))
        note = _to_str(data.get("note"))
        recurring_rule_id = _to_str(data.get("recurring_rule_id"))
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        category_id, date, note, tags, balance_delta,
                        recurring_rule_id)
                       VALUES (%s, %s, %s::transaction_type, %s, %s::currency_type,
                               %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id, user_id, type, amount, currency, account_id,
                                 counter_account_id, category_id, date, time, note,
                                 tags, exchange_rate, counter_amount, fee_amount,
                                 fee_account_id, person_id, linked_transaction_id,
                                 recurring_rule_id, balance_delta, created_at, updated_at""",
                    [
                        tx_id,
                        self.user_id,
                        tx_type,
                        amount,
                        currency,
                        account_id,
                        category_id,
                        tx_date,
                        note,
                        tags,
                        delta,
                        recurring_rule_id,
                    ],
                )
                row = cursor.fetchone()

                # Update account balance
                cursor.execute(
                    """UPDATE accounts
                       SET current_balance = current_balance + %s, updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [delta, account_id, self.user_id],
                )

        cols = [
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
        assert row is not None
        created = self._scan_tx_row(row, cols)

        new_balance = acc["current_balance"] + delta

        logger.info(
            "transaction.created type=%s currency=%s account_id=%s user=%s",
            tx_type,
            currency,
            account_id,
            self.user_id,
        )
        return created, new_balance

    def get_by_id(self, tx_id: str) -> dict[str, Any] | None:
        """Fetch a single transaction by ID."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, type, amount, currency, account_id,
                          counter_account_id, category_id, date, time, note,
                          tags, exchange_rate, counter_amount, fee_amount,
                          fee_account_id, person_id, linked_transaction_id,
                          recurring_rule_id, balance_delta, created_at, updated_at
                   FROM transactions WHERE id = %s AND user_id = %s""",
                [tx_id, self.user_id],
            )
            row = cursor.fetchone()
        if not row:
            return None
        cols = [
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
        return self._scan_tx_row(row, cols)

    def get_by_id_enriched(self, tx_id: str) -> dict[str, Any] | None:
        """Fetch a single transaction with account_name and running_balance."""
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
        Returns (transactions, has_more).
        """
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

    def get_recent_enriched(self, limit: int = 15) -> list[dict[str, Any]]:
        """Fetch recent transactions with account_name & running_balance."""
        if limit <= 0:
            limit = 15
        txs, _ = self.get_filtered_enriched({"limit": limit})
        return txs

    def get_by_account_enriched(
        self, account_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch transactions for a specific account, enriched."""
        txs, _ = self.get_filtered_enriched(
            {
                "account_id": account_id,
                "limit": limit,
            }
        )
        return txs

    def update(self, tx_id: str, data: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Update a transaction and recalculate balance delta.

        Balance adjustment = newDelta - oldDelta.
        """
        old = self.get_by_id(tx_id)
        if not old:
            raise ValueError(f"Transaction not found: {tx_id}")

        tx_type = data.get("type", old["type"])
        amount = float(data.get("amount", old["amount"]))
        self._validate_basic(amount, old["account_id"], tx_type)

        # Override currency from account
        acc = self._get_account(old["account_id"])
        currency = acc["currency"]

        old_delta = self._balance_delta(old["type"], float(old["amount"]))
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

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE transactions
                       SET type = %s::transaction_type, amount = %s,
                           currency = %s::currency_type, category_id = %s,
                           note = %s, date = %s, balance_delta = %s,
                           updated_at = NOW()
                       WHERE id = %s AND user_id = %s
                       RETURNING id, user_id, type, amount, currency, account_id,
                                 counter_account_id, category_id, date, time, note,
                                 tags, exchange_rate, counter_amount, fee_amount,
                                 fee_account_id, person_id, linked_transaction_id,
                                 recurring_rule_id, balance_delta, created_at, updated_at""",
                    [
                        tx_type,
                        amount,
                        currency,
                        category_id,
                        note,
                        tx_date,
                        new_delta,
                        tx_id,
                        self.user_id,
                    ],
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Transaction not found: {tx_id}")

                if balance_adjustment != 0:
                    cursor.execute(
                        """UPDATE accounts
                           SET current_balance = current_balance + %s, updated_at = NOW()
                           WHERE id = %s AND user_id = %s""",
                        [balance_adjustment, old["account_id"], self.user_id],
                    )

        cols = [
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
        assert row is not None
        updated = self._scan_tx_row(row, cols)
        new_balance = acc["current_balance"] + balance_adjustment

        logger.info("transaction.updated id=%s user=%s", tx_id, self.user_id)
        return updated, new_balance

    def delete(self, tx_id: str) -> None:
        """Delete a transaction and reverse its balance impact.

        For linked transactions (transfers/exchanges), deletes both legs.
        """
        tx = self.get_by_id(tx_id)
        if not tx:
            raise ValueError(f"Transaction not found: {tx_id}")

        is_linked = tx["linked_transaction_id"] is not None

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Delete this transaction
                cursor.execute(
                    "DELETE FROM transactions WHERE id = %s AND user_id = %s",
                    [tx_id, self.user_id],
                )

                if is_linked:
                    # Transfer/exchange: reverse both accounts
                    cursor.execute(
                        """UPDATE accounts
                           SET current_balance = current_balance + %s, updated_at = NOW()
                           WHERE id = %s AND user_id = %s""",
                        [tx["amount"], tx["account_id"], self.user_id],
                    )
                    # Delete and reverse linked transaction
                    linked_id = tx["linked_transaction_id"]
                    cursor.execute(
                        """SELECT amount, account_id FROM transactions
                           WHERE id = %s AND user_id = %s""",
                        [linked_id, self.user_id],
                    )
                    linked = cursor.fetchone()
                    if linked:
                        linked_amount, linked_account_id = (
                            float(linked[0]),
                            str(linked[1]),
                        )
                        cursor.execute(
                            "DELETE FROM transactions WHERE id = %s AND user_id = %s",
                            [linked_id, self.user_id],
                        )
                        cursor.execute(
                            """UPDATE accounts
                               SET current_balance = current_balance - %s, updated_at = NOW()
                               WHERE id = %s AND user_id = %s""",
                            [linked_amount, linked_account_id, self.user_id],
                        )
                else:
                    # Simple expense/income: reverse balance delta
                    reverse_delta = -self._balance_delta(
                        tx["type"], float(tx["amount"])
                    )
                    cursor.execute(
                        """UPDATE accounts
                           SET current_balance = current_balance + %s, updated_at = NOW()
                           WHERE id = %s AND user_id = %s""",
                        [reverse_delta, tx["account_id"], self.user_id],
                    )

        logger.info("transaction.deleted id=%s user=%s", tx_id, self.user_id)
