"""
Recurring service tests — CRUD, confirm/skip, date advancement, auto-processing.

Tests run against the real database with --reuse-db.
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from conftest import SessionFactory, UserFactory
from recurring.services import RecurringService
from tests.factories import AccountFactory, CategoryFactory, InstitutionFactory
from transactions.models import Transaction

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def rec_data(db):
    """User + institution + account + category for recurring tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Checking",
        currency="EGP",
        current_balance=50000,
        initial_balance=50000,
    )
    cat = CategoryFactory(user_id=user.id, name="Bills", type="expense")

    yield {
        "user_id": user_id,
        "account_id": str(acct.id),
        "category_id": str(cat.id),
    }


def _svc(user_id: str) -> RecurringService:
    return RecurringService(user_id, TZ)


def _make_template(rec_data: dict, **overrides) -> dict:
    """Build a template_transaction dict for tests."""
    tmpl = {
        "type": "expense",
        "amount": 100.0,
        "currency": "EGP",
        "account_id": rec_data["account_id"],
        "category_id": rec_data["category_id"],
        "note": "Monthly Netflix",
    }
    tmpl.update(overrides)
    return tmpl


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAll:
    def test_empty(self, rec_data):
        svc = _svc(rec_data["user_id"])
        assert svc.get_all() == []

    def test_ordered_by_due_date(self, rec_data):
        svc = _svc(rec_data["user_id"])
        svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": date(2026, 4, 15),
                "auto_confirm": False,
            }
        )
        svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "weekly",
                "next_due_date": date(2026, 3, 1),
                "auto_confirm": False,
            }
        )

        rules = svc.get_all()
        assert len(rules) == 2
        assert rules[0].next_due_date <= rules[1].next_due_date


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_valid(self, rec_data):
        svc = _svc(rec_data["user_id"])
        result = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": date(2026, 4, 1),
                "auto_confirm": True,
            }
        )
        assert result.id
        assert result.frequency == "monthly"
        assert result.auto_confirm is True
        assert result.template_transaction["note"] == "Monthly Netflix"

    def test_missing_template(self, rec_data):
        svc = _svc(rec_data["user_id"])
        with pytest.raises(ValueError, match="template_transaction"):
            svc.create(
                {
                    "frequency": "monthly",
                    "next_due_date": date(2026, 4, 1),
                }
            )

    def test_missing_frequency(self, rec_data):
        svc = _svc(rec_data["user_id"])
        with pytest.raises(ValueError, match="frequency"):
            svc.create(
                {
                    "template_transaction": _make_template(rec_data),
                    "next_due_date": date(2026, 4, 1),
                }
            )

    def test_missing_due_date(self, rec_data):
        svc = _svc(rec_data["user_id"])
        with pytest.raises(ValueError, match="next_due_date"):
            svc.create(
                {
                    "template_transaction": _make_template(rec_data),
                    "frequency": "monthly",
                }
            )


# ---------------------------------------------------------------------------
# get_due_pending
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetDuePending:
    def test_filters_auto_confirm(self, rec_data):
        """Only returns rules where auto_confirm=false."""
        svc = _svc(rec_data["user_id"])
        yesterday = date.today() - timedelta(days=1)

        # auto_confirm=true rule — should NOT appear in pending
        svc.create(
            {
                "template_transaction": _make_template(rec_data, note="Auto"),
                "frequency": "monthly",
                "next_due_date": yesterday,
                "auto_confirm": True,
            }
        )
        # auto_confirm=false rule — should appear in pending
        svc.create(
            {
                "template_transaction": _make_template(rec_data, note="Manual"),
                "frequency": "monthly",
                "next_due_date": yesterday,
                "auto_confirm": False,
            }
        )

        pending = svc.get_due_pending()
        assert len(pending) == 1
        assert pending[0].template_transaction["note"] == "Manual"

    def test_excludes_future_rules(self, rec_data):
        """Rules with next_due_date in the future are not pending."""
        svc = _svc(rec_data["user_id"])
        future = date.today() + timedelta(days=30)

        svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": future,
                "auto_confirm": False,
            }
        )

        pending = svc.get_due_pending()
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# confirm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirm:
    def test_creates_transaction_and_advances_date(self, rec_data):
        svc = _svc(rec_data["user_id"])
        yesterday = date.today() - timedelta(days=1)

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": yesterday,
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        # Date should have advanced by 1 month
        updated_rule = svc.get_by_id(rule.id)
        assert updated_rule is not None
        assert updated_rule.next_due_date > yesterday

        # Transaction should have been created via ORM
        count = Transaction.objects.filter(recurring_rule_id=UUID(rule.id)).count()
        assert count == 1

    def test_updates_account_balance(self, rec_data):
        """Confirm should deduct from account balance (expense)."""
        svc = _svc(rec_data["user_id"])

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, amount=500.0),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        balance = float(Account.objects.get(id=rec_data["account_id"]).current_balance)
        assert balance == 49500.0  # 50000 - 500


# ---------------------------------------------------------------------------
# skip
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSkip:
    def test_advances_date_no_transaction(self, rec_data):
        svc = _svc(rec_data["user_id"])
        yesterday = date.today() - timedelta(days=1)

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "weekly",
                "next_due_date": yesterday,
                "auto_confirm": False,
            }
        )

        svc.skip(rule.id)

        # Date should have advanced by 7 days
        updated = svc.get_by_id(rule.id)
        assert updated is not None
        assert updated.next_due_date == yesterday + timedelta(days=7)

        # No transaction should have been created
        count = Transaction.objects.filter(recurring_rule_id=UUID(rule.id)).count()
        assert count == 0


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDelete:
    def test_removes_rule(self, rec_data):
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )

        svc.delete(rule.id)
        assert svc.get_by_id(rule.id) is None


