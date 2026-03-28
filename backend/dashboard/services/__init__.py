"""
Dashboard service package — aggregates data from 10+ sources for the home page.

This is the most complex service in ClearMoney. It pulls data from institutions,
accounts, transactions, exchange rates, people, investments, snapshots, virtual accounts,
budgets, health checks, and credit card billing cycles.

Like Django's TemplateView.get_context_data() that aggregates from many QuerySets
and services into a single context dictionary. A few queries use raw SQL via
connection.cursor() for window functions and CTEs that don't map cleanly to the ORM.
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

# Re-export all dataclasses so external code can do:
#   from dashboard.services import DashboardService, DueSoonCard, HealthWarning
from .accounts import (
    InstitutionGroup,
    compute_net_worth,
    load_exchange_rate,
    load_institutions_with_accounts,
)
from .activity import (
    PeopleCurrencySummary,
    StreakInfo,
    TransactionRow,
    load_people_summary,
    load_recent_transactions,
    load_streak,
)  # StreakInfo, TransactionRow, load_recent_transactions, load_streak re-exported from transactions.services
from .credit_cards import (
    CreditCardSummary,
    DueSoonCard,
    _compute_due_date,
    compute_credit_card_summaries,
)
from .sparklines import (
    load_account_sparklines,
    load_net_worth_by_currency,
    load_net_worth_history,
)
from .spending import CurrencySpending, SpendingVelocity, compute_spending_comparison
from .widgets import (
    HealthWarning,
    load_budgets_with_spending,
    load_excluded_va_total,
    load_health_warnings,
    load_investments_total,
    load_virtual_accounts,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Main class + data container
    "DashboardService",
    "DashboardData",
    # Dataclasses
    "InstitutionGroup",
    "CurrencySpending",
    "SpendingVelocity",
    "CreditCardSummary",
    "DueSoonCard",
    "StreakInfo",
    "HealthWarning",
    "PeopleCurrencySummary",
    "TransactionRow",
    # Helpers (used by tests)
    "_compute_due_date",
]


@dataclass
class DashboardData:
    """All dashboard data — passed to template as a single context dict."""

    # Net worth
    net_worth: float = 0.0
    net_worth_egp: float = 0.0
    egp_total: float = 0.0
    usd_total: float = 0.0
    cash_total: float = 0.0
    credit_used: float = 0.0
    credit_avail: float = 0.0
    debt_total: float = 0.0
    exchange_rate: float = 0.0
    usd_in_egp: float = 0.0

    # Institutions & accounts
    institutions: list[InstitutionGroup] = field(default_factory=list)

    # People
    people_owed_to_me: float = 0.0
    people_i_owe: float = 0.0
    people_by_currency: list[PeopleCurrencySummary] = field(default_factory=list)
    has_people_activity: bool = False

    # Investments
    investment_total: float = 0.0

    # Credit cards
    due_soon_cards: list[DueSoonCard] = field(default_factory=list)
    credit_cards: list[CreditCardSummary] = field(default_factory=list)

    # Streak
    streak: StreakInfo = field(default_factory=StreakInfo)

    # Transactions
    recent_transactions: list[TransactionRow] = field(default_factory=list)

    # Sparklines
    net_worth_history: list[float] = field(default_factory=list)
    net_worth_change: float = 0.0
    net_worth_history_by_currency: dict[str, list[float]] = field(default_factory=dict)
    account_sparklines: dict[str, list[float]] = field(default_factory=dict)

    # Spending
    spending_by_currency: list[CurrencySpending] = field(default_factory=list)
    spending_velocity: SpendingVelocity = field(
        default_factory=lambda: SpendingVelocity(0, 0, 0, 0, 0, "green")
    )

    # Virtual accounts
    virtual_accounts: list[dict[str, Any]] = field(default_factory=list)
    excluded_va_total: float = 0.0

    # Budgets
    budgets: list[dict[str, Any]] = field(default_factory=list)

    # Health
    health_warnings: list[HealthWarning] = field(default_factory=list)


class DashboardService:
    """Aggregates all dashboard data from 10+ database sources.

    Delegates to module-level functions in sub-modules (accounts, credit_cards,
    spending, activity, widgets, sparklines). Each sub-module handles one data
    domain and is independently testable. The public get_dashboard() orchestrates
    them with best-effort error handling.

    Like Laravel's DashboardController calling 10+ repositories,
    or Django's TemplateView.get_context_data() pulling from many QuerySets.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_dashboard(self) -> dict[str, Any]:
        """Compute the full dashboard data. Called once per page load.

        Returns a flat dict suitable for Django template rendering.
        Each data source is loaded independently — failures are logged and skipped.
        """
        data = DashboardData()

        # 1. Core: institutions + accounts (hard requirement)
        try:
            all_accounts = self._load_institutions_with_accounts(data)
        except Exception:
            logger.exception("dashboard: failed to load institutions")
            all_accounts = []

        # 2. Exchange rate (needed for USD->EGP conversion)
        try:
            data.exchange_rate = self._load_exchange_rate()
        except Exception:
            logger.warning("dashboard: failed to load exchange rate")

        # 3. Compute net worth from loaded accounts
        self._compute_net_worth(data, all_accounts)

        # 4. Credit card summaries
        try:
            self._compute_credit_card_summaries(data, all_accounts)
        except Exception:
            logger.warning("dashboard: failed to compute CC summaries")

        # 5. Excluded virtual account balances
        try:
            excluded = self._load_excluded_va_total()
            if excluded > 0:
                data.excluded_va_total = excluded
                data.net_worth -= excluded
                data.egp_total -= excluded
                data.cash_total -= excluded
        except Exception:
            logger.warning("dashboard: failed to load excluded VA total")

        # 6. Recompute net worth EGP after VA exclusion
        if data.exchange_rate > 0:
            data.usd_in_egp = data.usd_total * data.exchange_rate
            data.net_worth_egp = (data.net_worth - data.usd_total) + data.usd_in_egp

        # 7. People summary
        try:
            self._load_people_summary(data)
        except Exception:
            logger.warning("dashboard: failed to load people")

        # 8. Virtual accounts
        try:
            data.virtual_accounts = self._load_virtual_accounts()
        except Exception:
            logger.warning("dashboard: failed to load virtual accounts")

        # 9. Investments
        try:
            data.investment_total = self._load_investments_total()
        except Exception:
            logger.warning("dashboard: failed to load investments")

        # 10. Streak
        try:
            data.streak = self._load_streak()
        except Exception:
            logger.warning("dashboard: failed to load streak")

        # 11. Recent transactions
        try:
            data.recent_transactions = self.load_recent_transactions(limit=10)
        except Exception:
            logger.warning("dashboard: failed to load recent transactions")

        # 12. Net worth sparkline
        try:
            self._load_net_worth_history(data)
        except Exception:
            logger.warning("dashboard: failed to load net worth history")

        # 13. Per-currency sparkline
        try:
            self._load_net_worth_by_currency(data)
        except Exception:
            logger.warning("dashboard: failed to load per-currency history")

        # 14. Per-account sparklines
        try:
            self._load_account_sparklines(data, all_accounts)
        except Exception:
            logger.warning("dashboard: failed to load account sparklines")

        # 15. Health warnings
        try:
            data.health_warnings = self._load_health_warnings(all_accounts)
        except Exception:
            logger.warning("dashboard: failed to load health warnings")

        # 16. Budgets
        try:
            data.budgets = self._load_budgets_with_spending()
        except Exception:
            logger.warning("dashboard: failed to load budgets")

        # 17. Spending comparison + velocity
        try:
            self._compute_spending_comparison(data)
        except Exception:
            logger.warning("dashboard: failed to compute spending comparison")

        # Compute template-helper fields
        result = data.__dict__
        # is_good for net worth change: positive change is good
        result["net_worth_change_is_good"] = data.net_worth_change > 0
        # is_good for spending: lower spending is good (negative change = good)
        for cs in data.spending_by_currency:
            cs.change_is_good = cs.change < 0  # type: ignore[attr-defined]
            for cat in cs.top_categories:
                cat["change_is_good"] = cat["change"] < 0
        return result

    # ------------------------------------------------------------------
    # Delegate methods — thin wrappers around module-level functions
    # ------------------------------------------------------------------

    def _load_institutions_with_accounts(
        self, data: DashboardData
    ) -> list[dict[str, Any]]:
        return load_institutions_with_accounts(self.user_id, data)

    def _load_exchange_rate(self) -> float:
        return load_exchange_rate()

    def _compute_net_worth(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
        compute_net_worth(data, all_accounts)

    def _compute_credit_card_summaries(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
        compute_credit_card_summaries(data, all_accounts, self.tz)

    def _load_excluded_va_total(self) -> float:
        return load_excluded_va_total(self.user_id)

    def _load_people_summary(self, data: DashboardData) -> None:
        load_people_summary(self.user_id, data)

    def _load_virtual_accounts(self) -> list[dict[str, Any]]:
        return load_virtual_accounts(self.user_id)

    def _load_investments_total(self) -> float:
        return load_investments_total(self.user_id)

    def _load_streak(self) -> StreakInfo:
        return load_streak(self.user_id, self.tz)

    def load_recent_transactions(self, limit: int = 10) -> list[TransactionRow]:
        """Public method — called by the partial view directly."""
        return load_recent_transactions(self.user_id, limit)

    def _load_net_worth_history(self, data: DashboardData) -> None:
        load_net_worth_history(self.user_id, data, self.tz)

    def _load_net_worth_by_currency(self, data: DashboardData) -> None:
        load_net_worth_by_currency(self.user_id, data, self.tz)

    def _load_account_sparklines(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
        load_account_sparklines(self.user_id, data, all_accounts, self.tz)

    def _load_health_warnings(
        self, all_accounts: list[dict[str, Any]]
    ) -> list[HealthWarning]:
        return load_health_warnings(self.user_id, all_accounts, self.tz)

    def _load_budgets_with_spending(self) -> list[dict[str, Any]]:
        return load_budgets_with_spending(self.user_id, self.tz)

    def _compute_spending_comparison(self, data: DashboardData) -> None:
        compute_spending_comparison(self.user_id, data, self.tz)
