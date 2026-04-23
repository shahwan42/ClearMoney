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
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F
from django.utils import timezone as django_tz

from accounts.models import Account
from auth_app.currency import get_supported_currencies
from core.serializers import serialize_instance, serialize_row
from people.models import Person, PersonCurrencyBalance
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def _person_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a .values() row to the expected dict format."""
    person = serialize_row(
        row,
        {
            "id": "id",
            "user_id": "user_id",
            "name": "name",
            "note": "note",
            "net_balance": "net_balance",
            "net_balance_egp": "net_balance_egp",
            "net_balance_usd": "net_balance_usd",
            "created_at": "created_at",
            "updated_at": "updated_at",
        },
    )
    return _with_balance_payload(person, [])


def _person_instance_to_dict(p: Person) -> dict[str, Any]:
    """Convert a Person model instance to a dict."""
    person = serialize_instance(p, _PERSON_FIELDS)
    return _with_balance_payload(person, [])


def _with_balance_payload(
    person: dict[str, Any], balances: list[dict[str, Any]]
) -> dict[str, Any]:
    """Attach generalized balances and compatibility-derived helpers."""
    normalized = _normalize_balance_rows(person, balances)
    person["balances"] = normalized
    person["balance_map"] = {
        balance["currency"]: balance["balance"] for balance in normalized
    }
    person["has_open_balance"] = any(balance["balance"] != 0 for balance in normalized)
    return person


def _normalize_balance_rows(
    person: dict[str, Any], balances: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Normalize balance rows and fall back to legacy fields when needed."""
    seen = {balance["currency"] for balance in balances}
    normalized = list(balances)
    for currency, field in (("EGP", "net_balance_egp"), ("USD", "net_balance_usd")):
        legacy_balance = float(person.get(field, 0) or 0)
        if currency not in seen and legacy_balance != 0:
            normalized.append({"currency": currency, "balance": legacy_balance})
    return sorted(normalized, key=_currency_sort_key)


def _currency_sort_key(balance: dict[str, Any]) -> tuple[int, str]:
    """Sort balances by registry order, then alphabetically."""
    supported_codes = [currency.code for currency in get_supported_currencies()]
    code = balance["currency"]
    if code in supported_codes:
        return (supported_codes.index(code), code)
    return (len(supported_codes), code)


def _serialize_balance_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a balance .values() row to a dict."""
    return serialize_row(
        dict(row),
        {
            "person_id": "person_id",
            "currency": "currency_id",
            "balance": "balance",
        },
    )


def _tx_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a transaction .values() row to a dict."""
    return serialize_row(
        row,
        {
            "id": "id",
            "type": "type",
            "amount": "amount",
            "currency": "currency",
            "account_id": "account_id",
            "person_id": "person_id",
            "note": "note",
            "date": "date",
            "balance_delta": "balance_delta",
            "created_at": "created_at",
        },
    )


