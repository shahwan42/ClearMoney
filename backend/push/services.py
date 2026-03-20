"""
NotificationService — generates push notification payloads by polling.

Checks multiple conditions (credit cards due, health warnings, budget thresholds,
recurring rules) and returns notification dicts for the frontend to display.

The service does NOT send push messages — the browser polls GET /api/push/check
and displays them via the Push API / in-app banner. We generate payloads;
the browser handles delivery.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from dashboard.services import DashboardService
from recurring.services import RecurringService

logger = logging.getLogger(__name__)


class NotificationService:
    """Aggregates notification triggers from dashboard and recurring services.

    Constructor takes user_id and timezone (same pattern as DashboardService
    and RecurringService). Both dependencies are created internally.

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

        # 1-3. Dashboard-based triggers: CC due, health, budgets
        try:
            dashboard_svc = DashboardService(self.user_id, self.tz)
            data: dict[str, Any] = dashboard_svc.get_dashboard()

            # 1. Credit cards due within 3 days
            for card in data.get("due_soon_cards", []):
                if card.days_until_due <= 3:
                    notifications.append(
                        {
                            "title": "Credit Card Due Soon",
                            "body": (
                                f"{card.account_name} is due in {card.days_until_due} day(s)"
                                f" — balance: EGP {-card.balance:.2f}"
                            ),
                            "url": "/accounts",
                            "tag": f"cc-due-{card.account_name}-{card.due_date.isoformat()}",
                        }
                    )

            # 2. Account health warnings
            for warning in data.get("health_warnings", []):
                notifications.append(
                    {
                        "title": "Account Health Warning",
                        "body": warning.message,
                        "url": f"/accounts/{warning.account_id}",
                        "tag": f"health-{warning.rule}-{warning.account_id}",
                    }
                )

            # 3. Budget threshold alerts (80% warning, 100% exceeded)
            for budget in data.get("budgets", []):
                pct = budget["percentage"]
                display_name = (
                    f"{budget['category_icon']} {budget['category_name']}".strip()
                )

                if pct >= 100:
                    notifications.append(
                        {
                            "title": "Budget Exceeded",
                            "body": (
                                f"{display_name}: spent EGP {budget['spent']:.0f}"
                                f" of EGP {budget['monthly_limit']:.0f}"
                                f" limit ({pct:.0f}%)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-exceeded-{budget['category_id']}",
                        }
                    )
                elif pct >= 80:
                    remaining = budget["monthly_limit"] - budget["spent"]
                    notifications.append(
                        {
                            "title": "Budget Warning",
                            "body": (
                                f"{display_name}: {pct:.0f}% of budget used"
                                f" (EGP {remaining:.0f} remaining)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-warning-{budget['category_id']}",
                        }
                    )

        except Exception:
            logger.exception("push: failed to load dashboard notifications")

        # 4. Recurring transactions due (needing confirmation)
        try:
            recurring_svc = RecurringService(self.user_id, self.tz)
            pending = recurring_svc.get_due_pending()

            for rule in pending:
                due_date = rule["next_due_date"]
                notifications.append(
                    {
                        "title": "Recurring Transaction Due",
                        "body": (
                            f"A recurring {rule['frequency']} transaction"
                            f" needs confirmation (due {due_date.strftime('%b %-d')})"
                        ),
                        "url": "/recurring",
                        "tag": f"recurring-{rule['id']}-{due_date.isoformat()}",
                    }
                )

        except Exception:
            logger.exception("push: failed to load recurring notifications")

        return notifications
