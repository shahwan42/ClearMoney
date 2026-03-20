"""
Transaction service layer — all business logic for transactions, transfers, exchanges.

Port of Go's service/transaction.go + repository/transaction.go.

Like Laravel's TransactionService — validates input, executes atomic SQL,
logs mutations. Uses raw SQL via connection.cursor() because models are
managed=False and queries use window functions, enum casts, and dynamic filters.

CRITICAL INVARIANTS:
- Currency is ALWAYS overridden from the account record (never trust form input).
- All balance updates are atomic (wrapped in transaction.atomic()).
- Exchange rates are always stored as "EGP per 1 USD".
- Amount is always positive; BalanceDelta holds the signed impact.
"""

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection, transaction

logger = logging.getLogger(__name__)

# Valid transaction types — must match PostgreSQL enum
VALID_TX_TYPES = {
    "expense", "income", "transfer", "exchange",
    "loan_out", "loan_in", "loan_repayment",
}

CREDIT_ACCOUNT_TYPES = {"credit_card", "credit_limit"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_float(value: Any) -> float | None:
    """Parse a value to float, returning None if empty or invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _to_str(value: Any) -> str | None:
    """Convert to non-empty string, or None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_tags(value: Any) -> list[str]:
    """Parse tags from DB result (may be list, string, or None)."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        # PostgreSQL returns text[] as '{tag1,tag2}'
        stripped = value.strip("{}")
        if stripped:
            return [t.strip('"') for t in stripped.split(",")]
    return []


def calculate_instapay_fee(amount: float) -> float:
    """Compute InstaPay fee: 0.1% of amount, min 0.5, max 20 EGP.

    Port of Go's CalculateInstapayFee — pure function, no side effects.
    """
    fee = amount * 0.001
    if fee < 0.5:
        fee = 0.5
    if fee > 20:
        fee = 20
    return round(fee, 2)


def resolve_exchange_fields(
    amount: float | None,
    rate: float | None,
    counter_amount: float | None,
) -> tuple[float, float, float]:
    """Compute the missing field from two provided values.

    Formula: amount * rate = counter_amount

    Port of Go's resolveExchangeFields.
    Raises ValueError if fewer than 2 values are provided.
    """
    count = sum(1 for v in (amount, rate, counter_amount) if v is not None and v > 0)
    if count < 2:
        raise ValueError("Provide at least two of: amount, rate, counter_amount")

    if amount and amount > 0 and rate and rate > 0:
        return amount, rate, round(amount * rate, 2)
    if amount and amount > 0 and counter_amount and counter_amount > 0:
        return amount, round(counter_amount / amount, 6), counter_amount
    if rate and rate > 0 and counter_amount and counter_amount > 0:
        return round(counter_amount / rate, 2), rate, counter_amount

    raise ValueError("Invalid exchange parameters")


# ---------------------------------------------------------------------------
# TransactionService
# ---------------------------------------------------------------------------


class TransactionService:
    """Port of Go's TransactionService + TransactionRepo.

    Like Laravel's TransactionService — validates input, executes atomic SQL,
    logs mutations. Takes user_id and tz in __init__ (same as AccountService).
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    # -------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------

    def _balance_delta(self, tx_type: str, amount: float) -> float:
        """Calculate signed balance impact. Port of Go's balanceDelta."""
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

    def _validate_basic(
        self, amount: float, account_id: str, tx_type: str
    ) -> None:
        """Validate basic transaction fields. Port of Go's validateBasic."""
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
            elif col in ("id", "user_id", "account_id", "counter_account_id",
                         "category_id", "fee_account_id", "person_id",
                         "linked_transaction_id", "recurring_rule_id"):
                val = str(val) if val is not None else None
            elif col in ("amount", "balance_delta", "exchange_rate",
                         "counter_amount", "fee_amount", "running_balance",
                         "current_balance", "credit_limit"):
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

        Port of Go's TransactionService.Create.
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
                        tx_id, self.user_id, tx_type, amount, currency,
                        account_id, category_id, tx_date, note,
                        tags, delta, recurring_rule_id,
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
            "id", "user_id", "type", "amount", "currency", "account_id",
            "counter_account_id", "category_id", "date", "time", "note",
            "tags", "exchange_rate", "counter_amount", "fee_amount",
            "fee_account_id", "person_id", "linked_transaction_id",
            "recurring_rule_id", "balance_delta", "created_at", "updated_at",
        ]
        assert row is not None
        created = self._scan_tx_row(row, cols)

        new_balance = acc["current_balance"] + delta

        logger.info(
            "transaction.created type=%s currency=%s account_id=%s user=%s",
            tx_type, currency, account_id, self.user_id,
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
            "id", "user_id", "type", "amount", "currency", "account_id",
            "counter_account_id", "category_id", "date", "time", "note",
            "tags", "exchange_rate", "counter_amount", "fee_amount",
            "fee_account_id", "person_id", "linked_transaction_id",
            "recurring_rule_id", "balance_delta", "created_at", "updated_at",
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
            "id", "type", "amount", "currency", "account_id",
            "counter_account_id", "category_id", "date", "time", "note",
            "tags", "exchange_rate", "counter_amount", "fee_amount",
            "fee_account_id", "person_id", "linked_transaction_id",
            "recurring_rule_id", "balance_delta", "created_at", "updated_at",
            "account_name", "category_name", "category_icon", "running_balance",
        ]
        return self._scan_tx_row(row, cols)

    def get_filtered_enriched(
        self, filters: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Fetch filtered transactions with account_name & running_balance.

        Port of Go's GetFilteredEnriched. Running balance is computed on the
        INNER query over ALL transactions, then filters applied on the OUTER query.
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
            "id", "type", "amount", "currency", "account_id",
            "counter_account_id", "category_id", "date", "time", "note",
            "tags", "exchange_rate", "counter_amount", "fee_amount",
            "fee_account_id", "person_id", "linked_transaction_id",
            "recurring_rule_id", "balance_delta", "created_at", "updated_at",
            "account_name", "category_name", "category_icon", "running_balance",
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
        txs, _ = self.get_filtered_enriched({
            "account_id": account_id, "limit": limit,
        })
        return txs

    def update(self, tx_id: str, data: dict[str, Any]) -> tuple[dict[str, Any], float]:
        """Update a transaction and recalculate balance delta.

        Port of Go's TransactionService.Update.
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
                        tx_type, amount, currency, category_id,
                        note, tx_date, new_delta,
                        tx_id, self.user_id,
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
            "id", "user_id", "type", "amount", "currency", "account_id",
            "counter_account_id", "category_id", "date", "time", "note",
            "tags", "exchange_rate", "counter_amount", "fee_amount",
            "fee_account_id", "person_id", "linked_transaction_id",
            "recurring_rule_id", "balance_delta", "created_at", "updated_at",
        ]
        assert row is not None
        updated = self._scan_tx_row(row, cols)
        new_balance = acc["current_balance"] + balance_adjustment

        logger.info("transaction.updated id=%s user=%s", tx_id, self.user_id)
        return updated, new_balance

    def delete(self, tx_id: str) -> None:
        """Delete a transaction and reverse its balance impact.

        Port of Go's TransactionService.Delete.
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
                        linked_amount, linked_account_id = float(linked[0]), str(linked[1])
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
                    reverse_delta = -self._balance_delta(tx["type"], float(tx["amount"]))
                    cursor.execute(
                        """UPDATE accounts
                           SET current_balance = current_balance + %s, updated_at = NOW()
                           WHERE id = %s AND user_id = %s""",
                        [reverse_delta, tx["account_id"], self.user_id],
                    )

        logger.info("transaction.deleted id=%s user=%s", tx_id, self.user_id)

    # -------------------------------------------------------------------
    # Transfers
    # -------------------------------------------------------------------

    def create_transfer(
        self,
        source_id: str,
        dest_id: str,
        amount: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a same-currency transfer between two accounts.

        Port of Go's TransactionService.CreateTransfer.
        6-step atomic: debit + credit + link + update source + update dest + commit.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot transfer to the same account")

        src_acc = self._get_account(source_id)
        dest_acc = self._get_account(dest_id)
        if src_acc["currency"] != dest_acc["currency"]:
            raise ValueError("Transfer requires same currency; use exchange for cross-currency")

        actual_currency = src_acc["currency"]
        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg (source)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [debit_id, self.user_id, amount, actual_currency,
                     source_id, dest_id, note, tx_date, -amount],
                )
                # Credit leg (destination)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [credit_id, self.user_id, amount, actual_currency,
                     dest_id, source_id, note, tx_date, amount],
                )
                # Link bidirectionally
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, source_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, dest_id, self.user_id],
                )

        logger.info(
            "transaction.transfer_created currency=%s source=%s dest=%s user=%s",
            actual_currency, source_id, dest_id, self.user_id,
        )
        debit_tx = self.get_by_id(debit_id)
        credit_tx = self.get_by_id(credit_id)
        return debit_tx or {}, credit_tx or {}

    def create_instapay_transfer(
        self,
        source_id: str,
        dest_id: str,
        amount: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
        fees_category_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], float]:
        """Create an InstaPay transfer with automatic fee.

        Port of Go's TransactionService.CreateInstapayTransfer.
        Source loses amount + fee, dest gains amount.
        Returns (debit_tx, credit_tx, fee_amount).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot transfer to the same account")

        src_acc = self._get_account(source_id)
        dest_acc = self._get_account(dest_id)
        if src_acc["currency"] != dest_acc["currency"]:
            raise ValueError("InstaPay requires same currency")

        actual_currency = src_acc["currency"]
        fee = calculate_instapay_fee(amount)

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        instapay_note = "InstaPay transfer"
        if note:
            instapay_note = f"{note} (InstaPay)"

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())
        fee_tx_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, fee_amount, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s)""",
                    [debit_id, self.user_id, amount, actual_currency,
                     source_id, dest_id, instapay_note, fee, tx_date, -amount],
                )
                # Credit leg
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'transfer'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [credit_id, self.user_id, amount, actual_currency,
                     dest_id, source_id, instapay_note, tx_date, amount],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],
                )
                # Fee transaction (separate expense)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        category_id, note, date, balance_delta)
                       VALUES (%s, %s, 'expense'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [fee_tx_id, self.user_id, fee, actual_currency,
                     source_id, fees_category_id, "InstaPay fee", tx_date, -fee],
                )
                # Update balances: source loses amount + fee
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount + fee, source_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, dest_id, self.user_id],
                )

        logger.info(
            "transaction.instapay_created currency=%s user=%s",
            actual_currency, self.user_id,
        )
        debit_tx = self.get_by_id(debit_id)
        credit_tx = self.get_by_id(credit_id)
        return debit_tx or {}, credit_tx or {}, fee

    # -------------------------------------------------------------------
    # Exchange
    # -------------------------------------------------------------------

    def create_exchange(
        self,
        source_id: str,
        dest_id: str,
        amount: float | None,
        rate: float | None,
        counter_amount: float | None,
        note: str | None,
        tx_date: date | str | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a cross-currency exchange between two accounts.

        Port of Go's TransactionService.CreateExchange.
        Rate always stored as "EGP per 1 USD". When source=EGP, inverts
        before resolution and inverts back for storage/logging.
        """
        if not source_id or not dest_id:
            raise ValueError("Both source and destination account_id required")
        if source_id == dest_id:
            raise ValueError("Cannot exchange to the same account")

        src_acc = self._get_account(source_id)
        dest_acc = self._get_account(dest_id)
        if src_acc["currency"] == dest_acc["currency"]:
            raise ValueError("Exchange requires different currencies; use transfer for same currency")

        # Rate convention: user enters "EGP per 1 USD"
        # When source=EGP: invert before resolution, invert back after
        source_is_egp = src_acc["currency"] == "EGP"
        if source_is_egp and rate is not None and rate > 0:
            rate = 1.0 / rate

        resolved_amount, formula_rate, resolved_counter = resolve_exchange_fields(
            amount, rate, counter_amount
        )

        # Display rate: always EGP per 1 USD
        display_rate = formula_rate
        if source_is_egp:
            display_rate = 1.0 / formula_rate

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        debit_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Debit leg (source currency out)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, exchange_rate, counter_amount,
                        note, date, balance_delta)
                       VALUES (%s, %s, 'exchange'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [debit_id, self.user_id, resolved_amount, src_acc["currency"],
                     source_id, dest_id, round(display_rate, 6),
                     round(resolved_counter, 2), note, tx_date, -resolved_amount],
                )
                # Credit leg (dest currency in)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, exchange_rate, counter_amount,
                        note, date, balance_delta)
                       VALUES (%s, %s, 'exchange'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [credit_id, self.user_id, resolved_counter, dest_acc["currency"],
                     dest_id, source_id, round(display_rate, 6),
                     round(resolved_amount, 2), note, tx_date, resolved_counter],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, debit_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [debit_id, credit_id, self.user_id],
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [resolved_amount, source_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [resolved_counter, dest_id, self.user_id],
                )

        # Log exchange rate (non-critical)
        try:
            source_label = f"{src_acc['currency']}/{dest_acc['currency']}"
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO exchange_rate_log (id, date, rate, source, note, created_at)
                       VALUES (%s, %s, %s, %s, %s, NOW())""",
                    [str(uuid.uuid4()), tx_date, round(display_rate, 6),
                     source_label, note],
                )
        except Exception:
            logger.warning("Failed to log exchange rate (non-critical)", exc_info=True)

        logger.info(
            "transaction.exchange_created source=%s dest=%s user=%s",
            src_acc["currency"], dest_acc["currency"], self.user_id,
        )
        debit_tx = self.get_by_id(debit_id)
        credit_tx = self.get_by_id(credit_id)
        return debit_tx or {}, credit_tx or {}

    # -------------------------------------------------------------------
    # Fawry Cashout
    # -------------------------------------------------------------------

    def create_fawry_cashout(
        self,
        credit_card_id: str,
        prepaid_id: str,
        amount: float,
        fee: float,
        currency: str | None,
        note: str | None,
        tx_date: date | str | None,
        fees_category_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Create a Fawry credit card cash-out.

        Port of Go's TransactionService.CreateFawryCashout.
        CC charged amount+fee (expense), prepaid gets amount (income).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if fee < 0:
            raise ValueError("Fee cannot be negative")
        if not credit_card_id or not prepaid_id:
            raise ValueError("Both credit card and prepaid account IDs are required")
        if credit_card_id == prepaid_id:
            raise ValueError("Credit card and prepaid account must be different")

        if tx_date is None:
            tx_date = date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date.split("T")[0], "%Y-%m-%d").date()

        total_charge = amount + fee
        cc_acc = self._get_account(credit_card_id)
        actual_currency = cc_acc["currency"]

        charge_note = "Fawry cash-out"
        if note:
            charge_note = f"{note} (Fawry cash-out)"
        credit_note = "Fawry top-up"
        if note:
            credit_note = f"{note} (Fawry top-up)"

        charge_id = str(uuid.uuid4())
        credit_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # CC charge (expense: amount + fee)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, category_id, fee_amount, note, date,
                        balance_delta)
                       VALUES (%s, %s, 'expense'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s, %s, %s)""",
                    [charge_id, self.user_id, total_charge, actual_currency,
                     credit_card_id, prepaid_id, fees_category_id, fee,
                     charge_note, tx_date, -total_charge],
                )
                # Prepaid credit (income: net amount)
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        counter_account_id, note, date, balance_delta)
                       VALUES (%s, %s, 'income'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)""",
                    [credit_id, self.user_id, amount, actual_currency,
                     prepaid_id, credit_card_id, credit_note, tx_date, amount],
                )
                # Link
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [credit_id, charge_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE transactions SET linked_transaction_id = %s
                       WHERE id = %s AND user_id = %s""",
                    [charge_id, credit_id, self.user_id],
                )
                # Update balances
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance - %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [total_charge, credit_card_id, self.user_id],
                )
                cursor.execute(
                    """UPDATE accounts SET current_balance = current_balance + %s,
                       updated_at = NOW() WHERE id = %s AND user_id = %s""",
                    [amount, prepaid_id, self.user_id],
                )

        logger.info(
            "transaction.fawry_cashout_created currency=%s user=%s",
            actual_currency, self.user_id,
        )
        charge_tx = self.get_by_id(charge_id)
        credit_tx = self.get_by_id(credit_id)
        return charge_tx or {}, credit_tx or {}

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
                self.create(item)
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
                    [self.user_id],
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
                    [self.user_id, tx_type],
                )
                defaults["recent_category_ids"] = [str(r[0]) for r in cursor.fetchall()]

                # Auto category (3+ consecutive)
                cursor.execute(
                    """SELECT category_id FROM transactions
                       WHERE user_id = %s AND type = %s AND category_id IS NOT NULL
                       ORDER BY created_at DESC LIMIT 3""",
                    [self.user_id, tx_type],
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
                [self.user_id, f"%{note_keyword}%"],
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
                [va_id, self.user_id],
            )
            va = cursor.fetchone()
            if not va:
                raise ValueError(f"Virtual account not found: {va_id}")

            va_account_id = str(va[1]) if va[1] else None
            tx = self.get_by_id(tx_id)
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
                    [amount, va_id, self.user_id],
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
                [tx_id, self.user_id],
            )
            allocations = cursor.fetchall()

            if allocations:
                with transaction.atomic():
                    for va_id, alloc_amount in allocations:
                        cursor.execute(
                            """UPDATE virtual_accounts
                               SET current_balance = current_balance - %s, updated_at = NOW()
                               WHERE id = %s AND user_id = %s""",
                            [float(alloc_amount), str(va_id), self.user_id],
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
                [self.user_id],
            )
            cols = ["id", "name", "currency", "current_balance", "type"]
            return [
                {col: (str(row[i]) if col == "id" else
                       float(row[i]) if col == "current_balance" else row[i])
                 for i, col in enumerate(cols)}
                for row in cursor.fetchall()
            ]

    def get_categories(self, cat_type: str | None = None) -> list[dict[str, Any]]:
        """Get categories, optionally filtered by type."""
        query = """SELECT id, name, type, icon FROM categories
                   WHERE user_id = %s"""
        params: list[Any] = [self.user_id]
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
                [self.user_id],
            )
            return [
                {
                    "id": str(r[0]), "name": r[1],
                    "account_id": str(r[2]) if r[2] else None,
                    "target_amount": float(r[3]) if r[3] else 0,
                    "current_balance": float(r[4]) if r[4] else 0,
                }
                for r in cursor.fetchall()
            ]

    # -------------------------------------------------------------------
    # Bare list queries (for JSON API — no enrichment)
    # -------------------------------------------------------------------

    _BARE_TX_COLS = [
        "id", "user_id", "type", "amount", "currency", "account_id",
        "counter_account_id", "category_id", "date", "time", "note",
        "tags", "exchange_rate", "counter_amount", "fee_amount",
        "fee_account_id", "person_id", "linked_transaction_id",
        "recurring_rule_id", "balance_delta", "created_at", "updated_at",
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
                [self.user_id, limit],
            )
            return [self._scan_tx_row(row, self._BARE_TX_COLS) for row in cursor.fetchall()]

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
                [self.user_id, account_id, limit],
            )
            return [self._scan_tx_row(row, self._BARE_TX_COLS) for row in cursor.fetchall()]

    def get_fees_category_id(self) -> str | None:
        """Look up the 'Fees & Charges' category ID."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM categories
                   WHERE user_id = %s AND name = 'Fees & Charges' LIMIT 1""",
                [self.user_id],
            )
            row = cursor.fetchone()
        return str(row[0]) if row else None
