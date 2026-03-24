"""
Accounts & Institutions service layer — business logic and ORM queries.

Like Django's fat-model or service-layer pattern. Uses the Django ORM with
``Model.objects.for_user(uid)`` for user-scoped queries. Two functions remain
as raw SQL: ``get_recent_transactions`` (window functions) and
``get_statement_data`` (complex period queries).
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, connection
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz

from core.billing import (
    get_billing_cycle_info,
    interest_free_remaining,
    parse_billing_cycle,
)
from core.models import (
    Account,
    AccountSnapshot,
    Institution,
    RecurringRule,
    VirtualAccount,
)

logger = logging.getLogger(__name__)

# Valid account types — validated in service layer
VALID_ACCOUNT_TYPES = {
    "savings",
    "current",
    "prepaid",
    "cash",
    "credit_card",
    "credit_limit",
}
CREDIT_ACCOUNT_TYPES = {"credit_card", "credit_limit"}
VALID_INSTITUTION_TYPES = {"bank", "fintech", "wallet"}
VALID_CURRENCIES = {"EGP", "USD"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_jsonb(value: Any) -> dict[str, Any] | None:
    """Parse a JSONB value that psycopg3 may return as a string or dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _require_trimmed_name(value: str, field_name: str) -> str:
    """Trim whitespace, raise ValueError if empty."""
    trimmed = value.strip() if value else ""
    if not trimmed:
        raise ValueError(f"{field_name} is required")
    return trimmed


# ---------------------------------------------------------------------------
# InstitutionService
# ---------------------------------------------------------------------------


class InstitutionService:
    """Like Laravel's InstitutionService — validates input, executes ORM queries,
    logs mutations.
    """

    # Columns fetched for institution dicts
    _FIELDS = (
        "id",
        "name",
        "type",
        "color",
        "icon",
        "display_order",
        "created_at",
        "updated_at",
    )

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Institution.objects.for_user(self.user_id)

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert a .values() row to an institution dict with stringified UUID."""
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "type": row["type"],
            "color": row["color"],
            "icon": row["icon"],
            "display_order": row["display_order"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_all(self) -> list[dict[str, Any]]:
        """All institutions ordered by display_order, name."""
        rows = self._qs().order_by("display_order", "name").values(*self._FIELDS)
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, inst_id: str) -> dict[str, Any] | None:
        """Single institution by ID. Returns None if not found."""
        row = self._qs().filter(id=inst_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def create(self, name: str, inst_type: str) -> dict[str, Any]:
        """Create institution. Validates name and type."""
        name = _require_trimmed_name(name, "institution name")
        if not inst_type:
            inst_type = "bank"
        if inst_type not in VALID_INSTITUTION_TYPES:
            raise ValueError(f"invalid institution type: {inst_type}")

        inst = Institution.objects.create(
            user_id=self.user_id,
            name=name,
            type=inst_type,
            color=None,
            icon=None,
            display_order=0,
        )
        logger.info("institution.created type=%s user=%s", inst_type, self.user_id)
        return {
            "id": str(inst.id),
            "name": inst.name,
            "type": inst.type,
            "color": inst.color,
            "icon": inst.icon,
            "display_order": inst.display_order,
            "created_at": inst.created_at,
            "updated_at": inst.updated_at,
        }

    def update(self, inst_id: str, name: str, inst_type: str) -> dict[str, Any] | None:
        """Update institution name and type. Returns updated record or None."""
        name = _require_trimmed_name(name, "institution name")
        now = django_tz.now()
        updated = (
            self._qs()
            .filter(id=inst_id)
            .update(
                name=name,
                type=inst_type,
                updated_at=now,
            )
        )
        if not updated:
            return None
        logger.info("institution.updated id=%s user=%s", inst_id, self.user_id)
        row = self._qs().filter(id=inst_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def delete(self, inst_id: str) -> bool:
        """Delete institution (cascades to accounts). Returns True if deleted."""
        count, _ = self._qs().filter(id=inst_id).delete()
        deleted = bool(count > 0)
        if deleted:
            logger.info("institution.deleted id=%s user=%s", inst_id, self.user_id)
        return deleted

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of institution IDs."""
        now = django_tz.now()
        for i, inst_id in enumerate(ids):
            self._qs().filter(id=inst_id).update(display_order=i, updated_at=now)
        logger.info("institution.reordered count=%d user=%s", len(ids), self.user_id)


