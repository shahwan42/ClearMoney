"""Dashboard activity — people summary, streak tracking, recent transactions.

Streak and recent transaction logic is owned by the transactions service.
This module re-exports their types for backward compatibility and handles
people summary (which is dashboard-specific aggregation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from auth_app.currency import get_supported_currencies
from people.models import Person

# Re-export from transactions service (canonical location)
from transactions.services.activity import (
    StreakInfo,  # noqa: F401
    TransactionRow,  # noqa: F401
    load_recent_transactions,  # noqa: F401
    load_streak,  # noqa: F401
)

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class PeopleCurrencySummary:
    """Per-currency people ledger totals."""

    currency: str
    owed_to_me: float = 0.0
    i_owe: float = 0.0

    @property
    def has_activity(self) -> bool:
        return self.owed_to_me != 0 or self.i_owe != 0


def _currency_sort_key(currency: str) -> tuple[int, str]:
    """Sort currencies by registry display order, then alphabetically."""
    supported_codes = [row.code for row in get_supported_currencies()]
    if currency in supported_codes:
        return (supported_codes.index(currency), currency)
    return (len(supported_codes), currency)


def load_people_summary(user_id: str, data: DashboardData) -> None:
    """Load people ledger grouped by currency."""
    summaries: dict[str, PeopleCurrencySummary] = {}
    debt_by_currency: dict[str, float] = {}
    people = Person.objects.for_user(user_id).prefetch_related("currency_balances")

    for person in people:
        balances = {
            row.currency_id: float(row.balance)
            for row in person.currency_balances.all()
        }
        for currency, balance in balances.items():
            summary = summaries.setdefault(
                currency,
                PeopleCurrencySummary(currency=currency),
            )
            if balance > 0:
                summary.owed_to_me += balance
            elif balance < 0:
                summary.i_owe += balance
                debt_by_currency[currency] = debt_by_currency.get(currency, 0.0) + abs(
                    balance
                )

    data.people_by_currency = [
        summary
        for currency, summary in sorted(
            summaries.items(), key=lambda item: _currency_sort_key(item[0])
        )
        if summary.has_activity
    ]
    data.debt_by_currency = {
        currency: debt_by_currency.get(currency, 0.0)
        + data.debt_by_currency.get(currency, 0.0)
        for currency in sorted(
            set(debt_by_currency.keys()) | set(data.debt_by_currency.keys()),
            key=_currency_sort_key,
        )
    }
    data.selected_people_summary = next(
        (
            summary
            for summary in data.people_by_currency
            if summary.currency == data.selected_currency
        ),
        None,
    )
    if data.selected_people_summary is not None:
        data.people_owed_to_me = data.selected_people_summary.owed_to_me
        data.people_i_owe = data.selected_people_summary.i_owe
    data.selected_debt = data.debt_by_currency.get(data.selected_currency, 0.0)
    data.has_people_activity = data.selected_people_summary is not None


# load_streak and load_recent_transactions are re-exported from
# transactions.services.activity (see imports above).
