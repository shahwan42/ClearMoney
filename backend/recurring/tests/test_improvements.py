"""Tests for RecurringService improvements."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from recurring.services import RecurringService
from recurring.types import RecurringRulePending
from tests.factories import AccountFactory, InstitutionFactory, UserFactory


@pytest.mark.django_db
class TestRecurringFrequencies:
    def test_advance_biweekly(self):
        user = UserFactory()
        svc = RecurringService(str(user.id), ZoneInfo("UTC"))
        rule = RecurringRulePending(
            id="1", user_id=str(user.id), template_transaction={},
            frequency="biweekly", day_of_month=None, next_due_date=datetime.date(2026, 1, 1),
            is_active=True, auto_confirm=False, created_at=None, updated_at=None
        )
        next_date = svc._advance_due_date(rule)
        assert next_date == datetime.date(2026, 1, 15)

    def test_advance_quarterly(self):
        user = UserFactory()
        svc = RecurringService(str(user.id), ZoneInfo("UTC"))
        rule = RecurringRulePending(
            id="1", user_id=str(user.id), template_transaction={},
            frequency="quarterly", day_of_month=None, next_due_date=datetime.date(2026, 1, 1),
            is_active=True, auto_confirm=False, created_at=None, updated_at=None
        )
        next_date = svc._advance_due_date(rule)
        assert next_date == datetime.date(2026, 4, 1)

    def test_advance_yearly(self):
        user = UserFactory()
        svc = RecurringService(str(user.id), ZoneInfo("UTC"))
        rule = RecurringRulePending(
            id="1", user_id=str(user.id), template_transaction={},
            frequency="yearly", day_of_month=None, next_due_date=datetime.date(2026, 1, 1),
            is_active=True, auto_confirm=False, created_at=None, updated_at=None
        )
        next_date = svc._advance_due_date(rule)
        assert next_date == datetime.date(2027, 1, 1)

@pytest.mark.django_db
class TestRecurringCalendar:
    def test_get_calendar_data(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = RecurringService(str(user.id), ZoneInfo("UTC"))

        # Monthly rule starting Jan 1st
        svc.create({
            "template_transaction": {
                "type": "expense", "amount": 100, "account_id": str(account.id), "note": "Rent"
            },
            "frequency": "monthly",
            "next_due_date": datetime.date(2026, 1, 1),
            "auto_confirm": False
        })

        # Get calendar for March
        occs = svc.get_calendar_data(2026, 3)
        assert len(occs) == 1
        assert occs[0]["due_date"] == datetime.date(2026, 3, 1)
        assert occs[0]["note"] == "Rent"

    def test_get_calendar_data_multiple_occurrences(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = RecurringService(str(user.id), ZoneInfo("UTC"))

        # Weekly rule starting March 1st
        svc.create({
            "template_transaction": {
                "type": "expense", "amount": 50, "account_id": str(account.id), "note": "Weekly"
            },
            "frequency": "weekly",
            "next_due_date": datetime.date(2026, 3, 1),
            "auto_confirm": False
        })

        # March has 5 Sundays in 2026: 1, 8, 15, 22, 29
        occs = svc.get_calendar_data(2026, 3)
        assert len(occs) == 5
        assert occs[0]["due_date"] == datetime.date(2026, 3, 1)
        assert occs[-1]["due_date"] == datetime.date(2026, 3, 29)