# ---------------------------------------------------------------------------
# advance_due_date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdvanceDueDate:
    def test_weekly(self, rec_data):
        from datetime import datetime

        from recurring.types import RecurringRulePending

        svc = _svc(rec_data["user_id"])
        rule = RecurringRulePending(
            id="test-id",
            user_id=rec_data["user_id"],
            next_due_date=date(2026, 3, 15),
            frequency="weekly",
            day_of_month=None,
            is_active=True,
            auto_confirm=False,
            template_transaction={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert svc._advance_due_date(rule) == date(2026, 3, 22)

    def test_monthly(self, rec_data):
        from datetime import datetime

        from recurring.types import RecurringRulePending

        svc = _svc(rec_data["user_id"])
        rule = RecurringRulePending(
            id="test-id",
            user_id=rec_data["user_id"],
            next_due_date=date(2026, 3, 15),
            frequency="monthly",
            day_of_month=None,
            is_active=True,
            auto_confirm=False,
            template_transaction={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert svc._advance_due_date(rule) == date(2026, 4, 15)

    def test_monthly_overflow_clamps(self, rec_data):
        """Jan 31 + 1 month = Feb 28 (dateutil clamps month overflow)."""
        from datetime import datetime

        from recurring.types import RecurringRulePending

        svc = _svc(rec_data["user_id"])
        rule = RecurringRulePending(
            id="test-id",
            user_id=rec_data["user_id"],
            next_due_date=date(2026, 1, 31),
            frequency="monthly",
            day_of_month=None,
            is_active=True,
            auto_confirm=False,
            template_transaction={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert svc._advance_due_date(rule) == date(2026, 2, 28)


# ---------------------------------------------------------------------------
# process_due_rules
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProcessDueRules:
    def test_only_auto_confirm(self, rec_data):
        """ProcessDueRules only executes auto_confirm=true rules."""
        svc = _svc(rec_data["user_id"])
        yesterday = date.today() - timedelta(days=1)

        # Manual rule — should NOT be processed
        svc.create(
            {
                "template_transaction": _make_template(rec_data, note="Manual"),
                "frequency": "monthly",
                "next_due_date": yesterday,
                "auto_confirm": False,
            }
        )
        # Auto rule — should be processed
        auto_rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, note="Auto"),
                "frequency": "monthly",
                "next_due_date": yesterday,
                "auto_confirm": True,
            }
        )

        count = svc.process_due_rules()
        assert count == 1

        # Auto rule date advanced
        updated = svc.get_by_id(auto_rule.id)
        assert updated is not None
        assert updated.next_due_date > yesterday


# ---------------------------------------------------------------------------
# execute_rule edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecuteRule:
    def test_missing_account_raises(self, rec_data):
        """Rule with empty account_id should raise ValueError."""
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, account_id=""),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )
        with pytest.raises(ValueError, match="no account_id"):
            svc.confirm(rule.id)


# ---------------------------------------------------------------------------
# rule_to_view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRuleToView:
    def test_extracts_note_and_amount(self, rec_data):
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(
                    rec_data, note="Netflix", amount=199.99
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )
        view = svc.rule_to_view(rule)
        assert view["note"] == "Netflix"
        assert view["amount_display"] == "199.99 EGP"

    def test_fallback_to_type_when_no_note(self, rec_data):
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, note=None),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )
        # Remove note key to simulate missing note
        rule.template_transaction.pop("note", None)
        view = svc.rule_to_view(rule)
        assert view["note"] == "expense"


# ---------------------------------------------------------------------------
# rule_to_view edge cases — missing/empty template fields
# ---------------------------------------------------------------------------


class TestRuleToViewEdgeCases:
    """rule_to_view handles incomplete template_transaction data gracefully."""

    def test_missing_amount_in_template(self) -> None:
        """Template with no 'amount' key defaults to 0 in display."""
        svc = RecurringService("fake-user-id", TZ)
        rule: dict[str, Any] = {
            "id": "rule-1",
            "user_id": "fake-user-id",
            "template_transaction": {"type": "expense", "note": "No amount"},
            "frequency": "monthly",
            "day_of_month": None,
            "next_due_date": date(2026, 4, 1),
            "is_active": True,
            "auto_confirm": False,
            "created_at": None,
            "updated_at": None,
        }
        view = svc.rule_to_view(rule)
        assert view["amount_display"] == "0.00 EGP"
        assert view["note"] == "No amount"

    def test_empty_template_transaction(self) -> None:
        """Completely empty template_transaction still produces valid output."""
        svc = RecurringService("fake-user-id", TZ)
        rule: dict[str, Any] = {
            "id": "rule-2",
            "user_id": "fake-user-id",
            "template_transaction": {},
            "frequency": "monthly",
            "day_of_month": None,
            "next_due_date": date(2026, 4, 1),
            "is_active": True,
            "auto_confirm": False,
            "created_at": None,
            "updated_at": None,
        }
        view = svc.rule_to_view(rule)
        # No note, no type → note falls back to empty string from .get("type", "")
        assert view["note"] == ""
        assert view["amount_display"] == "0.00 EGP"
