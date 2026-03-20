"""Dashboard credit cards — CC summaries, utilization, and due date computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from .accounts import CREDIT_TYPES
from .helpers import _parse_jsonb

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class CreditCardSummary:
    """Credit card dashboard summary.
    Go equivalent: service.CreditCardSummary"""

    account_id: str
    account_name: str
    balance: float  # negative = owed
    credit_limit: float
    utilization: float  # 0-100 %
    utilization_pct: float  # same, for chart
    has_billing_cycle: bool
    due_date: date | None = None
    days_until_due: int = 0
    is_due_soon: bool = False


@dataclass
class DueSoonCard:
    """Credit card with upcoming due date (within 7 days).
    Go equivalent: service.DueSoonCard"""

    account_name: str
    due_date: date
    days_until_due: int
    balance: float


def _compute_due_date(statement_day: int, due_day: int, today: date) -> date:
    """Compute credit card due date from billing cycle metadata.

    Delegates to core.billing.compute_due_date — kept as a thin wrapper
    to avoid touching all call sites.
    """
    from core.billing import compute_due_date

    return compute_due_date(statement_day, due_day, today)


def compute_credit_card_summaries(
    data: DashboardData, all_accounts: list[dict[str, Any]], tz: ZoneInfo
) -> None:
    """Build credit card summaries with utilization and due dates."""
    now = datetime.now(tz)
    today = now.date()

    for acc in all_accounts:
        if acc["type"] not in CREDIT_TYPES:
            continue

        balance = acc["current_balance"]
        limit = acc["credit_limit"] or 0.0

        # Utilization: |balance| / limit * 100
        utilization = 0.0
        if limit > 0:
            used = -balance if balance < 0 else 0
            utilization = used / limit * 100

        cc = CreditCardSummary(
            account_id=acc["id"],
            account_name=acc["name"],
            balance=balance,
            credit_limit=limit,
            utilization=utilization,
            utilization_pct=utilization,
            has_billing_cycle=False,
        )

        # Parse billing cycle from metadata
        meta = _parse_jsonb(acc.get("metadata"))
        if meta:
            statement_day = meta.get("statement_day", 0)
            due_day = meta.get("due_day", 0)
            if statement_day and due_day:
                cc.has_billing_cycle = True
                due_date = _compute_due_date(statement_day, due_day, today)
                cc.due_date = due_date
                cc.days_until_due = (due_date - today).days
                cc.is_due_soon = 0 <= cc.days_until_due <= 7

                if cc.is_due_soon:
                    data.due_soon_cards.append(
                        DueSoonCard(
                            account_name=acc["name"],
                            due_date=due_date,
                            days_until_due=cc.days_until_due,
                            balance=balance,
                        )
                    )

        data.credit_cards.append(cc)
