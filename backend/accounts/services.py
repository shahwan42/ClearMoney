"""
Accounts & Institutions service layer — business logic and raw SQL queries.

Port of Go's service/account.go, service/institution.go, service/account_health.go,
and relevant repository queries from repository/account.go, repository/institution.go.

Like Django's fat-model or service-layer pattern. Uses raw SQL via connection.cursor()
because all models are managed=False and queries use window functions, enum casts,
and JSONB operations that don't map cleanly to the ORM.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import IntegrityError, connection

from core.billing import (
    get_billing_cycle_info,
    interest_free_remaining,
    parse_billing_cycle,
)

logger = logging.getLogger(__name__)

# Valid enum values — must match PostgreSQL enum types
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
    """Port of Go's requireTrimmedName — trims whitespace, error if empty."""
    trimmed = value.strip() if value else ""
    if not trimmed:
        raise ValueError(f"{field_name} is required")
    return trimmed


# ---------------------------------------------------------------------------
# InstitutionService
# ---------------------------------------------------------------------------


class InstitutionService:
    """Port of Go's InstitutionService + InstitutionRepo.

    Like Laravel's InstitutionService — validates input, executes SQL,
    logs mutations.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """All institutions ordered by display_order, name."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, type, color, icon, display_order, created_at, updated_at
                FROM institutions WHERE user_id = %s
                ORDER BY display_order, name
                """,
                [self.user_id],
            )
            return [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "type": row[2],
                    "color": row[3],
                    "icon": row[4],
                    "display_order": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
                for row in cursor.fetchall()
            ]

    def get_by_id(self, inst_id: str) -> dict[str, Any] | None:
        """Single institution by ID. Returns None if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, type, color, icon, display_order, created_at, updated_at
                FROM institutions WHERE id = %s AND user_id = %s
                """,
                [inst_id, self.user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "name": row[1],
                "type": row[2],
                "color": row[3],
                "icon": row[4],
                "display_order": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }

    def create(self, name: str, inst_type: str) -> dict[str, Any]:
        """Create institution. Validates name and type."""
        name = _require_trimmed_name(name, "institution name")
        if not inst_type:
            inst_type = "bank"
        if inst_type not in VALID_INSTITUTION_TYPES:
            raise ValueError(f"invalid institution type: {inst_type}")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO institutions (user_id, name, type, color, icon, display_order)
                VALUES (%s, %s, %s, NULL, NULL, 0)
                RETURNING id, created_at, updated_at
                """,
                [self.user_id, name, inst_type],
            )
            row = cursor.fetchone()
            assert row is not None
            logger.info("institution.created type=%s user=%s", inst_type, self.user_id)
            return {
                "id": str(row[0]),
                "name": name,
                "type": inst_type,
                "color": None,
                "icon": None,
                "display_order": 0,
                "created_at": row[1],
                "updated_at": row[2],
            }

    def update(self, inst_id: str, name: str, inst_type: str) -> dict[str, Any] | None:
        """Update institution name and type. Returns updated record or None."""
        name = _require_trimmed_name(name, "institution name")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE institutions
                SET name = %s, type = %s, updated_at = now()
                WHERE id = %s AND user_id = %s
                RETURNING id, name, type, color, icon, display_order, created_at, updated_at
                """,
                [name, inst_type, inst_id, self.user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            logger.info("institution.updated id=%s user=%s", inst_id, self.user_id)
            return {
                "id": str(row[0]),
                "name": row[1],
                "type": row[2],
                "color": row[3],
                "icon": row[4],
                "display_order": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }

    def delete(self, inst_id: str) -> bool:
        """Delete institution (cascades to accounts). Returns True if deleted."""
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM institutions WHERE id = %s AND user_id = %s",
                [inst_id, self.user_id],
            )
            deleted: bool = cursor.rowcount > 0
            if deleted:
                logger.info("institution.deleted id=%s user=%s", inst_id, self.user_id)
            return deleted

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of institution IDs."""
        with connection.cursor() as cursor:
            for i, inst_id in enumerate(ids):
                cursor.execute(
                    "UPDATE institutions SET display_order = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                    [i, inst_id, self.user_id],
                )
        logger.info("institution.reordered count=%d user=%s", len(ids), self.user_id)


# ---------------------------------------------------------------------------
# AccountService
# ---------------------------------------------------------------------------