# ---------------------------------------------------------------------------
# AccountService
# ---------------------------------------------------------------------------


class AccountService:
    """Handles CRUD, dormant toggle, reorder, health config, balance history,
    transaction list, and virtual account queries for the account detail page.
    """

    # Columns fetched for full account dicts
    _FIELDS = (
        "id",
        "institution_id",
        "name",
        "type",
        "currency",
        "current_balance",
        "initial_balance",
        "credit_limit",
        "is_dormant",
        "role_tags",
        "display_order",
        "metadata",
        "health_config",
        "created_at",
        "updated_at",
    )

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Account.objects.for_user(self.user_id)

    # --- Read operations ---

    def get_all(self) -> list[dict[str, Any]]:
        """All accounts ordered by display_order, name."""
        rows = self._qs().order_by("display_order", "name").values(*self._FIELDS)
        return [self._row_to_dict(row) for row in rows]

    def get_for_dropdown(
        self, *, include_balance: bool = False
    ) -> list[dict[str, Any]]:
        """Active (non-dormant) accounts for form dropdowns.

        Returns lightweight dicts with id, name, currency (and optionally
        current_balance). Much cheaper than get_all() for dropdown selects.
        """
        qs = self._qs().filter(is_dormant=False).order_by("display_order", "name")
        if include_balance:
            rows = qs.values("id", "name", "currency", "current_balance")
            return [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "currency": r["currency"],
                    "current_balance": float(r["current_balance"]),
                }
                for r in rows
            ]
        rows = qs.values("id", "name", "currency")
        return [
            {"id": str(r["id"]), "name": r["name"], "currency": r["currency"]}
            for r in rows
        ]

    def get_by_id(self, account_id: str) -> dict[str, Any] | None:
        """Single account by ID. Returns None if not found."""
        row = self._qs().filter(id=account_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def get_by_institution(self, institution_id: str) -> list[dict[str, Any]]:
        """Accounts for a specific institution."""
        rows = (
            self._qs()
            .filter(institution_id=institution_id)
            .order_by("display_order", "name")
            .values(*self._FIELDS)
        )
        return [self._row_to_dict(row) for row in rows]

    # --- Write operations ---

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create account. Validates name, institution, credit limit rules."""
        name = _require_trimmed_name(data.get("name", ""), "account name")
        institution_id = data.get("institution_id", "")
        if not institution_id:
            raise ValueError("institution_id is required")

        acc_type = data.get("type", "current")
        if acc_type not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"invalid account type: {acc_type}")

        currency = data.get("currency", "EGP")
        if currency not in VALID_CURRENCIES:
            raise ValueError(f"invalid currency: {currency}")

        credit_limit = data.get("credit_limit")
        if acc_type in CREDIT_ACCOUNT_TYPES and credit_limit is None:
            raise ValueError(f"credit_limit is required for {acc_type} accounts")
        if acc_type == "cash" and credit_limit is not None:
            raise ValueError("cash accounts cannot have a credit limit")

        initial_balance = data.get("initial_balance", 0.0)

        account = Account.objects.create(
            user_id=self.user_id,
            institution_id=institution_id,
            name=name,
            type=acc_type,
            currency=currency,
            current_balance=initial_balance,
            initial_balance=initial_balance,
            credit_limit=credit_limit,
            is_dormant=False,
            role_tags=[],
            display_order=0,
            metadata={},
        )

        logger.info(
            "account.created type=%s currency=%s user=%s",
            acc_type,
            currency,
            self.user_id,
        )
        return {
            "id": str(account.id),
            "institution_id": institution_id,
            "name": name,
            "type": acc_type,
            "currency": currency,
            "current_balance": float(initial_balance),
            "initial_balance": float(initial_balance),
            "credit_limit": float(credit_limit) if credit_limit is not None else None,
            "is_dormant": False,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def update(self, account_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update account fields (not balance). Returns updated record or None."""
        name = _require_trimmed_name(data.get("name", ""), "account name")
        acc_type = data.get("type", "current")
        currency = data.get("currency", "EGP")
        credit_limit = data.get("credit_limit")
        now = django_tz.now()

        updated = (
            self._qs()
            .filter(id=account_id)
            .update(
                name=name,
                type=acc_type,
                currency=currency,
                credit_limit=credit_limit,
                updated_at=now,
            )
        )
        if not updated:
            return None
        logger.info("account.updated id=%s user=%s", account_id, self.user_id)
        row = self._qs().filter(id=account_id).values(*self._FIELDS).first()
        return self._row_to_dict(row) if row else None

    def delete(self, account_id: str) -> str | None:
        """Delete account. Returns error message or None on success.

        Cleans up recurring rules referencing this account (BUG-012).
        """
        try:
            # Clean up recurring rules referencing this account (BUG-012)
            RecurringRule.objects.for_user(self.user_id).filter(
                template_transaction__account_id=account_id
            ).delete()
            # Delete the account (CASCADE to transactions, snapshots, etc.)
            count, _ = self._qs().filter(id=account_id).delete()
            if count == 0:
                return "account not found"
            logger.info("account.deleted id=%s user=%s", account_id, self.user_id)
            return None
        except IntegrityError:
            raise

    def toggle_dormant(self, account_id: str) -> bool:
        """Toggle dormant flag. Returns True if account found."""
        # Fetch-toggle-save pattern because queryset .update() can't do NOT on a field
        account = self._qs().filter(id=account_id).first()
        if account is None:
            return False
        account.is_dormant = not account.is_dormant
        account.updated_at = django_tz.now()
        account.save(update_fields=["is_dormant", "updated_at"])
        logger.info("account.dormant_toggled id=%s user=%s", account_id, self.user_id)
        return True

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of account IDs."""
        now = django_tz.now()
        for i, account_id in enumerate(ids):
            self._qs().filter(id=account_id).update(display_order=i, updated_at=now)
        logger.info("account.reordered count=%d user=%s", len(ids), self.user_id)

    def update_health_config(self, account_id: str, config: dict[str, Any]) -> None:
        """Save health constraints to account's health_config JSONB."""
        now = django_tz.now()
        self._qs().filter(id=account_id).update(health_config=config, updated_at=now)
        logger.info(
            "account.health_config_updated id=%s user=%s", account_id, self.user_id
        )

    # --- Account detail data ---

    def get_balance_history(self, account_id: str, days: int = 30) -> list[float]:
        """30-day balance history from account_snapshots for sparkline."""
        today = date.today()
        from_date = today - timedelta(days=days)
        rows = (
            AccountSnapshot.objects.for_user(self.user_id)
            .filter(account_id=account_id, date__gte=from_date, date__lte=today)
            .order_by("date")
            .values_list("balance", flat=True)
        )
        return [float(bal) for bal in rows]

    def get_utilization_history(
        self, account_id: str, credit_limit: float, days: int = 30
    ) -> list[float]:
        """30-day utilization trend from balance history. Returns list of 0-100 values."""
        history = self.get_balance_history(account_id, days)
        if not history or credit_limit <= 0:
            return []
        return [min(100.0, max(0.0, (-bal / credit_limit) * 100)) for bal in history]

    def get_recent_transactions(
        self, account_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Recent transactions with running balance for account detail page.

        Uses window function for running balance calculation — kept as raw SQL.
        """
        # Raw SQL — window function computes running balance by subtracting
        # cumulative balance_deltas from the account's current_balance
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sub.id, sub.type, sub.amount, sub.currency, sub.account_id,
                    sub.category_id, sub.date, sub.note, sub.tags,
                    sub.balance_delta, sub.created_at,
                    sub.account_name, sub.category_name, sub.category_icon,
                    sub.running_balance
                FROM (
                    SELECT t.id, t.type, t.amount, t.currency, t.account_id,
                        t.category_id, t.date, t.note, t.tags,
                        t.balance_delta, t.created_at,
                        a.name AS account_name,
                        c.name AS category_name, c.icon AS category_icon,
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
                    WHERE t.user_id = %s AND t.account_id = %s
                ) sub
                ORDER BY sub.date DESC, sub.created_at DESC
                LIMIT %s
                """,
                [self.user_id, account_id, limit],
            )
            return [
                {
                    "id": str(row[0]),
                    "type": row[1],
                    "amount": float(row[2]),
                    "currency": row[3],
                    "account_id": str(row[4]),
                    "category_id": str(row[5]) if row[5] else None,
                    "date": row[6],
                    "note": row[7],
                    "tags": row[8] or [],
                    "balance_delta": float(row[9]),
                    "created_at": row[10],
                    "account_name": row[11],
                    "category_name": row[12],
                    "category_icon": row[13],
                    "running_balance": float(row[14]),
                }
                for row in cursor.fetchall()
            ]

    def get_linked_virtual_accounts(self, account_id: str) -> list[dict[str, Any]]:
        """Virtual accounts linked to this bank account (non-archived)."""
        rows = (
            VirtualAccount.objects.for_user(self.user_id)
            .filter(account_id=account_id, is_archived=False)
            .order_by("display_order", "created_at")
            .values(
                "id",
                "name",
                "target_amount",
                "current_balance",
                "icon",
                "color",
                "is_archived",
                "exclude_from_net_worth",
                "display_order",
                "account_id",
            )
        )
        result = []
        for row in rows:
            target = float(row["target_amount"]) if row["target_amount"] else 0.0
            current = float(row["current_balance"]) if row["current_balance"] else 0.0
            progress = (current / target * 100) if target > 0 else 0.0
            result.append(
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "target_amount": target,
                    "current_balance": current,
                    "icon": row["icon"],
                    "color": row["color"],
                    "is_archived": row["is_archived"],
                    "exclude_from_net_worth": row["exclude_from_net_worth"],
                    "display_order": row["display_order"],
                    "account_id": str(row["account_id"]),
                    "progress_pct": min(100.0, progress),
                }
            )
        return result

    def get_excluded_va_balance(self, account_id: str) -> float:
        """Total excluded VA balance for a bank account."""
        result = (
            VirtualAccount.objects.for_user(self.user_id)
            .filter(
                account_id=account_id,
                exclude_from_net_worth=True,
                is_archived=False,
            )
            .aggregate(total=Coalesce(Sum("current_balance"), Decimal("0")))
        )
        return float(result["total"])

    # --- Internal helpers ---

    def _row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert a .values() row to an account dict with computed fields."""
        balance = float(row["current_balance"])
        credit_limit = (
            float(row["credit_limit"]) if row["credit_limit"] is not None else None
        )
        acc_type = row["type"]
        is_credit = acc_type in CREDIT_ACCOUNT_TYPES
        metadata = _parse_jsonb(row["metadata"])
        health_config = (
            _parse_jsonb(row["health_config"]) if row["health_config"] else {}
        )

        available_credit = None
        if is_credit and credit_limit is not None:
            available_credit = credit_limit + balance  # balance is negative for CC

        inst_id = row["institution_id"]
        return {
            "id": str(row["id"]),
            "institution_id": str(inst_id) if inst_id else None,
            "name": row["name"],
            "type": acc_type,
            "currency": row["currency"],
            "current_balance": balance,
            "initial_balance": float(row["initial_balance"]),
            "credit_limit": credit_limit,
            "is_dormant": row["is_dormant"],
            "role_tags": row["role_tags"] or [],
            "display_order": row["display_order"],
            "metadata": metadata,
            "health_config": health_config,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            # Computed fields
            "is_credit_type": is_credit,
            "available_credit": available_credit,
        }


# ---------------------------------------------------------------------------
# Statement data
# ---------------------------------------------------------------------------


def get_statement_data(
    account: dict[str, Any], user_id: str, tz: ZoneInfo, period_str: str = ""
) -> dict[str, Any] | None:
    """Full CC statement: transactions, balances, interest-free period, payment history.

    Returns None if no billing cycle configured.
    Kept as raw SQL — complex period queries with multiple aggregations.
    """
    metadata = account.get("metadata")
    cycle = parse_billing_cycle(metadata)
    if not cycle:
        return None

    statement_day, due_day = cycle
    today = date.today()
    info = get_billing_cycle_info(statement_day, due_day, today)

    # If a specific period is requested (YYYY-MM), recompute for that month
    if period_str:
        try:
            parts = period_str.split("-")
            year = int(parts[0])
            month = int(parts[1])
            # Use statement_day of that month as reference
            ref_date = date(year, month, min(statement_day, 28))
            info = get_billing_cycle_info(statement_day, due_day, ref_date)
        except (ValueError, IndexError):
            pass  # Use current period on parse failure

    # Raw SQL — simple date-range filter, but kept consistent with raw SQL pattern
    # used throughout the statement module
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, type, amount, currency, account_id, date, note,
                   balance_delta, created_at
            FROM transactions
            WHERE account_id = %s AND date >= %s AND date <= %s AND user_id = %s
            ORDER BY date DESC, created_at DESC
            """,
            [account["id"], info.period_start, info.period_end, user_id],
        )
        transactions = [
            {
                "id": str(row[0]),
                "type": row[1],
                "amount": float(row[2]),
                "currency": row[3],
                "account_id": str(row[4]),
                "date": row[5],
                "note": row[6],
                "balance_delta": float(row[7]),
                "created_at": row[8],
            }
            for row in cursor.fetchall()
        ]

    # Calculate totals
    total_spending = 0.0
    total_payments = 0.0
    for tx in transactions:
        if tx["balance_delta"] < 0:
            total_spending += -tx["balance_delta"]
        else:
            total_payments += tx["balance_delta"]

    closing_balance = account["current_balance"]
    opening_balance = closing_balance
    for tx in transactions:
        opening_balance -= tx["balance_delta"]

    # Interest-free period
    remaining, is_urgent = interest_free_remaining(info.period_end, today)

    # Raw SQL — payment history includes counter_account_id match (both legs
    # of transfers/income that credit this CC), which is simpler in raw SQL
    payment_history: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, type, amount, currency, account_id, date, note,
                   balance_delta, created_at
            FROM transactions
            WHERE (account_id = %s OR counter_account_id = %s)
              AND balance_delta > 0
              AND type IN ('income', 'transfer')
              AND user_id = %s
            ORDER BY date DESC, created_at DESC
            LIMIT 10
            """,
            [account["id"], account["id"], user_id],
        )
        payment_history = [
            {
                "id": str(row[0]),
                "type": row[1],
                "amount": float(row[2]),
                "currency": row[3],
                "account_id": str(row[4]),
                "date": row[5],
                "note": row[6],
                "balance_delta": float(row[7]),
                "created_at": row[8],
            }
            for row in cursor.fetchall()
        ]

    return {
        "account": account,
        "billing_cycle": info,
        "transactions": transactions,
        "opening_balance": opening_balance,
        "total_spending": total_spending,
        "total_payments": total_payments,
        "closing_balance": closing_balance,
        "interest_free_days": 55,
        "interest_free_remain": remaining,
        "interest_free_urgent": is_urgent,
        "payment_history": payment_history,
    }
