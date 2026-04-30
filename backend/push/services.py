"""
NotificationService — generates push notification payloads by polling.

Checks multiple conditions (credit cards due, health warnings, budget thresholds,
recurring rules) and returns notification dicts for the frontend to display.

The service does NOT send push messages — the browser polls GET /api/push/check
and displays them via the Push API / in-app banner. We generate payloads;
the browser handles delivery.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TypedDict
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.utils.translation import gettext as _

from accounts.services import AccountService, load_health_warnings
from budgets.services import BudgetService
from core.billing import compute_due_date, parse_billing_cycle
from core.dates import month_range
from core.status import compute_threshold_status
from recurring.services import RecurringService
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class PersistStats(TypedDict):
    created: int
    updated: int
    resolved: int


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

        # 1-4. Leaf-service-based triggers: CC due, health, budgets, unusual spending
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
                                    f" — balance: {card.currency} {-card.current_balance:.2f}"
                                ),
                                "url": "/accounts",
                                "tag": f"cc-due-{card.name}-{due_date.isoformat()}",
                            }
                        )

            # 2. Account health warnings (Low balance, missing deposits, reconciliation)
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
            days_left = month_range(today)[1].day - today.day

            for budget in budget_svc.get_all_with_spending():
                pct = budget.percentage
                display_name = f"{budget.category_icon} {budget.category_name}".strip()
                status = compute_threshold_status(pct, (80.0, 100.0))

                if status == "red":
                    notifications.append(
                        {
                            "title": _("Budget Exceeded"),
                            "body": (
                                f"{display_name}: spent {budget.spent:.0f} "
                                f"of {budget.monthly_limit:.0f} "
                                f"limit ({pct:.0f}%)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-exceeded-{budget.category_id}",
                        }
                    )
                elif status == "amber":
                    notifications.append(
                        {
                            "title": _("Budget Warning"),
                            "body": (
                                f"{display_name}: {pct:.0f}% used "
                                f"({budget.remaining:.0f} remaining, {days_left} days left)"
                            ),
                            "url": "/budgets",
                            "tag": f"budget-warning-{budget.category_id}",
                        }
                    )

            # 4. Unusual Spending detection (Last 24h vs 30-day average)
            try:
                import uuid

                uuid.UUID(self.user_id)

                yesterday = datetime.now(self.tz) - timedelta(days=1)
                recent_txs = (
                    Transaction.objects.for_user(self.user_id)
                    .filter(
                        type="expense",
                        created_at__gte=yesterday,
                    )
                    .select_related("category")
                )

                for tx in recent_txs:
                    if not tx.category_id:
                        continue

                    # Calculate 30-day average for this category
                    thirty_days_ago = date.today() - timedelta(days=30)
                    avg_val = Transaction.objects.for_user(self.user_id).filter(
                        category_id=tx.category_id,
                        type="expense",
                        date__gte=thirty_days_ago,
                        date__lt=date.today(),
                    ).aggregate(avg=Avg("amount"))["avg"] or Decimal(0)

                    if avg_val > 0 and tx.amount > (avg_val * 3):
                        notifications.append(
                            {
                                "title": _("Unusual Spending Detected"),
                                "body": _(
                                    "%(amount).0f %(currency)s on %(cat)s is 3x your average"
                                )
                                % {
                                    "amount": tx.amount,
                                    "currency": tx.currency,
                                    "cat": tx.category.get_display_name(),
                                },
                                "url": "/transactions",
                                "tag": f"unusual-spending-{tx.id}",
                            }
                        )
            except (ValueError, ValidationError):
                # Skip unusual spending for non-UUID users (tests)
                pass

        except Exception:
            logger.exception(
                "push: failed to load account/health/budget/unusual notifications"
            )

        # 5. Recurring transactions due (needing confirmation)
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

        # 6. Twice-daily record-transaction reminders
        try:
            notifications.extend(self._get_record_reminders())
        except Exception:
            logger.exception("push: failed to load record reminders")

        return notifications

    def _get_record_reminders(self) -> list[dict[str, str]]:
        """Smart twice-daily reminders to log transactions.

        Morning (8am+): fires if no tx recorded since yesterday 9pm.
        Evening (9pm+): fires if no tx recorded since today 8am.
        Auto-resolves when the user records any transaction.
        """
        MORNING_HOUR = 8
        EVENING_HOUR = 21

        now = datetime.now(self.tz)
        today = now.date()
        yesterday = today - timedelta(days=1)
        reminders: list[dict[str, str]] = []

        if now.hour >= MORNING_HOUR:
            morning_window_start = datetime(
                yesterday.year,
                yesterday.month,
                yesterday.day,
                EVENING_HOUR,
                0,
                0,
                tzinfo=self.tz,
            )
            if (
                not Transaction.objects.for_user(self.user_id)
                .filter(created_at__gte=morning_window_start)
                .exists()
            ):
                reminders.append(
                    {
                        "title": _("Record Today's Transactions"),
                        "body": _(
                            "You haven't logged anything since last night."
                            " Take a minute to record your spending."
                        ),
                        "url": "/transactions/new",
                        "tag": f"record-reminder-morning-{today.isoformat()}",
                    }
                )

        if now.hour >= EVENING_HOUR:
            evening_window_start = datetime(
                today.year,
                today.month,
                today.day,
                MORNING_HOUR,
                0,
                0,
                tzinfo=self.tz,
            )
            if (
                not Transaction.objects.for_user(self.user_id)
                .filter(created_at__gte=evening_window_start)
                .exists()
            ):
                reminders.append(
                    {
                        "title": _("End-of-Day Check-In"),
                        "body": _(
                            "No transactions recorded today."
                            " Log what you spent before you forget."
                        ),
                        "url": "/transactions/new",
                        "tag": f"record-reminder-evening-{today.isoformat()}",
                    }
                )

        return reminders

    def generate_and_persist(self) -> PersistStats:
        """Generate notifications and persist them to the database.

        - Creates missing notifications for each current payload by (user, tag).
        - Updates existing notification content without resetting is_read.
        - Auto-resolves: deletes UNREAD notifications whose tags are not in
          the current payload set (condition no longer active).
        - Preserves READ notifications for history (cleaned up after 30 days).
        """
        from push.models import Notification

        payloads = self.get_pending_notifications()
        current_tags = {p["tag"] for p in payloads}
        created = updated = resolved = 0

        for payload in payloads:
            notif, was_created = Notification.objects.get_or_create(
                user_id=self.user_id,
                tag=payload["tag"],
                defaults={
                    "title": payload["title"],
                    "body": payload["body"],
                    "url": payload.get("url", ""),
                    "is_read": False,
                },
            )
            if was_created:
                created += 1
            else:
                # Update content but preserve is_read — user dismissals survive restarts
                notif.title = payload["title"]
                notif.body = payload["body"]
                notif.url = payload.get("url", "")
                notif.save(update_fields=["title", "body", "url", "updated_at"])
                updated += 1

        # Auto-resolve: remove unread notifications that are no longer active
        resolved_qs = Notification.objects.filter(
            user_id=self.user_id,
            is_read=False,
        ).exclude(tag__in=current_tags)
        resolved = resolved_qs.count()
        resolved_qs.delete()

        logger.info(
            "push.generate_and_persist user=%s created=%d updated=%d resolved=%d",
            self.user_id,
            created,
            updated,
            resolved,
        )
        return {"created": created, "updated": updated, "resolved": resolved}
