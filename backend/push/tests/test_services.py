"""
NotificationService tests — verifies notification generation logic.

Port of Go's internal/service/notifications_test.go plus additional
coverage for each notification trigger type. Uses pytest-mock to patch
DashboardService and RecurringService (unit tests, no DB needed).
"""

from datetime import date
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from pytest_mock import MockerFixture

from dashboard.services import DueSoonCard, HealthWarning
from push.services import NotificationService

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def mock_dashboard(mocker: MockerFixture) -> MagicMock:
    """Patch DashboardService so it doesn't hit the DB."""
    return mocker.patch("push.services.DashboardService")


@pytest.fixture
def mock_recurring(mocker: MockerFixture) -> MagicMock:
    """Patch RecurringService so it doesn't hit the DB."""
    return mocker.patch("push.services.RecurringService")


def _empty_dashboard() -> dict[str, Any]:
    """Return a dashboard dict with no triggers."""
    return {
        "due_soon_cards": [],
        "health_warnings": [],
        "budgets": [],
    }


# ---------------------------------------------------------------------------
# Credit card due soon
# ---------------------------------------------------------------------------


class TestCreditCardDueSoon:
    def test_cc_due_within_3_days(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["due_soon_cards"] = [
            DueSoonCard(
                account_name="CIB Visa",
                due_date=date(2026, 3, 21),
                days_until_due=2,
                balance=-1500.50,
            ),
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Credit Card Due Soon"
        assert "CIB Visa" in n["body"]
        assert "2 day(s)" in n["body"]
        assert "EGP 1500.50" in n["body"]
        assert n["url"] == "/accounts"
        assert n["tag"] == "cc-due-CIB Visa-2026-03-21"

    def test_cc_not_due_skipped(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["due_soon_cards"] = [
            DueSoonCard(
                account_name="HSBC MC",
                due_date=date(2026, 3, 25),
                days_until_due=5,
                balance=-2000.0,
            ),
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 0


# ---------------------------------------------------------------------------
# Health warnings
# ---------------------------------------------------------------------------


class TestHealthWarnings:
    def test_health_warning_notification(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["health_warnings"] = [
            HealthWarning(
                account_name="Savings",
                account_id="acc-123",
                rule="min_balance",
                message="Savings balance is below minimum (EGP 500)",
            ),
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
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
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["budgets"] = [
            {
                "id": "b-1",
                "category_id": "cat-1",
                "category_name": "Groceries",
                "category_icon": "\U0001f6d2",
                "monthly_limit": 2000.0,
                "spent": 1700.0,
                "percentage": 85.0,
                "currency": "EGP",
                "status": "amber",
            },
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        n = notifications[0]
        assert n["title"] == "Budget Warning"
        assert "85%" in n["body"]
        assert "EGP 300 remaining" in n["body"]
        assert n["tag"] == "budget-warning-cat-1"

    def test_budget_exceeded_at_100pct(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["budgets"] = [
            {
                "id": "b-2",
                "category_id": "cat-2",
                "category_name": "Transport",
                "category_icon": "",
                "monthly_limit": 500.0,
                "spent": 550.0,
                "percentage": 110.0,
                "currency": "EGP",
                "status": "red",
            },
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
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
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        data = _empty_dashboard()
        data["budgets"] = [
            {
                "id": "b-3",
                "category_id": "cat-3",
                "category_name": "Fun",
                "category_icon": "",
                "monthly_limit": 1000.0,
                "spent": 500.0,
                "percentage": 50.0,
                "currency": "EGP",
                "status": "green",
            },
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 0


# ---------------------------------------------------------------------------
# Recurring transactions due
# ---------------------------------------------------------------------------


class TestRecurringDue:
    def test_recurring_due_notification(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        mock_dashboard.return_value.get_dashboard.return_value = _empty_dashboard()
        mock_recurring.return_value.get_due_pending.return_value = [
            {
                "id": "rule-1",
                "frequency": "monthly",
                "next_due_date": date(2026, 3, 19),
                "auto_confirm": False,
            },
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
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        mock_dashboard.return_value.get_dashboard.return_value = _empty_dashboard()
        mock_recurring.return_value.get_due_pending.return_value = []

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert notifications == []

    def test_dashboard_error_still_returns_recurring(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        """If DashboardService fails, recurring notifications still work."""
        mock_dashboard.return_value.get_dashboard.side_effect = RuntimeError("db down")
        mock_recurring.return_value.get_due_pending.return_value = [
            {
                "id": "rule-2",
                "frequency": "weekly",
                "next_due_date": date(2026, 3, 19),
                "auto_confirm": False,
            },
        ]

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        assert notifications[0]["title"] == "Recurring Transaction Due"

    def test_recurring_error_still_returns_dashboard(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        """If RecurringService fails, dashboard notifications still work."""
        data = _empty_dashboard()
        data["health_warnings"] = [
            HealthWarning(
                account_name="Checking",
                account_id="acc-456",
                rule="min_monthly_deposit",
                message="No deposit this month",
            ),
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.side_effect = RuntimeError(
            "db down"
        )

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        assert len(notifications) == 1
        assert notifications[0]["title"] == "Account Health Warning"

    def test_multiple_triggers_combined(
        self, mock_dashboard: MagicMock, mock_recurring: MagicMock
    ) -> None:
        """All trigger types can appear in one response."""
        data = _empty_dashboard()
        data["due_soon_cards"] = [
            DueSoonCard("Card A", date(2026, 3, 20), 1, -500.0),
        ]
        data["health_warnings"] = [
            HealthWarning("Savings", "acc-1", "min_balance", "Low balance"),
        ]
        data["budgets"] = [
            {
                "id": "b-1",
                "category_id": "cat-1",
                "category_name": "Food",
                "category_icon": "",
                "monthly_limit": 1000.0,
                "spent": 1100.0,
                "percentage": 110.0,
                "currency": "EGP",
                "status": "red",
            },
        ]
        mock_dashboard.return_value.get_dashboard.return_value = data
        mock_recurring.return_value.get_due_pending.return_value = [
            {
                "id": "r-1",
                "frequency": "daily",
                "next_due_date": date(2026, 3, 19),
                "auto_confirm": False,
            },
        ]

        svc = NotificationService("user-1", TZ)
        notifications = svc.get_pending_notifications()

        titles = [n["title"] for n in notifications]
        assert "Credit Card Due Soon" in titles
        assert "Account Health Warning" in titles
        assert "Budget Exceeded" in titles
        assert "Recurring Transaction Due" in titles
        assert len(notifications) == 4