def _tx_instance_to_dict(tx: Transaction) -> dict[str, Any]:
    """Convert a Transaction model instance to a dict."""
    return serialize_instance(tx, _TX_FIELDS)


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
        rows = list(self._qs().order_by("name").values(*_PERSON_FIELDS))
        person_ids = [row["id"] for row in rows]
        balances_by_person = self._get_balances_by_person(person_ids)
        return [
            _with_balance_payload(
                _person_to_dict(row),
                balances_by_person.get(str(row["id"]), []),
            )
            for row in rows
        ]

    def get_by_id(self, person_id: str) -> dict[str, Any] | None:
        """Fetch a single person by ID. Returns None if not found."""
        row = self._qs().filter(id=person_id).values(*_PERSON_FIELDS).first()
        if not row:
            return None
        balances = self._get_balances_by_person([row["id"]]).get(str(row["id"]), [])
        return _with_balance_payload(_person_to_dict(row), balances)

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

    def _get_balances_by_person(
        self, person_ids: list[str] | list[uuid.UUID]
    ) -> dict[str, list[dict[str, Any]]]:
        """Return generalized balance rows grouped by person."""
        if not person_ids:
            return {}
        rows = (
            PersonCurrencyBalance.objects.filter(person_id__in=person_ids)
            .order_by("currency_id")
            .values("person_id", "currency_id", "balance")
        )
        balances_by_person: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            balance = _serialize_balance_row(row)
            balances_by_person.setdefault(balance["person_id"], []).append(
                {
                    "currency": balance["currency"],
                    "balance": balance["balance"],
                }
            )
        return balances_by_person

    def _get_person_balance_value(self, person_id: str, currency: str) -> float:
        """Return the current balance for one person/currency pair."""
        balance = (
            PersonCurrencyBalance.objects.filter(person_id=person_id, currency_id=currency)
            .values_list("balance", flat=True)
            .first()
        )
        return float(balance) if balance is not None else 0.0

    def _update_person_balance(
        self, person_id: str, currency: str, delta: Decimal, *, now: Any
    ) -> None:
        """Atomically apply a delta to generalized and compatibility balances."""
        balance_row, _ = PersonCurrencyBalance.objects.get_or_create(
            person_id=person_id,
            currency_id=currency,
            defaults={"balance": Decimal("0")},
        )
        PersonCurrencyBalance.objects.filter(id=balance_row.id).update(
            balance=F("balance") + delta,
            updated_at=now,
        )

        legacy_updates: dict[str, Any] = {
            "net_balance": F("net_balance") + delta,
            "updated_at": now,
        }
        if currency == "EGP":
            legacy_updates["net_balance_egp"] = F("net_balance_egp") + delta
        elif currency == "USD":
            legacy_updates["net_balance_usd"] = F("net_balance_usd") + delta
        Person.objects.for_user(self.user_id).filter(id=person_id).update(**legacy_updates)

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
        person_delta_decimal = Decimal(str(person_delta))
        account_delta_decimal = Decimal(str(account_delta))
        now = django_tz.now()

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
                current_balance=F("current_balance") + account_delta_decimal,
                updated_at=now,
            )

            self._update_person_balance(
                person_id,
                currency,
                person_delta_decimal,
                now=now,
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

        relevant_balance = self._get_person_balance_value(person_id, currency)

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
        person_delta_decimal = Decimal(str(person_delta))
        account_delta_decimal = Decimal(str(account_delta))
        now = django_tz.now()

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
                current_balance=F("current_balance") + account_delta_decimal,
                updated_at=now,
            )

            self._update_person_balance(
                person_id,
                currency,
                person_delta_decimal,
                now=now,
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

    def _compute_currency_breakdown(
        self, txns: list[dict[str, Any]], person: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Compute per-currency loan tallies and progress for a person's transactions.

        Accumulates totals (lent/borrowed/repaid) per currency from the transaction
        list, then builds a sorted-by-currency breakdown with progress percentages.

        Args:
            txns: List of transaction dicts (from get_person_transactions).
            person: Person dict with generalized `balances`.

        Returns:
            List of per-currency dicts, each containing currency, total_lent,
            total_borrowed, total_repaid, net_balance, and progress_pct.
            Ordered by currency registry display order.
        """
        currency_map: dict[str, dict[str, float]] = {}
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
                cd["total_lent"] += tx["amount"]
            elif tx["type"] == "loan_in":
                cd["total_borrowed"] += tx["amount"]
            elif tx["type"] == "loan_repayment":
                cd["total_repaid"] += tx["amount"]

        for balance in person["balances"]:
            currency_map.setdefault(
                balance["currency"],
                {
                    "total_lent": 0.0,
                    "total_borrowed": 0.0,
                    "total_repaid": 0.0,
                },
            )

        by_currency: list[dict[str, Any]] = []
        balance_map = person["balance_map"]
        for cur in sorted(currency_map, key=lambda code: _currency_sort_key({"currency": code, "balance": 0.0})):
            cd = currency_map[cur]
            net = balance_map.get(cur, 0.0)
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
        return by_currency

    def _compute_aggregate_progress(
        self, total_lent: float, total_borrowed: float, total_repaid: float
    ) -> float:
        """Compute aggregate repayment progress percentage across all currencies.

        Computes total debt (lent + borrowed) and expresses repaid amount as a
        capped percentage. Caps at 100% to handle over-repayments gracefully.

        Args:
            total_lent: Sum of all loan_out amounts across all currencies.
            total_borrowed: Sum of all loan_in amounts across all currencies.
            total_repaid: Sum of all loan_repayment amounts across all currencies.

        Returns:
            Progress percentage from 0.0 to 100.0, or 0.0 when total debt is zero.
        """
        total_debt_all = total_lent + total_borrowed
        return (
            min((total_repaid / total_debt_all) * 100, 100.0)
            if total_debt_all > 0
            else 0.0
        )

    def _compute_projected_payoff(
        self, repayment_dates: list[date], remaining: float, total_repaid: float
    ) -> date | None:
        """Project the estimated payoff date based on repayment history.

        Calculates the average repayment interval from the sorted repayment dates,
        then extrapolates how many payments are needed to clear the remaining balance.

        Requires at least two repayment events to establish an interval. Returns
        None if inputs are insufficient or if the average interval is invalid.

        Args:
            repayment_dates: Sorted list of repayment transaction dates.
            remaining: Absolute sum of net balances across all currencies.
            total_repaid: Total amount repaid to date.

        Returns:
            Estimated payoff date (date.today() + projected days), or None if
            insufficient data to project.
        """
        if len(repayment_dates) < 2 or remaining <= 0 or total_repaid <= 0:
            return None
        avg_repayment = total_repaid / len(repayment_dates)
        if avg_repayment <= 0:
            return None
        sorted_dates = sorted(repayment_dates)
        first, last = sorted_dates[0], sorted_dates[-1]
        total_days = (last - first).days
        if total_days <= 0:
            return None
        avg_interval_days = total_days / (len(repayment_dates) - 1)
        payments_needed = remaining / avg_repayment
        days_to_payoff = int(payments_needed * avg_interval_days)
        return date.today() + timedelta(days=days_to_payoff)

    def get_debt_summary(self, person_id: str) -> dict[str, Any] | None:
        """Compute full debt/loan summary for a person.

        Returns person info, per-currency breakdown, aggregate totals,
        progress percentages, and projected payoff date.

        Delegates to three sub-functions:
          - _compute_currency_breakdown: per-currency tallies and progress
          - _compute_aggregate_progress: overall repayment percentage
          - _compute_projected_payoff: estimated payoff date from repayment cadence

        Returns:
            Dict with keys: person, transactions, by_currency, total_lent,
            total_borrowed, total_repaid, progress_pct, projected_payoff.
            Returns None if person_id does not exist.
        """
        person = self.get_by_id(person_id)
        if not person:
            return None

        txns = self.get_person_transactions(person_id)

        total_lent = 0.0
        total_borrowed = 0.0
        total_repaid = 0.0
        repayment_dates: list[date] = []

        for tx in txns:
            if tx["type"] == "loan_out":
                total_lent += tx["amount"]
            elif tx["type"] == "loan_in":
                total_borrowed += tx["amount"]
            elif tx["type"] == "loan_repayment":
                total_repaid += tx["amount"]
                if isinstance(tx["date"], date):
                    repayment_dates.append(tx["date"])

        by_currency = self._compute_currency_breakdown(txns, person)
        progress_pct = self._compute_aggregate_progress(
            total_lent, total_borrowed, total_repaid
        )
        remaining = sum(abs(balance["balance"]) for balance in person["balances"])
        projected_payoff = self._compute_projected_payoff(
            repayment_dates, remaining, total_repaid
        )

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
