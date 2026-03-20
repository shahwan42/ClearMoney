"""Dashboard accounts — institution loading, exchange rate, net worth computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db import connection

if TYPE_CHECKING:
    from . import DashboardData

# Credit account types — matches Go's IsCreditType()
CREDIT_TYPES = {"credit_card", "credit_limit"}


@dataclass
class InstitutionGroup:
    """Institution with its accounts for the expandable list.
    Go equivalent: service.InstitutionGroup"""

    institution_id: str
    name: str
    initial: str  # first char of name, for avatar
    color: str
    icon: str
    accounts: list[dict[str, Any]]
    total: float  # sum of account balances (USD converted to EGP)


def load_institutions_with_accounts(
    user_id: str, data: DashboardData
) -> list[dict[str, Any]]:
    """Load institutions with nested accounts. Returns flat list of all accounts."""
    all_accounts: list[dict[str, Any]] = []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, type, color, icon, display_order
            FROM institutions WHERE user_id = %s
            ORDER BY display_order, name
            """,
            [user_id],
        )
        institutions = cursor.fetchall()

        for (
            inst_id,
            inst_name,
            inst_type,
            color,
            icon,
            display_order,
        ) in institutions:
            cursor.execute(
                """
                SELECT id, name, type, currency, current_balance, credit_limit,
                       is_dormant, metadata, COALESCE(health_config, '{}'::jsonb),
                       display_order
                FROM accounts WHERE institution_id = %s AND user_id = %s
                ORDER BY display_order, name
                """,
                [str(inst_id), user_id],
            )
            accounts = cursor.fetchall()

            account_list: list[dict[str, Any]] = []
            for row in accounts:
                acc = {
                    "id": str(row[0]),
                    "name": row[1],
                    "type": row[2],
                    "currency": row[3],
                    "current_balance": float(row[4]),
                    "credit_limit": float(row[5]) if row[5] is not None else None,
                    "is_dormant": row[6],
                    "metadata": row[7],
                    "health_config": row[8],
                    "display_order": row[9],
                }
                account_list.append(acc)
                all_accounts.append(acc)

            # Institution total: convert USD to EGP for consistent display
            inst_total = 0.0
            for acc in account_list:
                if acc["currency"] == "USD" and data.exchange_rate > 0:
                    inst_total += acc["current_balance"] * data.exchange_rate
                else:
                    inst_total += acc["current_balance"]

            data.institutions.append(
                InstitutionGroup(
                    institution_id=str(inst_id),
                    name=inst_name,
                    initial=inst_name[0] if inst_name else "?",
                    color=color or "",
                    icon=icon or "",
                    accounts=account_list,
                    total=inst_total,
                )
            )

    return all_accounts


def load_exchange_rate() -> float:
    """Load latest USD/EGP exchange rate.

    Exchange rates are global (no user_id filter) — shared across all users.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rate FROM exchange_rate_log ORDER BY date DESC, created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return float(row[0])
    return 0.0


def compute_net_worth(data: DashboardData, all_accounts: list[dict[str, Any]]) -> None:
    """Compute net worth totals from loaded accounts."""
    for acc in all_accounts:
        balance = acc["current_balance"]
        data.net_worth += balance

        if acc["currency"] == "USD":
            data.usd_total += balance
        elif acc["currency"] == "EGP":
            data.egp_total += balance

        if acc["type"] in CREDIT_TYPES:
            data.credit_used += balance  # negative for CCs (display negates)
            limit = acc["credit_limit"]
            if limit is not None and limit > 0:
                # available = limit + balance (balance is negative, so this subtracts debt)
                data.credit_avail += limit + balance
        else:
            data.cash_total += balance

    # Recalculate institution totals now that exchange rate is loaded
    if data.exchange_rate > 0:
        for group in data.institutions:
            total = 0.0
            for acc in group.accounts:
                if acc["currency"] == "USD":
                    total += acc["current_balance"] * data.exchange_rate
                else:
                    total += acc["current_balance"]
            group.total = total
