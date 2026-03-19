"""
Dashboard service — aggregates data from 10+ sources for the home page.

Port of Go's DashboardService (internal/service/dashboard.go, 752 lines).
This is the most complex service in ClearMoney. It pulls data from institutions,
accounts, transactions, exchange rates, people, investments, snapshots, virtual accounts,
budgets, health checks, and credit card billing cycles.

Like Django's TemplateView.get_context_data() that aggregates from many QuerySets
and services into a single context dictionary. Uses raw SQL via connection.cursor()
because the queries involve window functions, CTEs, and PostgreSQL enum casts that
don't map cleanly to the ORM (and all models are managed=False).
"""

import json
import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses — typed equivalents of Go's dashboard structs
# ---------------------------------------------------------------------------


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


@dataclass
class CurrencySpending:
    """Per-currency month-over-month spending comparison.
    Go equivalent: service.CurrencySpending"""

    currency: str
    this_month: float
    last_month: float
    change: float  # % change (positive = spending more)
    top_categories: list[dict[str, Any]]


@dataclass
class SpendingVelocity:
    """Spending pace relative to last month.
    Go equivalent: service.SpendingVelocity"""

    percentage: float  # current spend / last month total × 100
    days_elapsed: int
    days_total: int
    days_left: int
    day_progress: float  # % of month elapsed
    status: str  # "green", "amber", "red"


@dataclass
class CreditCardSummary:
    """Credit card dashboard summary.
    Go equivalent: service.CreditCardSummary"""

    account_id: str
    account_name: str
    balance: float  # negative = owed
    credit_limit: float
    utilization: float  # 0–100 %
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


@dataclass
class StreakInfo:
    """Habit tracking — consecutive days with transactions.
    Go equivalent: service.StreakInfo"""

    consecutive_days: int = 0
    weekly_count: int = 0
    active_today: bool = False


@dataclass
class HealthWarning:
    """Violated health constraint on an account.
    Go equivalent: service.AccountHealthWarning"""

    account_name: str
    account_id: str
    rule: str  # "min_balance" or "min_monthly_deposit"
    message: str


@dataclass
class PeopleCurrencySummary:
    """Per-currency people ledger totals.
    Go equivalent: service.PeopleCurrencySummary"""

    currency: str
    owed_to_me: float = 0.0
    i_owe: float = 0.0


@dataclass
class TransactionRow:
    """Recent transaction display row with running balance.
    Go equivalent: repository.TransactionDisplayRow"""

    id: str
    type: str
    amount: float
    currency: str
    date: date
    note: str | None
    balance_delta: float
    account_name: str
    running_balance: float


@dataclass
class DashboardData:
    """All dashboard data — passed to template as a single context dict.
    Go equivalent: service.DashboardData"""

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


# Credit account types — matches Go's IsCreditType()
CREDIT_TYPES = {"credit_card", "credit_limit"}


