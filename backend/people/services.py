"""
Person service layer — business logic for people ledger (loans and debts).

Port of Go's service/person.go + repository/person.go.

Like Laravel's PersonService — validates input, executes atomic SQL,
logs mutations. Uses raw SQL via connection.cursor() because models are
managed=False and queries use enum casts.

CRITICAL INVARIANTS:
- Currency is ALWAYS overridden from the account record (never trust form input).
- All balance updates are atomic (wrapped in transaction.atomic()).
- Amount is always positive; deltas hold the signed impact.
- Net balance convention: positive = they owe me, negative = I owe them.
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection, transaction

logger = logging.getLogger(__name__)

# Columns returned by person SELECT queries
_PERSON_COLS = [
    "id", "user_id", "name", "note", "net_balance",
    "net_balance_egp", "net_balance_usd", "created_at", "updated_at",
]

# Columns returned by transaction SELECT queries (loan-related)
_TX_COLS = [
    "id", "type", "amount", "currency", "account_id",
    "person_id", "note", "date", "balance_delta", "created_at",
]


def _row_to_person(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a person SQL row to a dict."""
    return {
        "id": str(row[0]),
        "user_id": str(row[1]),
        "name": row[2],
        "note": row[3],
        "net_balance": float(row[4]),
        "net_balance_egp": float(row[5]),
        "net_balance_usd": float(row[6]),
        "created_at": row[7],
        "updated_at": row[8],
    }


