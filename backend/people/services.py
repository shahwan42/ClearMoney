"""
Person service layer — business logic for people ledger (loans and debts).

Like Laravel's PersonService — validates input, executes atomic operations,
logs mutations.

CRITICAL INVARIANTS:
- Currency is ALWAYS overridden from the account record (never trust form input).
- All balance updates are atomic (wrapped in transaction.atomic()).
- Amount is always positive; deltas hold the signed impact.
- Net balance convention: positive = they owe me, negative = I owe them.
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F
from django.utils import timezone as django_tz

from core.models import Account, Person, Transaction

logger = logging.getLogger(__name__)


def _person_to_dict(p: dict[str, Any]) -> dict[str, Any]:
    """Convert a .values() row to the expected dict format."""
    return {
        "id": str(p["id"]),
        "user_id": str(p["user_id"]),
        "name": p["name"],
        "note": p["note"],
        "net_balance": float(p["net_balance"]),
        "net_balance_egp": float(p["net_balance_egp"]),
        "net_balance_usd": float(p["net_balance_usd"]),
        "created_at": p["created_at"],
        "updated_at": p["updated_at"],
    }


def _person_instance_to_dict(p: Person) -> dict[str, Any]:
    """Convert a Person model instance to a dict."""
    return {
        "id": str(p.id),
        "user_id": str(p.user_id),
        "name": p.name,
        "note": p.note,
        "net_balance": float(p.net_balance),
        "net_balance_egp": float(p.net_balance_egp),
        "net_balance_usd": float(p.net_balance_usd),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _tx_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a transaction .values() row to a dict."""
    return {
        "id": str(row["id"]),
        "type": row["type"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "account_id": str(row["account_id"]),
        "person_id": str(row["person_id"]) if row["person_id"] else None,
        "note": row["note"],
        "date": row["date"],
        "balance_delta": float(row["balance_delta"]),
        "created_at": row["created_at"],
    }


def _tx_instance_to_dict(tx: Transaction) -> dict[str, Any]:
    """Convert a Transaction model instance to a dict."""
    return {
        "id": str(tx.id),
        "type": tx.type,
        "amount": float(tx.amount),
        "currency": tx.currency,
        "account_id": str(tx.account_id),
        "person_id": str(tx.person_id) if tx.person_id else None,
        "note": tx.note,
        "date": tx.date,
        "balance_delta": float(tx.balance_delta),
        "created_at": tx.created_at,
    }


# Fields returned in person dicts
_PERSON_FIELDS = (
    "id",
    "user_id",
    "name",
    "note",
    "net_balance",
    "net_balance_egp",
    "net_balance_usd",
    "created_at",
    "updated_at",
)

# Fields returned in transaction dicts
_TX_FIELDS = (
    "id",
    "type",
    "amount",
    "currency",
    "account_id",
    "person_id",
    "note",
    "date",
    "balance_delta",
    "created_at",
)


class PersonService:
    """Business logic for people ledger — CRUD, loans, repayments, debt summary.

    Each instance is scoped to a single user.
    Like Laravel's PersonService with user_id injection.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Person.objects.for_user(self.user_id)

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """List all persons for the user, ordered by name."""
        rows = self._qs().order_by("name").values(*_PERSON_FIELDS)
        return [_person_to_dict(row) for row in rows]

    def get_by_id(self, person_id: str) -> dict[str, Any] | None:
        """Fetch a single person by ID. Returns None if not found."""
        row = self._qs().filter(id=person_id).values(*_PERSON_FIELDS).first()
        if not row:
            return None
        return _person_to_dict(row)

    def create(self, name: str) -> dict[str, Any]:
        """Create a new person. Name is required."""
        name = name.strip()
        if not name:
            raise ValueError("name is required")
        person = Person.objects.create(
            id=uuid.uuid4(),
            user_id=self.user_id,
            name=name,
        )
        logger.info("person.created user=%s", self.user_id)
        return _person_instance_to_dict(person)

    def update(
        self, person_id: str, name: str, note: str | None = None
    ) -> dict[str, Any] | None:
        """Update a person's name and optional note."""
        name = name.strip()
        if not name:
            raise ValueError("name is required")
        updated = (
            self._qs()
            .filter(id=person_id)
            .update(name=name, note=note, updated_at=django_tz.now())
        )
        if not updated:
            return None
        logger.info("person.updated user=%s person_id=%s", self.user_id, person_id)
        return self.get_by_id(person_id)

    def delete(self, person_id: str) -> bool:
        """Delete a person. Returns True if deleted, False if not found."""
        count, _ = self._qs().filter(id=person_id).delete()
        deleted: bool = count > 0
        if deleted:
            logger.info("person.deleted user=%s person_id=%s", self.user_id, person_id)
        return deleted

    # -----------------------------------------------------------------------
    # Loan / Repayment (atomic balance updates)
    # -----------------------------------------------------------------------

    def _get_account(self, account_id: str) -> dict[str, Any]:
        """Fetch account record. Raises ValueError if not found."""
        row = (
            Account.objects.for_user(self.user_id)
            .filter(id=account_id)
            .values("id", "name", "currency", "current_balance")
            .first()
        )
        if not row:
            raise ValueError(f"Account not found: {account_id}")
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "currency": row["currency"],
            "current_balance": float(row["current_balance"]),
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

        loan_out: I lent money -> account_delta = -amount, person_delta = +amount
        loan_in:  I borrowed   -> account_delta = +amount, person_delta = -amount
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

        tx_id = uuid.uuid4()
        balance_col = self._balance_col_for_currency(currency)

        with transaction.atomic():
            # 1. Create transaction
            tx = Transaction.objects.create(
                id=tx_id,
                user_id=self.user_id,
                type=loan_type,
                amount=amount,
                currency=currency,
                account_id=account_id,
                person_id=person_id,
                note=note,
                date=tx_date,
                balance_delta=account_delta,
            )

            # 2. Atomic F() update — avoids race conditions on concurrent balance changes
            Account.objects.for_user(self.user_id).filter(id=account_id).update(
                current_balance=F("current_balance") + Decimal(str(account_delta)),
                updated_at=django_tz.now(),
            )

            # 3. Dynamic column via **kwargs — balance_col resolves to
            # "net_balance_egp" or "net_balance_usd" based on account currency
            Person.objects.for_user(self.user_id).filter(id=person_id).update(
                **{balance_col: F(balance_col) + Decimal(str(person_delta))},
                net_balance=F("net_balance") + Decimal(str(person_delta)),
                updated_at=django_tz.now(),
            )

        logger.info(
            "person.loan_recorded type=%s currency=%s user=%s",
            loan_type,
            currency,
            self.user_id,
        )
        return _tx_instance_to_dict(tx)

    def record_repayment(
        self,
        person_id: str,
        account_id: str,
        amount: float,
        note: str | None = None,
        tx_date: date | None = None,
    ) -> dict[str, Any]:
        """Record a loan repayment and atomically update balances.

        Direction determined by current balance:
        - Positive (they owe me): money enters my account -> account_delta = +amount
        - Negative (I owe them): money leaves my account -> account_delta = -amount
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
        relevant_balance = (
            person["net_balance_egp"]
            if currency != "USD"
            else person["net_balance_usd"]
        )

        if relevant_balance > 0:
            # They owe me -> they're paying back -> money enters my account
            account_delta = amount
            person_delta = -amount
        else:
            # I owe them -> I'm paying back -> money leaves my account
            account_delta = -amount
            person_delta = amount

        tx_date = tx_date or date.today()
        if isinstance(tx_date, str):
            tx_date = datetime.strptime(tx_date, "%Y-%m-%d").date()

        tx_id = uuid.uuid4()

        with transaction.atomic():
            # 1. Create loan_repayment transaction
            tx = Transaction.objects.create(
                id=tx_id,
                user_id=self.user_id,
                type="loan_repayment",
                amount=amount,
                currency=currency,
                account_id=account_id,
                person_id=person_id,
                note=note,
                date=tx_date,
                balance_delta=account_delta,
            )

            # 2. Atomic F() update — avoids race conditions on concurrent balance changes
            Account.objects.for_user(self.user_id).filter(id=account_id).update(
                current_balance=F("current_balance") + Decimal(str(account_delta)),
                updated_at=django_tz.now(),
            )

            # 3. Dynamic column via **kwargs — balance_col resolves to
            # "net_balance_egp" or "net_balance_usd" based on account currency
            Person.objects.for_user(self.user_id).filter(id=person_id).update(
                **{balance_col: F(balance_col) + Decimal(str(person_delta))},
                net_balance=F("net_balance") + Decimal(str(person_delta)),
                updated_at=django_tz.now(),
            )

        logger.info(
            "person.repayment_recorded currency=%s user=%s",
            currency,
            self.user_id,
        )
        return _tx_instance_to_dict(tx)

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def get_person_transactions(
        self, person_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Fetch loan/repayment transactions for a person."""
        rows = (
            Transaction.objects.for_user(self.user_id)
            .filter(
                person_id=person_id,
                type__in=["loan_out", "loan_in", "loan_repayment"],
            )
            .order_by("-date", "-created_at")
            .values(*_TX_FIELDS)[:limit]
        )
        return [_tx_to_dict(row) for row in rows]

    def get_debt_summary(self, person_id: str) -> dict[str, Any] | None:
        """Compute full debt/loan summary for a person.

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
                currency_map[cur] = {
                    "total_lent": 0.0,
                    "total_borrowed": 0.0,
                    "total_repaid": 0.0,
                }
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
            net = (
                person["net_balance_egp"] if cur == "EGP" else person["net_balance_usd"]
            )
            total_debt = cd["total_lent"] + cd["total_borrowed"]
            progress = (
                min((cd["total_repaid"] / total_debt) * 100, 100.0)
                if total_debt > 0
                else 0.0
            )
            by_currency.append(
                {
                    "currency": cur,
                    "total_lent": cd["total_lent"],
                    "total_borrowed": cd["total_borrowed"],
                    "total_repaid": cd["total_repaid"],
                    "net_balance": net,
                    "progress_pct": progress,
                }
            )

        # Aggregate progress
        total_debt_all = total_lent + total_borrowed
        progress_pct = (
            min((total_repaid / total_debt_all) * 100, 100.0)
            if total_debt_all > 0
            else 0.0
        )

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
