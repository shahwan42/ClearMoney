"""Dashboard accounts — institution loading, exchange rate, net worth computation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from accounts.models import Account, Institution
from accounts.services import compute_net_worth as _compute_net_worth_impl
from exchange_rates.models import ExchangeRateLog
from people.models import Person

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
class CardStrategy:
    """Strategy for processing accounts belonging to a specific net-worth card type.

    Attributes:
        filter_fn: Returns True if an account should be included in this card's breakdown.
        transform_fn: Mutates the row dict before appending (e.g. abs-ify balance, add `available` field).
        sort_key: Which row field to sort by ('balance' or 'available').
        sort_reverse: Sort descending when True, ascending when False.
    """

    filter_fn: Callable[[Any, float], bool]
    transform_fn: Callable[[Any, float, dict[str, Any]], None]
    sort_key: str
    sort_reverse: bool


def _is_liquid_cash(acc: Any, bal: float) -> bool:
    """Include non-credit, non-dormant accounts with a positive balance."""
    return acc.type not in CREDIT_TYPES and not acc.is_dormant and bal > 0


def _transform_liquid_cash(acc: Any, bal: float, row: dict[str, Any]) -> None:
    """No transformation needed — balance is used as-is."""
    pass


def _is_credit_used(acc: Any, bal: float) -> bool:
    """Include credit accounts with a negative balance (amount owed)."""
    return acc.type in CREDIT_TYPES and bal < 0


def _transform_credit_used(acc: Any, bal: float, row: dict[str, Any]) -> None:
    """Show negative balance as a positive 'used' amount."""
    row["balance"] = abs(bal)


def _is_credit_available(acc: Any, bal: float) -> bool:
    """Include credit accounts that have an explicit credit limit."""
    if acc.type not in CREDIT_TYPES:
        return False
    limit = float(acc.credit_limit) if acc.credit_limit else 0
    return limit > 0


def _transform_credit_available(acc: Any, bal: float, row: dict[str, Any]) -> None:
    """Add `available` = credit_limit + current_balance (which is negative)."""
    limit = float(acc.credit_limit) if acc.credit_limit else 0
    row["available"] = limit + bal
    row["credit_limit"] = limit


def _is_debt(acc: Any, bal: float) -> bool:
    """Include any account with a negative balance."""
    return bal < 0


def _transform_debt(acc: Any, bal: float, row: dict[str, Any]) -> None:
    """No transformation needed — negative balance correctly represents debt."""
    pass


# Card-type → strategy mapping used by get_net_worth_breakdown().
# Each strategy encapsulates the filter, transform, and sort rules for one KPI card.
_STRATEGIES: dict[str, CardStrategy] = {
    "liquid_cash": CardStrategy(
        filter_fn=_is_liquid_cash,
        transform_fn=_transform_liquid_cash,
        sort_key="balance",
        sort_reverse=True,
    ),
    "credit_used": CardStrategy(
        filter_fn=_is_credit_used,
        transform_fn=_transform_credit_used,
        sort_key="balance",
        sort_reverse=True,
    ),
    "credit_available": CardStrategy(
        filter_fn=_is_credit_available,
        transform_fn=_transform_credit_available,
        sort_key="available",
        sort_reverse=True,
    ),
    "debt": CardStrategy(
        filter_fn=_is_debt,
        transform_fn=_transform_debt,
        sort_key="balance",
        sort_reverse=False,
    ),
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
    total: float  # sum of account balances in selected currency


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

        # Institution total: sum ONLY accounts matching selected_currency
        inst_total = sum(
            acc["current_balance"]
            for acc in account_list
            if acc["currency"] == data.selected_currency
        )

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
    """Compute net worth totals from loaded accounts.

    Delegates to accounts.services.compute_net_worth() for the core computation.
    """
    summary = _compute_net_worth_impl(all_accounts)
    data.net_worth = summary.net_worth
    data.totals_by_currency = summary.totals_by_currency
    data.cash_by_currency = summary.cash_by_currency
    data.debt_by_currency = summary.debt_by_currency
    data.credit_used_by_currency = summary.credit_used_by_currency
    data.credit_avail_by_currency = summary.credit_avail_by_currency
    data.credit_used = summary.credit_used
    data.credit_avail = summary.credit_avail
    data.debt_total = summary.debt_total

    # Recalculate institution totals for selected_currency
    for group in data.institutions:
        group.total = sum(
            acc["current_balance"]
            for acc in group.accounts
            if acc["currency"] == data.selected_currency
        )


def _get_people_debt(user_id: str, selected_currency: str) -> list[dict[str, Any]]:
    """Return people records where the user owes them money (negative balance).

    Filtered by selected_currency.
    """
    rows = []
    people = Person.objects.for_user(user_id).prefetch_related("currency_balances")
    for person in people.order_by("name"):
        balance_row = person.currency_balances.filter(
            currency_id=selected_currency
        ).first()
        balance = float(balance_row.balance) if balance_row else 0.0

        if balance < 0:
            rows.append(
                {
                    "name": person.name,
                    "balance": balance,
                    "currency": selected_currency,
                    "institution_name": "People",
                    "institution_icon": "👤",
                }
            )
    return rows


def get_net_worth_breakdown(
    user_id: str, card_type: str, selected_currency: str
) -> dict[str, Any]:
    """Return accounts contributing to a specific net worth sub-card.

    Like drilling down from a KPI card to its underlying data.
    Filtered by selected_currency.

    Args:
        user_id: The authenticated user's ID.
        card_type: One of 'liquid_cash', 'credit_used', 'credit_available', 'debt'.
        selected_currency: Filter by this currency.

    Returns:
        {"title": str, "accounts": [{"name", "balance", "currency", ...}]}
    """
    if card_type not in _CARD_TITLES:
        raise ValueError(f"Unknown card type: {card_type}")

    strategy = _STRATEGIES[card_type]

    accounts = (
        Account.objects.for_user(user_id)
        .filter(currency=selected_currency)
        .select_related("institution")
        .order_by("institution__name", "name")
    )

    result_accounts: list[dict[str, Any]] = []

    for acc in accounts:
        bal = float(acc.current_balance)
        if not strategy.filter_fn(acc, bal):
            continue

        inst = acc.institution
        row: dict[str, Any] = {
            "name": acc.name,
            "balance": bal,
            "currency": acc.currency,
            "institution_name": inst.name if inst else "",
            "institution_icon": (inst.icon or "") if inst else "",
        }
        strategy.transform_fn(acc, bal, row)
        result_accounts.append(row)

    if card_type == "debt":
        result_accounts.extend(_get_people_debt(user_id, selected_currency))

    result_accounts.sort(
        key=lambda a: a[strategy.sort_key], reverse=strategy.sort_reverse
    )

    return {"title": _CARD_TITLES[card_type], "accounts": result_accounts}