def _row_to_tx(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a loan transaction SQL row to a dict."""
    return {
        "id": str(row[0]),
        "type": row[1],
        "amount": float(row[2]),
        "currency": row[3],
        "account_id": str(row[4]),
        "person_id": str(row[5]) if row[5] else None,
        "note": row[6],
        "date": row[7],
        "balance_delta": float(row[8]),
        "created_at": row[9],
    }


class PersonService:
    """Business logic for people ledger — CRUD, loans, repayments, debt summary.

    Port of Go's PersonService. Each instance is scoped to a single user.
    Like Laravel's PersonService with user_id injection.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """List all persons for the user, ordered by name."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, name, note, net_balance,
                          net_balance_egp, net_balance_usd, created_at, updated_at
                   FROM persons WHERE user_id = %s ORDER BY name""",
                [self.user_id],
            )
            return [_row_to_person(row) for row in cursor.fetchall()]

    def get_by_id(self, person_id: str) -> dict[str, Any] | None:
        """Fetch a single person by ID. Returns None if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, user_id, name, note, net_balance,
                          net_balance_egp, net_balance_usd, created_at, updated_at
                   FROM persons WHERE id = %s AND user_id = %s""",
                [person_id, self.user_id],
            )
            row = cursor.fetchone()
        if not row:
            return None
        return _row_to_person(row)

    def create(self, name: str) -> dict[str, Any]:
        """Create a new person. Name is required."""
        name = name.strip()
        if not name:
            raise ValueError("name is required")
        person_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO persons (id, user_id, name)
                   VALUES (%s, %s, %s)
                   RETURNING id, user_id, name, note, net_balance,
                             net_balance_egp, net_balance_usd, created_at, updated_at""",
                [person_id, self.user_id, name],
            )
            row = cursor.fetchone()
        assert row is not None
        logger.info("person.created user=%s", self.user_id)
        return _row_to_person(row)

    def update(self, person_id: str, name: str, note: str | None = None) -> dict[str, Any] | None:
        """Update a person's name and optional note."""
        name = name.strip()
        if not name:
            raise ValueError("name is required")
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE persons SET name = %s, note = %s, updated_at = NOW()
                   WHERE id = %s AND user_id = %s
                   RETURNING id, user_id, name, note, net_balance,
                             net_balance_egp, net_balance_usd, created_at, updated_at""",
                [name, note, person_id, self.user_id],
            )
            row = cursor.fetchone()
        if not row:
            return None
        logger.info("person.updated user=%s person_id=%s", self.user_id, person_id)
        return _row_to_person(row)

    def delete(self, person_id: str) -> bool:
        """Delete a person. Returns True if deleted, False if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM persons WHERE id = %s AND user_id = %s",
                [person_id, self.user_id],
            )
            deleted: bool = cursor.rowcount > 0
        if deleted:
            logger.info("person.deleted user=%s person_id=%s", self.user_id, person_id)
        return deleted

    # -----------------------------------------------------------------------
    # Loan / Repayment (atomic balance updates)
    # -----------------------------------------------------------------------

    def _get_account(self, account_id: str) -> dict[str, Any]:
        """Fetch account record. Raises ValueError if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, name, currency, current_balance
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
        }

    def _balance_col_for_currency(self, currency: str) -> str:
        """Return the person balance column for the given currency."""
        if currency == "USD":
            return "net_balance_usd"
        return "net_balance_egp"

    def record_loan(
        self,
        person_id: str,
        account_id: str,
        amount: float,
        loan_type: str,
        note: str | None = None,
        tx_date: date | None = None,
    ) -> dict[str, Any]:
        """Record a loan (lend or borrow) and atomically update balances.

        Port of Go's PersonService.RecordLoan.

        loan_out: I lent money → account_delta = -amount, person_delta = +amount
        loan_in:  I borrowed   → account_delta = +amount, person_delta = -amount
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        if not person_id or not account_id:
            raise ValueError("person_id and account_id are required")
        if loan_type not in ("loan_out", "loan_in"):
            raise ValueError("type must be loan_out or loan_in")

        # Currency override from account (never trust form input)
        acc = self._get_account(account_id)
        currency = acc["currency"]

        if loan_type == "loan_out":
            account_delta = -amount
            person_delta = amount
        else:
            account_delta = amount
            person_delta = -amount

        tx_date = tx_date or date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()

        tx_id = str(uuid.uuid4())
        balance_col = self._balance_col_for_currency(currency)

        with transaction.atomic():
            with connection.cursor() as cursor:
                # 1. Create transaction
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        person_id, note, date, balance_delta)
                       VALUES (%s, %s, %s::transaction_type, %s, %s::currency_type,
                               %s, %s, %s, %s, %s)
                       RETURNING id, type, amount, currency, account_id,
                                 person_id, note, date, balance_delta, created_at""",
                    [
                        tx_id, self.user_id, loan_type, amount, currency,
                        account_id, person_id, note, tx_date, account_delta,
                    ],
                )
                row = cursor.fetchone()

                # 2. Update account balance
                cursor.execute(
                    """UPDATE accounts
                       SET current_balance = current_balance + %s, updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [account_delta, account_id, self.user_id],
                )

                # 3. Update person balance (currency-specific + legacy)
                cursor.execute(
                    f"""UPDATE persons
                       SET {balance_col} = {balance_col} + %s,
                           net_balance = net_balance + %s,
                           updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [person_delta, person_delta, person_id, self.user_id],
                )

        assert row is not None
        logger.info(
            "person.loan_recorded type=%s currency=%s user=%s",
            loan_type, currency, self.user_id,
        )
        return _row_to_tx(row)

    def record_repayment(
        self,
        person_id: str,
        account_id: str,
        amount: float,
        note: str | None = None,
        tx_date: date | None = None,
    ) -> dict[str, Any]:
        """Record a loan repayment and atomically update balances.

        Port of Go's PersonService.RecordRepayment.

        Direction determined by current balance:
        - Positive (they owe me): money enters my account → account_delta = +amount
        - Negative (I owe them): money leaves my account → account_delta = -amount
        """
        if amount <= 0:
            raise ValueError("amount must be positive")
        if not person_id or not account_id:
            raise ValueError("person_id and account_id are required")

        # Currency override from account
        acc = self._get_account(account_id)
        currency = acc["currency"]

        # Fetch current person balance to determine repayment direction
        person = self.get_by_id(person_id)
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        balance_col = self._balance_col_for_currency(currency)
        relevant_balance = person["net_balance_egp"] if currency != "USD" else person["net_balance_usd"]

        if relevant_balance > 0:
            # They owe me → they're paying back → money enters my account
            account_delta = amount
            person_delta = -amount
        else:
            # I owe them → I'm paying back → money leaves my account
            account_delta = -amount
            person_delta = amount

        tx_date = tx_date or date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()

        tx_id = str(uuid.uuid4())

        with transaction.atomic():
            with connection.cursor() as cursor:
                # 1. Create loan_repayment transaction
                cursor.execute(
                    """INSERT INTO transactions
                       (id, user_id, type, amount, currency, account_id,
                        person_id, note, date, balance_delta)
                       VALUES (%s, %s, 'loan_repayment'::transaction_type, %s,
                               %s::currency_type, %s, %s, %s, %s, %s)
                       RETURNING id, type, amount, currency, account_id,
                                 person_id, note, date, balance_delta, created_at""",
                    [
                        tx_id, self.user_id, amount, currency,
                        account_id, person_id, note, tx_date, account_delta,
                    ],
                )
                row = cursor.fetchone()

                # 2. Update account balance
                cursor.execute(
                    """UPDATE accounts
                       SET current_balance = current_balance + %s, updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [account_delta, account_id, self.user_id],
                )

                # 3. Update person balance (currency-specific + legacy)
                cursor.execute(
                    f"""UPDATE persons
                       SET {balance_col} = {balance_col} + %s,
                           net_balance = net_balance + %s,
                           updated_at = NOW()
                       WHERE id = %s AND user_id = %s""",
                    [person_delta, person_delta, person_id, self.user_id],
                )

        assert row is not None
        logger.info(
            "person.repayment_recorded currency=%s user=%s",
            currency, self.user_id,
        )
        return _row_to_tx(row)

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def get_person_transactions(self, person_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """Fetch loan/repayment transactions for a person."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, type, amount, currency, account_id,
                          person_id, note, date, balance_delta, created_at
                   FROM transactions
                   WHERE user_id = %s AND person_id = %s
                     AND type IN ('loan_out', 'loan_in', 'loan_repayment')
                   ORDER BY date DESC, created_at DESC
                   LIMIT %s""",
                [self.user_id, person_id, limit],
            )
            return [_row_to_tx(row) for row in cursor.fetchall()]

    def get_debt_summary(self, person_id: str) -> dict[str, Any] | None:
        """Compute full debt/loan summary for a person.

        Port of Go's PersonService.GetDebtSummary.

        Returns person info, per-currency breakdown, aggregate totals,
        progress percentages, and projected payoff date.
        """
        person = self.get_by_id(person_id)
        if not person:
            return None

        txns = self.get_person_transactions(person_id)

        # Per-currency tallies
        currency_map: dict[str, dict[str, float]] = {}
        total_lent = 0.0
        total_borrowed = 0.0
        total_repaid = 0.0
        repayment_dates: list[date] = []

        for tx in txns:
            cur = tx["currency"]
            if cur not in currency_map:
                currency_map[cur] = {"total_lent": 0.0, "total_borrowed": 0.0, "total_repaid": 0.0}
            cd = currency_map[cur]

            if tx["type"] == "loan_out":
                total_lent += tx["amount"]
                cd["total_lent"] += tx["amount"]
            elif tx["type"] == "loan_in":
                total_borrowed += tx["amount"]
                cd["total_borrowed"] += tx["amount"]
            elif tx["type"] == "loan_repayment":
                total_repaid += tx["amount"]
                cd["total_repaid"] += tx["amount"]
                if isinstance(tx["date"], date):
                    repayment_dates.append(tx["date"])

        # Build per-currency breakdown with progress
        by_currency: list[dict[str, Any]] = []

        # EGP first, then USD (match Go ordering)
        for cur in ["EGP", "USD"]:
            if cur not in currency_map:
                continue
            cd = currency_map[cur]
            net = person["net_balance_egp"] if cur == "EGP" else person["net_balance_usd"]
            total_debt = cd["total_lent"] + cd["total_borrowed"]
            progress = min((cd["total_repaid"] / total_debt) * 100, 100.0) if total_debt > 0 else 0.0
            by_currency.append({
                "currency": cur,
                "total_lent": cd["total_lent"],
                "total_borrowed": cd["total_borrowed"],
                "total_repaid": cd["total_repaid"],
                "net_balance": net,
                "progress_pct": progress,
            })

        # Aggregate progress
        total_debt_all = total_lent + total_borrowed
        progress_pct = min((total_repaid / total_debt_all) * 100, 100.0) if total_debt_all > 0 else 0.0

        # Projected payoff
        projected_payoff = None
        remaining = abs(person["net_balance_egp"]) + abs(person["net_balance_usd"])
        if len(repayment_dates) >= 2 and remaining > 0 and total_repaid > 0:
            avg_repayment = total_repaid / len(repayment_dates)
            if avg_repayment > 0:
                sorted_dates = sorted(repayment_dates)
                first = sorted_dates[0]
                last = sorted_dates[-1]
                total_days = (last - first).days
                if total_days > 0:
                    avg_interval_days = total_days / (len(repayment_dates) - 1)
                    payments_needed = remaining / avg_repayment
                    days_to_payoff = int(payments_needed * avg_interval_days)
                    projected_payoff = date.today() + timedelta(days=days_to_payoff)

        return {
            "person": person,
            "transactions": txns,
            "by_currency": by_currency,
            "total_lent": total_lent,
            "total_borrowed": total_borrowed,
            "total_repaid": total_repaid,
            "progress_pct": progress_pct,
            "projected_payoff": projected_payoff,
        }
