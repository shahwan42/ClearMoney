"""
NotificationService — generates push notification payloads by polling.

Checks multiple conditions (credit cards due, health warnings, budget thresholds,
recurring rules) and returns notification dicts for the frontend to display.

The service does NOT send push messages — the browser polls GET /api/push/check
and displays them via the Push API / in-app banner. We generate payloads;
the browser handles delivery.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils.translation import gettext as _

from accounts.services import AccountService, load_health_warnings
from budgets.services import BudgetService
from core.billing import compute_due_date, parse_billing_cycle
from recurring.services import RecurringService

logger = logging.getLogger(__name__)


class NotificationService:
    """Aggregates notification triggers from leaf services.

    Constructor takes user_id and timezone (same pattern as AccountService,
    BudgetService, RecurringService). Dependencies are created internally.

    Each trigger source is wrapped in try/except — one failing source
    doesn't block others.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_pending_notifications(self) -> list[dict[str, str]]:
        """Check all trigger conditions and return notification payloads.

        Returns a list of dicts with keys: title, body, url, tag.
        The tag field is a dedup key — the browser won't show duplicates.
        """
        notifications: list[dict[str, str]] = []

        # 1-3. Leaf-service-based triggers: CC due, health, budgets
        try:
            # Get all accounts for CC due date checks and health warnings
            acct_svc = AccountService(self.user_id, self.tz)
            all_accounts = acct_svc.get_all()
            credit_accounts = [
                a for a in all_accounts if a.type in {"credit_card", "credit_limit"}
            ]
            today = datetime.now(self.tz).date()

            # 1. Credit cards due within 3 days
            for card in credit_accounts:
                billing = parse_billing_cycle(card.metadata)
                if billing:
                    stmt_day, due_day = billing
                    due_date = compute_due_date(stmt_day, due_day, today)
                    days_until = (due_date - today).days
                    if 0 <= days_until <= 3:
                        notifications.append(
                            {
                                "title": _("Credit Card Due Soon"),
                                "body": (
                                    f"{card.name} is due in {days_until} day(s)"
                                    f" — balance: EGP {-card.current_balance:.2f}"
                                ),
                                "url": "/accounts",
                                "tag": f"cc-due-{card.name}-{due_date.isoformat()}",
                            }
                        )

            # 2. Account health warnings
            for warning in load_health_warnings(self.user_id, all_accounts, self.tz):
                notifications.append(
                    {
                        "title": _("Account Health Warning"),
                        "body": warning.message,
                        "url": f"/accounts/{warning.account_id}",
                        "tag": f"health-{warning.rule}-{warning.account_id}",
                    }
                )

            # 3. Budget threshold alerts (80% warning, 100% exceeded)
            budget_svc = BudgetService(self.user_id, self.tz)
            for budget in budget_svc.get_all_with_spending():
                pct = budget.percentage
                display_name = f"{budget.category_icon} {budget.category_name}".strip()

                if pct >= 100:
                    notifications.append(
                        {
                            "title": _("Budget Exceeded"),
                            "body": (
                                f"{display_name}: spent EGP {budget.spent:.0f}"
                                f" of EGP {budget.monthly_limit:.0f}"
                                f" limit ({pct:.0f}%)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-exceeded-{budget.category_id}",
                        }
                    )
                elif pct >= 80:
                    remaining = budget.monthly_limit - budget.spent
                    notifications.append(
                        {
                            "title": _("Budget Warning"),
                            "body": (
                                f"{display_name}: {pct:.0f}% of budget used"
                                f" (EGP {remaining:.0f} remaining)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-warning-{budget.category_id}",
                        }
                    )

        except Exception:
            logger.exception("push: failed to load account/health/budget notifications")

        # 4. Recurring transactions due (needing confirmation)
        try:
            recurring_svc = RecurringService(self.user_id, self.tz)
            pending = recurring_svc.get_due_pending()

            for rule in pending:
                due_date = rule.next_due_date
                notifications.append(
                    {
                        "title": _("Recurring Transaction Due"),
                        "body": (
                            f"A recurring {rule.frequency} transaction"
                            f" needs confirmation (due {due_date.strftime('%b %-d')})"
                        ),
                        "url": "/recurring",
                        "tag": f"recurring-{rule.id}-{due_date.isoformat()}",
                    }
                )

        except Exception:
            logger.exception("push: failed to load recurring notifications")

        return notifications
