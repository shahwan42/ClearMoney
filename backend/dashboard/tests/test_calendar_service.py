"""Unit tests for CalendarService — financial event aggregation by day."""

import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from dashboard.services.calendar import CalendarService
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    RecurringRuleFactory,
    TransactionFactory,
    UserFactory,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.mark.django_db
class TestCalendarServiceGetMonthEvents:
    """CalendarService.get_month_events() aggregates transactions and recurring rules."""

    def test_empty_month_has_budget_reset_event(self) -> None:
        """Budget Reset event always appears on day 1 even for new users."""
        user = UserFactory()
        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        assert 1 in events
        reset_events = [e for e in events[1] if e["title"] == "Budget Reset"]
        assert len(reset_events) == 1

    def test_transaction_appears_on_correct_day(self) -> None:
        """Actual transactions are grouped under the day they occurred."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
        category = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")

        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            type="expense",
            amount=Decimal("250"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )

        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        assert 15 in events
        tx_events = [e for e in events[15] if e["type"] == "transaction"]
        assert len(tx_events) == 1
        assert tx_events[0]["amount"] == 250.0
        assert tx_events[0]["subtype"] == "expense"
        assert tx_events[0]["is_projection"] is False

    def test_income_transaction_included(self) -> None:
        """Income transactions appear alongside expense transactions."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")

        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            type="income",
            amount=Decimal("5000"),
            currency="EGP",
            date=datetime.date(2026, 3, 1),
        )

        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        income_events = [e for e in events.get(1, []) if e.get("subtype") == "income"]
        assert len(income_events) == 1

    def test_recurring_rule_generates_projection_event(self) -> None:
        """Recurring rules produce is_projection=True events in the calendar."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")

        RecurringRuleFactory(
            user_id=user.id,
            template_transaction={
                "type": "expense",
                "amount": 1500,
                "currency": "EGP",
                "account_id": str(account.id),
            },
            frequency="monthly",
            day_of_month=10,
            next_due_date=datetime.date(2026, 3, 10),
            is_active=True,
        )

        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        recurring_events = [
            e
            for day_events in events.values()
            for e in day_events
            if e["type"] == "recurring"
        ]
        assert len(recurring_events) >= 1
        assert recurring_events[0]["is_projection"] is True

    def test_transactions_outside_month_excluded(self) -> None:
        """Transactions from other months do not appear in the requested month."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")

        # Transaction in February — should NOT appear in March events
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            type="expense",
            amount=Decimal("100"),
            currency="EGP",
            date=datetime.date(2026, 2, 28),
        )

        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        tx_events = [
            e
            for day_events in events.values()
            for e in day_events
            if e["type"] == "transaction"
        ]
        assert len(tx_events) == 0

    def test_data_isolation_between_users(self) -> None:
        """CalendarService only returns events for the requested user."""
        user_a = UserFactory()
        user_b = UserFactory()
        inst_b = InstitutionFactory(user_id=user_b.id)
        account_b = AccountFactory(user_id=user_b.id, institution_id=inst_b.id, currency="EGP")

        TransactionFactory(
            user_id=user_b.id,
            account_id=account_b.id,
            type="expense",
            amount=Decimal("999"),
            currency="EGP",
            date=datetime.date(2026, 3, 20),
        )

        svc = CalendarService(str(user_a.id), TZ)
        events = svc.get_month_events(2026, 3)

        tx_events = [
            e
            for day_events in events.values()
            for e in day_events
            if e["type"] == "transaction"
        ]
        assert len(tx_events) == 0

    def test_multiple_events_same_day(self) -> None:
        """Multiple events on the same day are all included."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
        cat = CategoryFactory(user_id=user.id, type="expense")

        for amount in [100, 200, 300]:
            TransactionFactory(
                user_id=user.id,
                account_id=account.id,
                category_id=cat.id,
                type="expense",
                amount=Decimal(str(amount)),
                currency="EGP",
                date=datetime.date(2026, 3, 5),
            )

        svc = CalendarService(str(user.id), TZ)
        events = svc.get_month_events(2026, 3)

        tx_events = [e for e in events.get(5, []) if e["type"] == "transaction"]
        assert len(tx_events) == 3