class DashboardService:
    """Aggregates all dashboard data from 10+ database sources.

    Port of Go's DashboardService. Uses raw SQL via connection.cursor().
    Each private method handles one data domain and is independently testable.
    The public get_dashboard() orchestrates them with best-effort error handling.

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

        # 2. Exchange rate (needed for USD→EGP conversion)
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
    # Private query methods
    # ------------------------------------------------------------------

    def _load_institutions_with_accounts(
        self, data: DashboardData
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
                [self.user_id],
            )
            institutions = cursor.fetchall()

            for inst_id, inst_name, inst_type, color, icon, display_order in institutions:
                cursor.execute(
                    """
                    SELECT id, name, type, currency, current_balance, credit_limit,
                           is_dormant, metadata, COALESCE(health_config, '{}'::jsonb),
                           display_order
                    FROM accounts WHERE institution_id = %s AND user_id = %s
                    ORDER BY display_order, name
                    """,
                    [str(inst_id), self.user_id],
                )
                accounts = cursor.fetchall()

                account_list = []
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

    def _load_exchange_rate(self) -> float:
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

    def _compute_net_worth(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
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

    def _compute_credit_card_summaries(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
        """Build credit card summaries with utilization and due dates."""
        now = datetime.now(self.tz)
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
                    due_date = _compute_due_date(
                        statement_day, due_day, today
                    )
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

    def _load_excluded_va_total(self) -> float:
        """Load total balance of virtual accounts excluded from net worth."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(current_balance), 0)
                FROM virtual_accounts
                WHERE user_id = %s AND exclude_from_net_worth = true AND is_archived = false
                """,
                [self.user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _load_people_summary(self, data: DashboardData) -> None:
        """Load people ledger grouped by currency."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, net_balance, net_balance_egp, net_balance_usd
                FROM persons WHERE user_id = %s ORDER BY name
                """,
                [self.user_id],
            )
            rows = cursor.fetchall()

        egp = PeopleCurrencySummary(currency="EGP")
        usd = PeopleCurrencySummary(currency="USD")

        for _name, net_balance, net_balance_egp, net_balance_usd in rows:
            nb = float(net_balance)
            nb_egp = float(net_balance_egp)
            nb_usd = float(net_balance_usd)

            if nb_egp > 0:
                egp.owed_to_me += nb_egp
            elif nb_egp < 0:
                egp.i_owe += nb_egp

            if nb_usd > 0:
                usd.owed_to_me += nb_usd
            elif nb_usd < 0:
                usd.i_owe += nb_usd

            if nb > 0:
                data.people_owed_to_me += nb
            elif nb < 0:
                data.people_i_owe += nb

        if egp.owed_to_me != 0 or egp.i_owe != 0:
            data.people_by_currency.append(egp)
        if usd.owed_to_me != 0 or usd.i_owe != 0:
            data.people_by_currency.append(usd)

        data.has_people_activity = (
            len(data.people_by_currency) > 0
            or data.people_owed_to_me != 0
            or data.people_i_owe != 0
        )

    def _load_virtual_accounts(self) -> list[dict[str, Any]]:
        """Load active virtual accounts for dashboard widget."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, target_amount, current_balance, icon, color,
                       exclude_from_net_worth, display_order
                FROM virtual_accounts
                WHERE user_id = %s AND is_archived = false
                ORDER BY display_order, name
                """,
                [self.user_id],
            )
            rows = cursor.fetchall()

        result = []
        for row in rows:
            target = float(row[2]) if row[2] else 0.0
            current = float(row[3])
            progress = (current / target * 100) if target > 0 else 0.0
            result.append(
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "target_amount": target,
                    "current_balance": current,
                    "icon": row[4] or "",
                    "color": row[5] or "#0d9488",
                    "exclude_from_net_worth": row[6],
                    "display_order": row[7],
                    "progress_pct": progress,
                }
            )
        return result

    def _load_investments_total(self) -> float:
        """Load total investment portfolio value."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(SUM(units * last_unit_price), 0) FROM investments WHERE user_id = %s",
                [self.user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _load_streak(self) -> StreakInfo:
        """Compute consecutive days with transactions + weekly count.

        Port of Go's StreakService.GetStreak() — backward-walking algorithm.
        """
        info = StreakInfo()
        now = datetime.now(self.tz)
        today = now.date()

        with connection.cursor() as cursor:
            # Distinct transaction dates, descending
            cursor.execute(
                """
                SELECT DISTINCT date::date AS d FROM transactions
                WHERE date <= %s AND user_id = %s
                ORDER BY d DESC LIMIT 365
                """,
                [today, self.user_id],
            )
            dates = [row[0] for row in cursor.fetchall()]

        if not dates:
            return info

        expected = today
        for d in dates:
            if d == expected:
                info.consecutive_days += 1
                if expected == today:
                    info.active_today = True
                expected -= timedelta(days=1)
            elif d < expected:
                # Grace period: if no tx today but yesterday has one
                if info.consecutive_days == 0 and d == today - timedelta(days=1):
                    info.consecutive_days += 1
                    expected = d - timedelta(days=1)
                else:
                    break

        # Weekly count (Mon-Sun)
        weekday = now.weekday()  # 0=Mon, 6=Sun
        monday = today - timedelta(days=weekday)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM transactions
                WHERE date >= %s AND date <= %s AND user_id = %s
                """,
                [monday, today, self.user_id],
            )
            row = cursor.fetchone()
            info.weekly_count = row[0] if row else 0

        return info

    def load_recent_transactions(self, limit: int = 10) -> list[TransactionRow]:
        """Load recent transactions with running balance.

        Port of Go's TransactionRepo.GetRecentEnriched() — uses window function.
        This method is public so the partial view can call it directly.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sub.id, sub.type, sub.amount, sub.currency, sub.date,
                       sub.note, sub.balance_delta, sub.account_name, sub.running_balance
                FROM (
                    SELECT t.id, t.type, t.amount, t.currency, t.date, t.note,
                           t.balance_delta, a.name AS account_name,
                           a.current_balance - COALESCE(
                               SUM(t.balance_delta) OVER (
                                   PARTITION BY t.account_id
                                   ORDER BY t.date DESC, t.created_at DESC
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                               ), 0
                           ) AS running_balance
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE t.user_id = %s
                ) sub
                ORDER BY sub.date DESC, sub.id DESC
                LIMIT %s
                """,
                [self.user_id, limit],
            )
            rows = cursor.fetchall()

        return [
            TransactionRow(
                id=str(row[0]),
                type=row[1],
                amount=float(row[2]),
                currency=row[3],
                date=row[4],
                note=row[5],
                balance_delta=float(row[6]),
                account_name=row[7],
                running_balance=float(row[8]),
            )
            for row in rows
        ]

    def _load_net_worth_history(self, data: DashboardData) -> None:
        """Load 30-day net worth sparkline from daily_snapshots."""
        today = datetime.now(self.tz).date()
        start = today - timedelta(days=30)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT net_worth_egp FROM daily_snapshots
                WHERE date >= %s AND date <= %s AND user_id = %s
                ORDER BY date ASC
                """,
                [start, today, self.user_id],
            )
            rows = cursor.fetchall()

        if len(rows) >= 2:
            values = [float(r[0]) for r in rows]
            data.net_worth_history = values
            oldest = values[0]
            current = values[-1]
            if oldest != 0:
                data.net_worth_change = (current - oldest) / abs(oldest) * 100

    def _load_net_worth_by_currency(self, data: DashboardData) -> None:
        """Load per-currency net worth history for dual sparkline."""
        today = datetime.now(self.tz).date()
        start = today - timedelta(days=30)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.date, a.currency, SUM(s.balance) as total
                FROM account_snapshots s
                JOIN accounts a ON a.id = s.account_id
                WHERE s.date >= %s AND s.date <= %s AND s.user_id = %s
                GROUP BY s.date, a.currency
                ORDER BY s.date ASC
                """,
                [start, today, self.user_id],
            )
            rows = cursor.fetchall()

        if not rows:
            return

        by_currency: dict[str, list[float]] = {}
        # Group by currency, ordered by date
        for _date, currency, total in rows:
            by_currency.setdefault(currency, []).append(float(total))

        if by_currency:
            data.net_worth_history_by_currency = by_currency

    def _load_account_sparklines(
        self, data: DashboardData, all_accounts: list[dict[str, Any]]
    ) -> None:
        """Load per-account 30-day balance sparklines."""
        today = datetime.now(self.tz).date()
        start = today - timedelta(days=30)

        sparklines: dict[str, list[float]] = {}
        with connection.cursor() as cursor:
            for acc in all_accounts:
                cursor.execute(
                    """
                    SELECT balance FROM account_snapshots
                    WHERE account_id = %s AND date >= %s AND date <= %s AND user_id = %s
                    ORDER BY date ASC
                    """,
                    [acc["id"], start, today, self.user_id],
                )
                rows = cursor.fetchall()
                if len(rows) >= 2:
                    sparklines[acc["id"]] = [float(r[0]) for r in rows]

        if sparklines:
            data.account_sparklines = sparklines

    def _load_health_warnings(
        self, all_accounts: list[dict[str, Any]]
    ) -> list[HealthWarning]:
        """Check account health constraints.

        Port of Go's AccountHealthService.CheckAll().
        Parses health_config JSONB and checks min_balance / min_monthly_deposit.
        """
        warnings: list[HealthWarning] = []
        now = datetime.now(self.tz)
        today = now.date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1)
        else:
            month_end = date(today.year, today.month + 1, 1)

        for acc in all_accounts:
            cfg = _parse_jsonb(acc.get("health_config"))
            if not cfg:
                continue

            # Check minimum balance
            min_balance = cfg.get("min_balance")
            if min_balance is not None and acc["current_balance"] < float(min_balance):
                warnings.append(
                    HealthWarning(
                        account_name=acc["name"],
                        account_id=acc["id"],
                        rule="min_balance",
                        message=f"{acc['name']} is below minimum balance",
                    )
                )

            # Check minimum monthly deposit
            min_deposit = cfg.get("min_monthly_deposit")
            if min_deposit is not None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM transactions
                            WHERE account_id = %s AND user_id = %s AND type = 'income'
                            AND amount >= %s AND date >= %s AND date < %s
                        )
                        """,
                        [acc["id"], self.user_id, float(min_deposit), month_start, month_end],
                    )
                    row = cursor.fetchone()
                    has_deposit = row[0] if row else False

                if not has_deposit:
                    warnings.append(
                        HealthWarning(
                            account_name=acc["name"],
                            account_id=acc["id"],
                            rule="min_monthly_deposit",
                            message=f"{acc['name']} is missing required monthly deposit",
                        )
                    )

        return warnings

    def _load_budgets_with_spending(self) -> list[dict[str, Any]]:
        """Load budgets with current month's actual spending.

        Port of Go's BudgetRepo.GetAllWithSpending().
        """
        today = datetime.now(self.tz).date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1)
        else:
            month_end = date(today.year, today.month + 1, 1)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.id, b.category_id, b.monthly_limit, b.currency, b.is_active,
                       c.name AS category_name,
                       COALESCE(c.icon, '') AS category_icon,
                       COALESCE(SUM(t.amount), 0) AS spent
                FROM budgets b
                JOIN categories c ON b.category_id = c.id
                LEFT JOIN transactions t ON t.category_id = b.category_id
                    AND t.type = 'expense'
                    AND t.date >= %s AND t.date < %s
                    AND t.currency = b.currency::currency_type
                    AND t.user_id = b.user_id
                WHERE b.is_active = true AND b.user_id = %s
                GROUP BY b.id, c.name, c.icon
                ORDER BY c.name
                """,
                [month_start, month_end, self.user_id],
            )
            rows = cursor.fetchall()

        budgets = []
        for row in rows:
            limit_amt = float(row[2])
            spent = float(row[7])
            pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0

            if pct >= 100:
                status = "red"
            elif pct >= 80:
                status = "amber"
            else:
                status = "green"

            budgets.append(
                {
                    "id": str(row[0]),
                    "category_id": str(row[1]),
                    "monthly_limit": limit_amt,
                    "currency": row[3],
                    "category_name": row[5],
                    "category_icon": row[6],
                    "spent": spent,
                    "percentage": pct,
                    "status": status,
                }
            )
        return budgets

    def _compute_spending_comparison(self, data: DashboardData) -> None:
        """Compute this month vs last month spending + top categories + velocity.

        Port of Go's DashboardService.computeSpendingComparison().
        """
        now = datetime.now(self.tz)
        today = now.date()
        this_month_start = today.replace(day=1)

        # Last month start
        if this_month_start.month == 1:
            last_month_start = date(this_month_start.year - 1, 12, 1)
        else:
            last_month_start = date(this_month_start.year, this_month_start.month - 1, 1)

        # Next month start (end of current month range)
        if this_month_start.month == 12:
            next_month_start = date(this_month_start.year + 1, 1, 1)
        else:
            next_month_start = date(this_month_start.year, this_month_start.month + 1, 1)

        # Spending per currency this month
        this_month_by_currency = self._query_spending_by_currency(
            this_month_start, next_month_start
        )

        # Spending per currency last month
        last_month_by_currency = self._query_spending_by_currency(
            last_month_start, this_month_start
        )

        # Collect all currencies, EGP first
        currencies = set(this_month_by_currency.keys()) | set(last_month_by_currency.keys())
        ordered = []
        if "EGP" in currencies:
            ordered.append("EGP")
        for c in sorted(currencies):
            if c != "EGP":
                ordered.append(c)

        for cur in ordered:
            this_amt = this_month_by_currency.get(cur, 0.0)
            last_amt = last_month_by_currency.get(cur, 0.0)
            change = ((this_amt - last_amt) / last_amt * 100) if last_amt > 0 else 0.0

            top_cats = self._query_top_categories(
                cur, this_month_start, next_month_start, last_month_start
            )

            data.spending_by_currency.append(
                CurrencySpending(
                    currency=cur,
                    this_month=this_amt,
                    last_month=last_amt,
                    change=change,
                    top_categories=top_cats,
                )
            )

        # Spending velocity
        _, days_in_month = monthrange(today.year, today.month)
        days_elapsed = today.day
        days_left = days_in_month - days_elapsed
        day_progress = days_elapsed / days_in_month * 100

        total_this = 0.0
        total_last = 0.0
        for cs in data.spending_by_currency:
            rate = data.exchange_rate if cs.currency == "USD" and data.exchange_rate > 0 else 1.0
            total_this += cs.this_month * rate
            total_last += cs.last_month * rate

        pct = (total_this / total_last * 100) if total_last > 0 else 0.0

        if pct <= day_progress:
            status = "green"
        elif pct <= day_progress + 10:
            status = "amber"
        else:
            status = "red"

        data.spending_velocity = SpendingVelocity(
            percentage=pct,
            days_elapsed=days_elapsed,
            days_total=days_in_month,
            days_left=days_left,
            day_progress=day_progress,
            status=status,
        )

    def _query_spending_by_currency(
        self, start: date, end: date
    ) -> dict[str, float]:
        """Query total expense spending grouped by currency for a date range."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT currency, COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE type = 'expense' AND date >= %s AND date < %s AND user_id = %s
                GROUP BY currency ORDER BY currency
                """,
                [start, end, self.user_id],
            )
            return {row[0]: float(row[1]) for row in cursor.fetchall()}

    def _query_top_categories(
        self,
        currency: str,
        this_month_start: date,
        next_month_start: date,
        last_month_start: date,
    ) -> list[dict[str, Any]]:
        """Query top 3 spending categories with month-over-month change.

        Port of Go's queryTopCategoriesForCurrency() — uses CTE.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH this_month AS (
                    SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
                        COALESCE(c.icon, '') AS cat_icon,
                        SUM(t.amount) AS amount
                    FROM transactions t
                    LEFT JOIN categories c ON t.category_id = c.id
                    WHERE t.type = 'expense' AND t.currency = %s::currency_type
                        AND t.date >= %s AND t.date < %s
                        AND t.user_id = %s
                    GROUP BY c.name, c.icon
                    ORDER BY SUM(t.amount) DESC
                    LIMIT 3
                ),
                last_month AS (
                    SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
                        SUM(t.amount) AS amount
                    FROM transactions t
                    LEFT JOIN categories c ON t.category_id = c.id
                    WHERE t.type = 'expense' AND t.currency = %s::currency_type
                        AND t.date >= %s AND t.date < %s
                        AND t.user_id = %s
                    GROUP BY c.name
                )
                SELECT tm.cat_name, tm.cat_icon, tm.amount,
                    COALESCE(lm.amount, 0) AS last_amount
                FROM this_month tm
                LEFT JOIN last_month lm ON tm.cat_name = lm.cat_name
                """,
                [
                    currency, this_month_start, next_month_start, self.user_id,
                    currency, last_month_start, this_month_start, self.user_id,
                ],
            )
            rows = cursor.fetchall()

        categories = []
        for name, icon, this_amt, last_amt in rows:
            this_f = float(this_amt)
            last_f = float(last_amt)
            change = ((this_f - last_f) / last_f * 100) if last_f > 0 else 0.0
            categories.append(
                {
                    "name": name,
                    "icon": icon,
                    "amount": this_f,
                    "change": change,
                    "is_up": change > 0,
                }
            )
        return categories


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_jsonb(value: Any) -> dict[str, Any] | None:
    """Parse a JSONB value that psycopg3 may return as a string.

    psycopg3 returns JSONB columns as strings, not dicts.
    This helper handles both cases safely.
    """
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


def _compute_due_date(statement_day: int, due_day: int, today: date) -> date:
    """Compute credit card due date from billing cycle metadata.

    Delegates to core.billing.compute_due_date — kept as a thin wrapper
    to avoid touching all call sites.
    """
    from core.billing import compute_due_date

    return compute_due_date(statement_day, due_day, today)
