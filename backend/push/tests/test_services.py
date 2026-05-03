"""
NotificationService tests — verifies notification generation logic.

Coverage for each notification trigger type. Uses pytest-mock to patch
leaf services (AccountService, BudgetService, load_health_warnings, RecurringService)
Unit tests, no DB needed.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from pytest_mock import MockerFixture

import auth_app.models
from accounts.types import AccountSummary, HealthWarning
from budgets.types import BudgetWithSpending
from push.services import NotificationService
from recurring.types import RecurringRulePending

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def mock_accounts(mocker: MockerFixture) -> MagicMock:
    """Patch AccountService so it doesn't hit the DB."""
    return mocker.patch("push.services.AccountService")


@pytest.fixture
def mock_health_warnings(mocker: MockerFixture) -> MagicMock:
    """Patch load_health_warnings so it doesn't hit the DB."""
    return mocker.patch("push.services.load_health_warnings")


@pytest.fixture
def mock_budgets(mocker: MockerFixture) -> MagicMock:
    """Patch BudgetService so it doesn't hit the DB."""
    return mocker.patch("push.services.BudgetService")


@pytest.fixture
def mock_billing(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Patch billing utilities so they don't need real data."""
    parse_mock = mocker.patch("push.services.parse_billing_cycle")
    compute_mock = mocker.patch("push.services.compute_due_date")
    # Mock datetime.now() to return a fixed date (Mar 19, 2026) for CC due calculations
    datetime_mock = mocker.patch("push.services.datetime")
    now_mock = MagicMock()
    now_mock.date.return_value = date(2026, 3, 19)
    datetime_mock.now.return_value = now_mock
    return {"parse": parse_mock, "compute": compute_mock}


@pytest.fixture
def mock_recurring(mocker: MockerFixture) -> MagicMock:
    """Patch RecurringService so it doesn't hit the DB."""
    return mocker.patch("push.services.RecurringService")


# ---------------------------------------------------------------------------
# Credit card due soon
# ---------------------------------------------------------------------------


class TestCreditCardDueSoon:
    def test_cc_due_within_3_days(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        # Setup account data
        cc_account = AccountSummary(
            id="cc-1",
            name="CIB Visa",
            institution_id=None,
            currency="EGP",
            type="credit_card",
            current_balance=-1500.50,
            initial_balance=0.0,
            credit_limit=5000.0,
            is_dormant=False,
            is_credit_type=True,
            available_credit=3499.50,
            display_order=0,
            metadata={"statement_day": 15, "due_day": 20},
            health_config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        mock_accounts.return_value.get_all.return_value = [cc_account]
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.return_value = []

        # Setup billing mocks
        mock_billing["parse"].return_value = (15, 20)
        mock_billing["compute"].return_value = date(2026, 3, 21)

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Credit Card Due Soon"
        assert "CIB Visa" in n["body"]
        assert "2 day(s)" in n["body"]
        assert "EGP 1500.50" in n["body"]
        assert n["url"] == "/accounts"

    def test_cc_not_due_skipped(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        # Setup account data
        cc_account = AccountSummary(
            id="cc-2",
            name="HSBC MC",
            institution_id=None,
            currency="EGP",
            type="credit_card",
            current_balance=-2000.0,
            initial_balance=0.0,
            credit_limit=10000.0,
            is_dormant=False,
            is_credit_type=True,
            available_credit=8000.0,
            display_order=0,
            metadata={"statement_day": 15, "due_day": 20},
            health_config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        mock_accounts.return_value.get_all.return_value = [cc_account]
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.return_value = []

        # Setup billing mocks: due date is 5 days away (outside 3-day window)
        mock_billing["parse"].return_value = (15, 20)
        mock_billing["compute"].return_value = date(2026, 3, 25)

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 0


# ---------------------------------------------------------------------------
# Health warnings
# ---------------------------------------------------------------------------


class TestHealthWarnings:
    def test_health_warning_notification(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = [
            HealthWarning(
                account_name="Savings",
                account_id="acc-123",
                rule="min_balance",
                message="Savings balance is below minimum (EGP 500)",
            ),
        ]
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Account Health Warning"
        assert "below minimum" in n["body"]
        assert n["url"] == "/accounts/acc-123"
        assert n["tag"] == "health-min_balance-acc-123"


# ---------------------------------------------------------------------------
# Budget thresholds
# ---------------------------------------------------------------------------


class TestBudgetThresholds:
    def test_budget_warning_at_80pct(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = [
            BudgetWithSpending(
                id="b-1",
                category_id="cat-1",
                category_name="Groceries",
                category_icon="🛒",
                monthly_limit=2000.0,
                spent=1700.0,
                percentage=85.0,
                currency="EGP",
                remaining=300.0,
                status="amber",
            ),
        ]
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Budget Warning"
        assert "85%" in n["body"]
        assert "300" in n["body"]
        assert n["tag"] == "budget-warning-cat-1"

    def test_budget_exceeded_at_100pct(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = [
            BudgetWithSpending(
                id="b-2",
                category_id="cat-2",
                category_name="Transport",
                category_icon="",
                monthly_limit=500.0,
                spent=550.0,
                percentage=110.0,
                currency="EGP",
                remaining=-50.0,
                status="red",
            ),
        ]
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Budget Exceeded"
        assert "Transport" in n["body"]
        assert "550" in n["body"]
        assert "500" in n["body"]
        assert "110%" in n["body"]
        assert n["tag"] == "budget-exceeded-cat-2"

    def test_budget_below_80_no_notification(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = [
            {
                "id": "b-3",
                "category_id": "cat-3",
                "category_name": "Fun",
                "category_icon": "",
                "monthly_limit": 1000.0,
                "spent": 500.0,
                "percentage": 50.0,
                "currency": "EGP",
            },
        ]
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 0


# ---------------------------------------------------------------------------
# Recurring transactions due
# ---------------------------------------------------------------------------


class TestRecurringDue:
    def test_recurring_due_notification(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.return_value = [
            RecurringRulePending(
                id="rule-1",
                user_id="user-1",
                frequency="monthly",
                day_of_month=None,
                next_due_date=date(2026, 3, 19),
                is_active=True,
                auto_confirm=False,
                template_transaction={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Recurring Transaction Due"
        assert "monthly" in n["body"]
        assert "Mar 19" in n["body"]
        assert n["url"] == "/recurring"
        assert n["tag"] == "recurring-rule-1-2026-03-19"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_when_no_issues(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = []
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert notifications == []

    def test_accounts_error_still_returns_recurring(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        """If AccountService fails, recurring notifications still work."""
        mock_accounts.return_value.get_all.side_effect = RuntimeError("db down")
        mock_recurring.return_value.get_due_pending.return_value = [
            RecurringRulePending(
                id="rule-2",
                user_id="user-1",
                frequency="weekly",
                day_of_month=None,
                next_due_date=date(2026, 3, 19),
                is_active=True,
                auto_confirm=False,
                template_transaction={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        assert notifications[0]["title"] == "Recurring Transaction Due"

    def test_recurring_error_still_returns_account_warnings(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        """If RecurringService fails, account notifications still work."""
        mock_accounts.return_value.get_all.return_value = []
        mock_health_warnings.return_value = [
            HealthWarning(
                account_name="Checking",
                account_id="acc-456",
                rule="min_monthly_deposit",
                message="No deposit this month",
            ),
        ]
        mock_budgets.return_value.get_all_with_spending.return_value = []
        mock_recurring.return_value.get_due_pending.side_effect = RuntimeError(
            "db down"
        )

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        assert notifications[0]["title"] == "Account Health Warning"

    def test_multiple_triggers_combined(
        self,
        mock_accounts: MagicMock,
        mock_health_warnings: MagicMock,
        mock_budgets: MagicMock,
        mock_billing: dict[str, MagicMock],
        mock_recurring: MagicMock,
    ) -> None:
        """All trigger types can appear in one response."""
        cc_account = AccountSummary(
            id="cc-1",
            name="First card",
            institution_id=None,
            currency="EGP",
            type="credit_card",
            current_balance=-500.0,
            initial_balance=0.0,
            credit_limit=3000.0,
            is_dormant=False,
            is_credit_type=True,
            available_credit=2500.0,
            display_order=0,
            metadata={"statement_day": 10, "due_day": 15},
            health_config={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        mock_accounts.return_value.get_all.return_value = [cc_account]
        mock_health_warnings.return_value = [
            HealthWarning("Savings", "acc-1", "min_balance", "Low balance"),
        ]
        mock_budgets.return_value.get_all_with_spending.return_value = [
            BudgetWithSpending(
                id="b-1",
                category_id="cat-1",
                category_name="Food",
                category_icon="",
                monthly_limit=1000.0,
                spent=1100.0,
                percentage=110.0,
                currency="EGP",
                remaining=-100.0,
                status="red",
            ),
        ]
        mock_recurring.return_value.get_due_pending.return_value = [
            RecurringRulePending(
                id="r-1",
                user_id="user-1",
                frequency="daily",
                day_of_month=None,
                next_due_date=date(2026, 3, 19),
                is_active=True,
                auto_confirm=False,
                template_transaction={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ),
        ]

        # Setup billing mocks for CC (due in 1 day)
        mock_billing["parse"].return_value = (10, 15)
        mock_billing["compute"].return_value = date(2026, 3, 21)

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        titles = [n["title"] for n in notifications]
        assert "Credit Card Due Soon" in titles
        assert "Account Health Warning" in titles
        assert "Budget Exceeded" in titles
        assert "Recurring Transaction Due" in titles
        assert len(notifications) == 4


# ---------------------------------------------------------------------------
# generate_and_persist tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGenerateAndPersist:
    """Tests for NotificationService.generate_and_persist()."""

    def _make_user(self) -> "tuple[str, auth_app.models.User]":
        from tests.factories import UserFactory

        user = UserFactory()
        return str(user.id), user

    def _svc(self, user_id: str, mocker: MockerFixture) -> NotificationService:
        svc = NotificationService(user_id, TZ)
        mocker.patch.object(
            svc,
            "get_pending_notifications",
            return_value=[
                {
                    "title": "Budget Alert",
                    "body": "Over budget",
                    "url": "/budgets",
                    "tag": "budget-exceeded-1",
                },
            ],
        )
        return svc

    def test_create_new_notification(self, mocker: MockerFixture) -> None:
        from push.models import Notification

        user_id, _ = self._make_user()
        svc = self._svc(user_id, mocker)
        stats = svc.generate_and_persist()

        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert Notification.objects.for_user(user_id).count() == 1

    def test_update_existing_notification(self, mocker: MockerFixture) -> None:
        from push.models import Notification

        user_id, user = self._make_user()
        Notification.objects.create(
            user=user,
            title="Old Title",
            body="Old body",
            url="/old",
            tag="budget-exceeded-1",
            is_read=True,
        )
        svc = self._svc(user_id, mocker)
        stats = svc.generate_and_persist()

        assert stats["created"] == 0
        assert stats["updated"] == 1
        notif = Notification.objects.get(user_id=user_id, tag="budget-exceeded-1")
        assert notif.title == "Budget Alert"
        assert notif.is_read is True  # read state preserved across restarts

    def test_read_state_preserved_on_update(self, mocker: MockerFixture) -> None:
        """Dismissed notifications must not reappear after app restart."""
        from push.models import Notification

        user_id, user = self._make_user()
        Notification.objects.create(
            user=user,
            title="Budget Alert",
            body="Over budget",
            url="/budgets",
            tag="budget-exceeded-1",
            is_read=True,  # user dismissed it
        )
        svc = self._svc(user_id, mocker)
        svc.generate_and_persist()

        notif = Notification.objects.get(user_id=user_id, tag="budget-exceeded-1")
        assert notif.is_read is True  # must survive restart

    def test_resolve_stale_unread_notifications(self, mocker: MockerFixture) -> None:
        from push.models import Notification

        user_id, user = self._make_user()
        Notification.objects.create(
            user=user, title="Stale", body="Gone", tag="stale-tag", is_read=False
        )
        svc = self._svc(user_id, mocker)
        stats = svc.generate_and_persist()

        assert stats["resolved"] == 1
        assert not Notification.objects.filter(
            user_id=user_id, tag="stale-tag"
        ).exists()

    def test_delete_read_notifications_for_resolved_conditions(
        self, mocker: MockerFixture
    ) -> None:
        """Resolved conditions delete ALL notifications (read+unread) so that
        if the condition recurs the user sees a fresh alert."""
        from push.models import Notification

        user_id, user = self._make_user()
        Notification.objects.create(
            user=user, title="Read", body="Done", tag="old-read-tag", is_read=True
        )
        svc = self._svc(user_id, mocker)
        stats = svc.generate_and_persist()

        # Read notification for a resolved condition must be deleted
        assert stats["resolved"] == 1
        assert not Notification.objects.filter(
            user_id=user_id, tag="old-read-tag"
        ).exists()


# ---------------------------------------------------------------------------
# Record transaction reminders (twice-daily, smart)
# ---------------------------------------------------------------------------

# Fixed reference times in UTC (Africa/Cairo = UTC+3 in April 2026)
_MORNING_8_30_UTC = "2026-04-30 05:30:00"  # 8:30am Cairo (UTC+3)
_EVENING_9_30_UTC = "2026-04-30 18:30:00"  # 9:30pm Cairo (UTC+3)
_BEFORE_MORNING_UTC = "2026-04-30 04:59:00"  # 7:59am Cairo (UTC+3)
_BEFORE_EVENING_UTC = "2026-04-30 17:59:00"  # 8:59pm Cairo (UTC+3)


@pytest.mark.django_db
class TestRecordReminders:
    """Twice-daily reminder fires if no transaction recorded in each window."""

    TZ = ZoneInfo("Africa/Cairo")

    def _make_user_and_account(self) -> tuple[str, Any]:
        from tests.factories import AccountFactory, InstitutionFactory, UserFactory

        user = UserFactory()
        institution = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=institution.id)
        return str(user.id), account

    def _svc_with_mocked_other_triggers(
        self, user_id: str, mocker: MockerFixture
    ) -> NotificationService:
        """Return a service where all non-record triggers return empty."""
        mocker.patch(
            "push.services.AccountService"
        ).return_value.get_all.return_value = []
        mocker.patch("push.services.load_health_warnings").return_value = []
        mocker.patch(
            "push.services.BudgetService"
        ).return_value.get_all_with_spending.return_value = []
        mocker.patch(
            "push.services.RecurringService"
        ).return_value.get_due_pending.return_value = []
        return NotificationService(user_id, self.TZ)

    def _make_tx_at(
        self, user_id: str, account_id: uuid.UUID | str, created_at: datetime
    ) -> None:
        """Create a transaction and force its created_at to a specific UTC time."""

        from tests.factories import TransactionFactory
        from transactions.models import Transaction

        tx = TransactionFactory(user_id=user_id, account_id=account_id)
        aware = (
            created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at
        )
        Transaction.objects.filter(id=tx.id).update(created_at=aware)

    def _tags(self, svc: NotificationService) -> list[str]:
        return [n["tag"] for n in svc.get_pending_notifications()]

    # ------------------------------------------------------------------
    # Morning window tests
    # ------------------------------------------------------------------

    def test_morning_reminder_fires_when_no_tx_since_yesterday_evening(
        self, mocker: MockerFixture
    ) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" in tags

    def test_morning_reminder_suppressed_when_tx_after_yesterday_9pm(
        self, mocker: MockerFixture
    ) -> None:
        from datetime import datetime as dt

        import freezegun

        user_id, account = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        # tx at yesterday 9:30pm Cairo (19:30 UTC)
        self._make_tx_at(user_id, account.id, dt(2026, 4, 29, 19, 30, tzinfo=UTC))
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" not in tags

    def test_morning_reminder_not_suppressed_when_tx_before_yesterday_9pm(
        self, mocker: MockerFixture
    ) -> None:
        from datetime import datetime as dt

        import freezegun

        user_id, account = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        # tx at yesterday 8:30pm Cairo (17:30 UTC, UTC+3) — before window start (yesterday 9pm = 18:00 UTC)
        self._make_tx_at(user_id, account.id, dt(2026, 4, 29, 17, 30, tzinfo=UTC))
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" in tags

    # ------------------------------------------------------------------
    # Evening window tests
    # ------------------------------------------------------------------

    def test_evening_reminder_fires_when_no_tx_since_morning(
        self, mocker: MockerFixture
    ) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_EVENING_9_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-evening-2026-04-30" in tags

    def test_evening_reminder_suppressed_when_tx_recorded_this_afternoon(
        self, mocker: MockerFixture
    ) -> None:
        from datetime import datetime as dt

        import freezegun

        user_id, account = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        # tx at today 3pm Cairo (13:00 UTC)
        self._make_tx_at(user_id, account.id, dt(2026, 4, 30, 13, 0, tzinfo=UTC))
        with freezegun.freeze_time(_EVENING_9_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-evening-2026-04-30" not in tags

    # ------------------------------------------------------------------
    # Before-window tests (no trigger)
    # ------------------------------------------------------------------

    def test_no_reminder_before_morning_window(self, mocker: MockerFixture) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_BEFORE_MORNING_UTC):
            tags = self._tags(svc)
        assert not any(t.startswith("record-reminder-") for t in tags)

    def test_no_evening_reminder_before_evening_window(
        self, mocker: MockerFixture
    ) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_BEFORE_EVENING_UTC):
            tags = self._tags(svc)
        assert "record-reminder-evening-2026-04-30" not in tags

    # ------------------------------------------------------------------
    # Combined / edge cases
    # ------------------------------------------------------------------

    def test_both_reminders_fire_when_no_tx_all_day(
        self, mocker: MockerFixture
    ) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_EVENING_9_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" in tags
        assert "record-reminder-evening-2026-04-30" in tags

    def test_reminder_tag_includes_today_date(self, mocker: MockerFixture) -> None:
        import freezegun

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" in tags

    def test_transfer_type_tx_suppresses_reminder(self, mocker: MockerFixture) -> None:
        from datetime import datetime as dt

        import freezegun

        from tests.factories import TransactionFactory
        from transactions.models import Transaction

        user_id, account = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)
        tx = TransactionFactory(user_id=user_id, account_id=account.id, type="transfer")
        Transaction.objects.filter(id=tx.id).update(
            created_at=dt(2026, 4, 29, 19, 30, tzinfo=UTC)
        )
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" not in tags

    def test_other_user_tx_does_not_suppress_reminder(
        self, mocker: MockerFixture
    ) -> None:
        from datetime import datetime as dt

        import freezegun

        from tests.factories import TransactionFactory
        from transactions.models import Transaction

        user_id, _ = self._make_user_and_account()
        svc = self._svc_with_mocked_other_triggers(user_id, mocker)

        # tx belongs to a different real user
        _, other_account = self._make_user_and_account()
        tx = TransactionFactory(
            user_id=other_account.user_id, account_id=other_account.id
        )
        Transaction.objects.filter(id=tx.id).update(
            created_at=dt(2026, 4, 29, 19, 30, tzinfo=UTC)
        )
        with freezegun.freeze_time(_MORNING_8_30_UTC):
            tags = self._tags(svc)
        assert "record-reminder-morning-2026-04-30" in tags