class AccountService:
    """Port of Go's AccountService + AccountRepo + AccountHealthService.

    Handles CRUD, dormant toggle, reorder, health config, balance history,
    transaction list, and virtual account queries for the account detail page.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    # --- Read operations ---

    def get_all(self) -> list[dict[str, Any]]:
        """All accounts ordered by display_order, name."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, institution_id, name, type, currency, current_balance,
                    initial_balance, credit_limit, is_dormant, role_tags,
                    display_order, metadata, COALESCE(health_config, '{}'::jsonb),
                    created_at, updated_at
                FROM accounts WHERE user_id = %s
                ORDER BY display_order, name
                """,
                [self.user_id],
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_for_dropdown(
        self, *, include_balance: bool = False
    ) -> list[dict[str, Any]]:
        """Active (non-dormant) accounts for form dropdowns.

        Returns lightweight dicts with id, name, currency (and optionally
        current_balance). Much cheaper than get_all() for dropdown selects.
        """
        if include_balance:
            sql = """SELECT id, name, currency, current_balance
                     FROM accounts WHERE user_id = %s AND is_dormant = false
                     ORDER BY display_order, name"""
        else:
            sql = """SELECT id, name, currency
                     FROM accounts WHERE user_id = %s AND is_dormant = false
                     ORDER BY display_order, name"""
        with connection.cursor() as cursor:
            cursor.execute(sql, [self.user_id])
            rows = cursor.fetchall()
        if include_balance:
            return [
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "currency": r[2],
                    "current_balance": float(r[3]),
                }
                for r in rows
            ]
        return [{"id": str(r[0]), "name": r[1], "currency": r[2]} for r in rows]

    def get_by_id(self, account_id: str) -> dict[str, Any] | None:
        """Single account by ID. Returns None if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, institution_id, name, type, currency, current_balance,
                    initial_balance, credit_limit, is_dormant, role_tags,
                    display_order, metadata, COALESCE(health_config, '{}'::jsonb),
                    created_at, updated_at
                FROM accounts WHERE id = %s AND user_id = %s
                """,
                [account_id, self.user_id],
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def get_by_institution(self, institution_id: str) -> list[dict[str, Any]]:
        """Accounts for a specific institution."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, institution_id, name, type, currency, current_balance,
                    initial_balance, credit_limit, is_dormant, role_tags,
                    display_order, metadata, COALESCE(health_config, '{}'::jsonb),
                    created_at, updated_at
                FROM accounts WHERE institution_id = %s AND user_id = %s
                ORDER BY display_order, name
                """,
                [institution_id, self.user_id],
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

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

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO accounts (user_id, institution_id, name, type, currency,
                    current_balance, initial_balance, credit_limit, is_dormant,
                    role_tags, display_order, metadata)
                VALUES (%s, %s, %s, %s::account_type, %s::currency_type,
                    %s, %s, %s, false, '{}', 0, '{}'::jsonb)
                RETURNING id, created_at, updated_at
                """,
                [
                    self.user_id,
                    institution_id,
                    name,
                    acc_type,
                    currency,
                    initial_balance,
                    initial_balance,
                    credit_limit,
                ],
            )
            row = cursor.fetchone()
            assert row is not None

        logger.info(
            "account.created type=%s currency=%s user=%s",
            acc_type,
            currency,
            self.user_id,
        )
        return {
            "id": str(row[0]),
            "institution_id": institution_id,
            "name": name,
            "type": acc_type,
            "currency": currency,
            "current_balance": float(initial_balance),
            "initial_balance": float(initial_balance),
            "credit_limit": float(credit_limit) if credit_limit is not None else None,
            "is_dormant": False,
            "created_at": row[1],
            "updated_at": row[2],
        }

    def update(self, account_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update account fields (not balance). Returns updated record or None."""
        name = _require_trimmed_name(data.get("name", ""), "account name")
        acc_type = data.get("type", "current")
        currency = data.get("currency", "EGP")
        credit_limit = data.get("credit_limit")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE accounts
                SET name = %s, type = %s::account_type, currency = %s::currency_type,
                    credit_limit = %s, updated_at = now()
                WHERE id = %s AND user_id = %s
                RETURNING id, institution_id, name, type, currency, current_balance,
                    initial_balance, credit_limit, is_dormant, role_tags,
                    display_order, metadata, COALESCE(health_config, '{}'::jsonb),
                    created_at, updated_at
                """,
                [name, acc_type, currency, credit_limit, account_id, self.user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            logger.info("account.updated id=%s user=%s", account_id, self.user_id)
            return self._row_to_dict(row)

    def delete(self, account_id: str) -> str | None:
        """Delete account. Returns error message or None on success.

        Checks for installment FK RESTRICT, cleans up recurring rules (BUG-012).
        """
        try:
            with connection.cursor() as cursor:
                # Clean up recurring rules referencing this account (BUG-012)
                cursor.execute(
                    """
                    DELETE FROM recurring_rules
                    WHERE template_transaction->>'account_id' = %s AND user_id = %s
                    """,
                    [account_id, self.user_id],
                )
                # Delete the account (CASCADE to transactions, snapshots, etc.)
                cursor.execute(
                    "DELETE FROM accounts WHERE id = %s AND user_id = %s",
                    [account_id, self.user_id],
                )
                if cursor.rowcount == 0:
                    return "account not found"
                logger.info("account.deleted id=%s user=%s", account_id, self.user_id)
                return None
        except IntegrityError as e:
            error_str = str(e)
            if "23503" in error_str or "installment" in error_str.lower():
                return "Cannot delete: active installment plans exist"
            raise

    def toggle_dormant(self, account_id: str) -> bool:
        """Toggle dormant flag. Returns True if account found."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE accounts SET is_dormant = NOT is_dormant, updated_at = now()
                WHERE id = %s AND user_id = %s
                """,
                [account_id, self.user_id],
            )
            toggled: bool = cursor.rowcount > 0
            if toggled:
                logger.info(
                    "account.dormant_toggled id=%s user=%s", account_id, self.user_id
                )
            return toggled

    def reorder(self, ids: list[str]) -> None:
        """Update display_order for a list of account IDs."""
        with connection.cursor() as cursor:
            for i, account_id in enumerate(ids):
                cursor.execute(
                    "UPDATE accounts SET display_order = %s, updated_at = now() WHERE id = %s AND user_id = %s",
                    [i, account_id, self.user_id],
                )
        logger.info("account.reordered count=%d user=%s", len(ids), self.user_id)

    def update_health_config(self, account_id: str, config: dict[str, Any]) -> None:
        """Save health constraints to account's health_config JSONB."""
        config_json = json.dumps(config)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE accounts SET health_config = %s::jsonb, updated_at = now() WHERE id = %s AND user_id = %s",
                [config_json, account_id, self.user_id],
            )
        logger.info(
            "account.health_config_updated id=%s user=%s", account_id, self.user_id
        )

    # --- Account detail data ---

    def get_balance_history(self, account_id: str, days: int = 30) -> list[float]:
        """30-day balance history from account_snapshots for sparkline."""
        today = date.today()
        from_date = today - timedelta(days=days)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT balance FROM account_snapshots
                WHERE account_id = %s AND date >= %s AND date <= %s AND user_id = %s
                ORDER BY date ASC
                """,
                [account_id, from_date, today, self.user_id],
            )
            return [float(row[0]) for row in cursor.fetchall()]

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

        Port of Go's GetFilteredEnriched with AccountID filter.
        Uses window function for running balance calculation.
        """
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
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, target_amount, current_balance, icon, color,
                       is_archived, exclude_from_net_worth, display_order, account_id
                FROM virtual_accounts
                WHERE account_id = %s AND is_archived = false AND user_id = %s
                ORDER BY display_order, created_at
                """,
                [account_id, self.user_id],
            )
            result = []
            for row in cursor.fetchall():
                target = float(row[2]) if row[2] else 0.0
                current = float(row[3]) if row[3] else 0.0
                progress = (current / target * 100) if target > 0 else 0.0
                result.append(
                    {
                        "id": str(row[0]),
                        "name": row[1],
                        "target_amount": target,
                        "current_balance": current,
                        "icon": row[4],
                        "color": row[5],
                        "is_archived": row[6],
                        "exclude_from_net_worth": row[7],
                        "display_order": row[8],
                        "account_id": str(row[9]),
                        "progress_pct": min(100.0, progress),
                    }
                )
            return result

    def get_excluded_va_balance(self, account_id: str) -> float:
        """Total excluded VA balance for a bank account."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(current_balance), 0)
                FROM virtual_accounts
                WHERE account_id = %s AND exclude_from_net_worth = true
                    AND is_archived = false AND user_id = %s
                """,
                [account_id, self.user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    # --- Internal helpers ---

    def _row_to_dict(self, row: tuple[Any, ...]) -> dict[str, Any]:
        """Convert a SELECT row to an account dict."""
        balance = float(row[5])
        credit_limit = float(row[7]) if row[7] is not None else None
        acc_type = row[3]
        is_credit = acc_type in CREDIT_ACCOUNT_TYPES
        metadata = _parse_jsonb(row[11])
        health_config = _parse_jsonb(row[12])

        available_credit = None
        if is_credit and credit_limit is not None:
            available_credit = credit_limit + balance  # balance is negative for CC

        return {
            "id": str(row[0]),
            "institution_id": str(row[1]) if row[1] else None,
            "name": row[2],
            "type": acc_type,
            "currency": row[4],
            "current_balance": balance,
            "initial_balance": float(row[6]),
            "credit_limit": credit_limit,
            "is_dormant": row[8],
            "role_tags": row[9] or [],
            "display_order": row[10],
            "metadata": metadata,
            "health_config": health_config,
            "created_at": row[13],
            "updated_at": row[14],
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

    Port of Go's GetStatementData(). Returns None if no billing cycle configured.
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

    # Fetch transactions in billing period
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

    # Payment history
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
