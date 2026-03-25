"""Dashboard accounts — institution loading, exchange rate, net worth computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.models import Account, ExchangeRateLog, Institution

if TYPE_CHECKING:
    from . import DashboardData

# Credit account types
CREDIT_TYPES = {"credit_card", "credit_limit"}

# Card type → display title
_CARD_TITLES: dict[str, str] = {
    "liquid_cash": "Liquid Cash",
    "credit_used": "Credit Used",
    "credit_available": "Credit Available",
    "debt": "Debt",
}


@dataclass
class InstitutionGroup:
    """Institution with its accounts for the expandable list."""

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

    institutions = Institution.objects.for_user(user_id).order_by(
        "display_order", "name"
    )

    for inst in institutions:
        accounts = (
            Account.objects.for_user(user_id)
            .filter(institution_id=inst.id)
            .order_by("display_order", "name")
        )

        account_list: list[dict[str, Any]] = []
        for row in accounts:
            acc = {
                "id": str(row.id),
                "name": row.name,
                "type": row.type,
                "currency": row.currency,
                "current_balance": float(row.current_balance),
                "credit_limit": float(row.credit_limit)
                if row.credit_limit is not None
                else None,
                "is_dormant": row.is_dormant,
                "metadata": row.metadata,
                "health_config": row.health_config,
                "display_order": row.display_order,
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
                institution_id=str(inst.id),
                name=inst.name,
                initial=inst.name[0] if inst.name else "?",
                color=inst.color or "",
                icon=inst.icon or "",
                accounts=account_list,
                total=inst_total,
            )
        )

    return all_accounts


def load_exchange_rate() -> float:
    """Load latest USD/EGP exchange rate.

    Exchange rates are global (no user_id filter) — shared across all users.
    """
    latest = ExchangeRateLog.objects.order_by("-date", "-created_at").first()
    if latest:
        return float(latest.rate)
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


def get_net_worth_breakdown(user_id: str, card_type: str) -> dict[str, Any]:
    """Return accounts contributing to a specific net worth sub-card.

    Like drilling down from a KPI card to its underlying data.

    Args:
        user_id: The authenticated user's ID.
        card_type: One of 'liquid_cash', 'credit_used', 'credit_available', 'debt'.

    Returns:
        {"title": str, "accounts": [{"name", "balance", "currency", ...}]}
    """
    if card_type not in _CARD_TITLES:
        raise ValueError(f"Unknown card type: {card_type}")

    # Load all accounts with institution info
    accounts = (
        Account.objects.for_user(user_id)
        .select_related("institution")
        .order_by("institution__name", "name")
    )

    result_accounts: list[dict[str, Any]] = []

    for acc in accounts:
        bal = float(acc.current_balance)
        inst = acc.institution
        inst_name = inst.name if inst else ""
        inst_icon = (inst.icon or "") if inst else ""

        row: dict[str, Any] = {
            "name": acc.name,
            "balance": bal,
            "currency": acc.currency,
            "institution_name": inst_name,
            "institution_icon": inst_icon,
        }

        if card_type == "liquid_cash":
            # Non-credit, non-dormant, positive balance
            if acc.type not in CREDIT_TYPES and not acc.is_dormant and bal > 0:
                result_accounts.append(row)

        elif card_type == "credit_used":
            # Credit accounts with negative balance (debt on card)
            if acc.type in CREDIT_TYPES and bal < 0:
                row["balance"] = abs(bal)  # show as positive "used" amount
                result_accounts.append(row)

        elif card_type == "credit_available":
            # Credit accounts with a limit
            if acc.type in CREDIT_TYPES:
                limit = float(acc.credit_limit) if acc.credit_limit else 0
                if limit > 0:
                    row["available"] = limit + bal  # limit + negative balance
                    row["credit_limit"] = limit
                    result_accounts.append(row)

        elif card_type == "debt":
            # All accounts with negative balance
            if bal < 0:
                result_accounts.append(row)

    # Sort: highest first for assets, most negative first for debt
    if card_type == "credit_available":
        result_accounts.sort(key=lambda a: a["available"], reverse=True)
    elif card_type in ("liquid_cash", "credit_used"):
        result_accounts.sort(key=lambda a: a["balance"], reverse=True)
    else:  # debt: most negative first
        result_accounts.sort(key=lambda a: a["balance"])

    return {"title": _CARD_TITLES[card_type], "accounts": result_accounts}
