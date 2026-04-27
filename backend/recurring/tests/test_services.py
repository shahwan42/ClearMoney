"""
Recurring service tests — CRUD, confirm/skip, date advancement, auto-processing.

Tests run against the real database with --reuse-db.
"""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from conftest import SessionFactory, UserFactory
from recurring.services import RecurringService
from recurring.types import RecurringRulePending
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
    cat = CategoryFactory(user_id=user.id, name={"en": "Bills"}, type="expense")

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

    def test_confirm_with_actual_amount_uses_actual(self, rec_data):
        """Confirm with actual_amount creates transaction with overridden amount."""
        svc = _svc(rec_data["user_id"])

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, amount=500.0),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        # Actual charge was 475 (cheaper than expected)
        svc.confirm(rule.id, overrides={"amount": 475.0})

        tx = Transaction.objects.get(recurring_rule_id=UUID(rule.id))
        assert float(tx.amount) == 475.0

    def test_confirm_with_actual_amount_updates_balance_correctly(self, rec_data):
        """Balance reflects actual amount, not template amount."""
        svc = _svc(rec_data["user_id"])

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, amount=500.0),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id, overrides={"amount": 600.0})

        balance = float(Account.objects.get(id=rec_data["account_id"]).current_balance)
        assert balance == 49400.0  # 50000 - 600 (actual)

    def test_confirm_without_actual_amount_uses_template(self, rec_data):
        """When actual_amount is None, template amount is used unchanged."""
        svc = _svc(rec_data["user_id"])

        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data, amount=300.0),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)  # no actual_amount

        tx = Transaction.objects.get(recurring_rule_id=UUID(rule.id))
        assert float(tx.amount) == 300.0

    def test_auto_allocates_to_virtual_accounts(self, rec_data):
        """Confirming an income rule auto-allocates to linked VAs with auto_allocate=True."""
        from virtual_accounts.models import VirtualAccount

        svc = _svc(rec_data["user_id"])

        va = VirtualAccount.objects.create(
            user_id=rec_data["user_id"],
            name="Savings",
            account_id=rec_data["account_id"],
            target_amount=10000.0,
            monthly_target=500.0,
            auto_allocate=True,
            current_balance=0.0,
        )

        rule = svc.create(
            {
                "template_transaction": _make_template(
                    rec_data, type="income", amount=2000.0
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        va.refresh_from_db()
        assert float(va.current_balance) == 500.0


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
        rule = RecurringRulePending(
            id="rule-1",
            user_id="fake-user-id",
            template_transaction={"type": "expense", "note": "No amount"},
            frequency="monthly",
            day_of_month=None,
            next_due_date=date(2026, 4, 1),
            is_active=True,
            auto_confirm=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        view = svc.rule_to_view(rule)
        assert view["amount_display"] == "0.00 EGP"
        assert view["note"] == "No amount"

    def test_empty_template_transaction(self) -> None:
        """Completely empty template_transaction still produces valid output."""
        svc = RecurringService("fake-user-id", TZ)
        rule = RecurringRulePending(
            id="rule-2",
            user_id="fake-user-id",
            template_transaction={},
            frequency="monthly",
            day_of_month=None,
            next_due_date=date(2026, 4, 1),
            is_active=True,
            auto_confirm=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        view = svc.rule_to_view(rule)
        # No note, no type → note falls back to empty string from .get("type", "")
        assert view["note"] == ""
        assert view["amount_display"] == "0.00 EGP"


# ---------------------------------------------------------------------------
# execute transfer rules
# ---------------------------------------------------------------------------


@pytest.fixture
def transfer_data(db):
    """User + institution + two same-currency accounts for transfer rule tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)
    source = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Source Account",
        currency="EGP",
        current_balance=20000,
        initial_balance=20000,
    )
    dest = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Dest Account",
        currency="EGP",
        current_balance=5000,
        initial_balance=5000,
    )
    # Fees & Charges category needed for fee transactions
    cat = CategoryFactory(
        user_id=user.id, name={"en": "Fees & Charges"}, type="expense"
    )

    yield {
        "user_id": user_id,
        "source_id": str(source.id),
        "dest_id": str(dest.id),
        "category_id": str(cat.id),
    }


def _make_transfer_template(transfer_data: dict, **overrides) -> dict:
    """Build a transfer template_transaction dict for tests."""
    tmpl = {
        "type": "transfer",
        "amount": 1000.0,
        "currency": "EGP",
        "account_id": transfer_data["source_id"],
        "counter_account_id": transfer_data["dest_id"],
        "note": "Monthly rent",
    }
    tmpl.update(overrides)
    return tmpl


@pytest.mark.django_db
class TestExecuteTransferRule:
    def test_creates_linked_transactions(self, transfer_data):
        """Confirming a transfer rule creates debit + credit transactions."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(transfer_data),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        # Should have 2 linked transfer transactions (debit + credit)
        txs = list(
            Transaction.objects.filter(type="transfer").order_by("balance_delta")
        )
        assert len(txs) == 2
        assert float(txs[0].balance_delta) == -1000.0
        assert float(txs[1].balance_delta) == 1000.0

    def test_updates_both_balances(self, transfer_data):
        """Transfer rule updates source and destination balances."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(
                    transfer_data, amount=5000.0
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        source_balance = float(
            Account.objects.get(id=transfer_data["source_id"]).current_balance
        )
        dest_balance = float(
            Account.objects.get(id=transfer_data["dest_id"]).current_balance
        )
        assert source_balance == 15000.0  # 20000 - 5000
        assert dest_balance == 10000.0  # 5000 + 5000

    def test_with_fee(self, transfer_data):
        """Transfer rule with fee deducts amount + fee from source."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(
                    transfer_data, amount=1000.0, fee_amount=25.0
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        source_balance = float(
            Account.objects.get(id=transfer_data["source_id"]).current_balance
        )
        dest_balance = float(
            Account.objects.get(id=transfer_data["dest_id"]).current_balance
        )
        # Source loses amount + fee
        assert source_balance == 18975.0  # 20000 - 1000 - 25
        # Dest gains amount only
        assert dest_balance == 6000.0  # 5000 + 1000

    def test_missing_counter_account_raises(self, transfer_data):
        """Transfer rule with no counter_account_id raises ValueError."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(
                    transfer_data, counter_account_id=""
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        with pytest.raises(ValueError, match="no counter_account_id"):
            svc.confirm(rule.id)

    def test_advances_due_date(self, transfer_data):
        """Confirming a transfer rule advances the due date."""
        svc = _svc(transfer_data["user_id"])
        today = date.today()
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(transfer_data),
                "frequency": "weekly",
                "next_due_date": today,
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        updated = svc.get_by_id(rule.id)
        assert updated is not None
        assert updated.next_due_date == today + timedelta(days=7)

    def test_auto_process_transfer(self, transfer_data):
        """Auto-confirm transfer rules are processed by process_due_rules."""
        svc = _svc(transfer_data["user_id"])
        svc.create(
            {
                "template_transaction": _make_transfer_template(transfer_data),
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": True,
            }
        )

        count = svc.process_due_rules()
        assert count == 1

        # Balances updated
        source_balance = float(
            Account.objects.get(id=transfer_data["source_id"]).current_balance
        )
        assert source_balance == 19000.0  # 20000 - 1000


@pytest.mark.django_db
class TestRuleToViewTransfer:
    def test_transfer_shows_counter_account_name(self, transfer_data):
        """rule_to_view exposes is_transfer and counter_account_name."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(transfer_data),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )

        view = svc.rule_to_view(rule)
        assert view["is_transfer"] is True
        assert view["source_account_name"] == "Source Account"
        assert view["counter_account_name"] == "Dest Account"

    def test_transfer_with_fee_display(self, transfer_data):
        """rule_to_view shows fee_display for transfer rules with fee."""
        svc = _svc(transfer_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_transfer_template(
                    transfer_data, fee_amount=15.0
                ),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )

        view = svc.rule_to_view(rule)
        assert view["fee_display"] == "15.00 EGP"

    def test_non_transfer_has_no_transfer_fields(self, rec_data):
        """Non-transfer rules have is_transfer=False and no counter fields."""
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": date.today(),
            }
        )

        view = svc.rule_to_view(rule)
        assert view["is_transfer"] is False


# ---------------------------------------------------------------------------
# build_template_transaction — exchange support + tags/va_id/fee for all types
# ---------------------------------------------------------------------------


@pytest.fixture
def exchange_data(db):
    """User + two different-currency accounts for exchange rule tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)
    egp_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="EGP Account",
        currency="EGP",
        current_balance=50000,
        initial_balance=50000,
    )
    usd_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="USD Account",
        currency="USD",
        current_balance=1000,
        initial_balance=1000,
    )

    yield {
        "user_id": user_id,
        "egp_id": str(egp_acct.id),
        "usd_id": str(usd_acct.id),
    }


@pytest.mark.django_db
class TestBuildTemplateTransactionExchange:
    def test_exchange_type_stored(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "exchange",
                "account_id": exchange_data["egp_id"],
                "counter_account_id": exchange_data["usd_id"],
                "amount": 3000.0,
            }
        )
        assert tmpl["type"] == "exchange"
        assert tmpl["account_id"] == exchange_data["egp_id"]
        assert tmpl["counter_account_id"] == exchange_data["usd_id"]
        assert tmpl["amount"] == 3000.0

    def test_exchange_optional_rate_stored(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "exchange",
                "account_id": exchange_data["egp_id"],
                "counter_account_id": exchange_data["usd_id"],
                "amount": 3000.0,
                "exchange_rate": 50.5,
            }
        )
        assert tmpl["exchange_rate"] == 50.5

    def test_exchange_without_rate_ok(self, exchange_data):
        """Rate is optional at rule creation."""
        svc = _svc(exchange_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "exchange",
                "account_id": exchange_data["egp_id"],
                "counter_account_id": exchange_data["usd_id"],
                "amount": 3000.0,
            }
        )
        assert "exchange_rate" not in tmpl

    def test_exchange_missing_dest_raises(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        with pytest.raises(ValueError, match="[Dd]estination"):
            svc.build_template_transaction(
                {
                    "type": "exchange",
                    "account_id": exchange_data["egp_id"],
                    "amount": 3000.0,
                }
            )

    def test_exchange_same_account_raises(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        with pytest.raises(ValueError, match="[Dd]ifferent"):
            svc.build_template_transaction(
                {
                    "type": "exchange",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["egp_id"],
                    "amount": 3000.0,
                }
            )

    def test_transfer_type_diff_currency_auto_detects_exchange(self, exchange_data):
        """Submitting type=transfer with different-currency accounts → stored as exchange."""
        svc = _svc(exchange_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "transfer",
                "account_id": exchange_data["egp_id"],
                "counter_account_id": exchange_data["usd_id"],
                "amount": 3000.0,
            }
        )
        assert tmpl["type"] == "exchange"

    def test_transfer_type_same_currency_stays_transfer(self, transfer_data):
        """Submitting type=transfer with same-currency accounts → stays transfer."""
        svc = _svc(transfer_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "transfer",
                "account_id": transfer_data["source_id"],
                "counter_account_id": transfer_data["dest_id"],
                "amount": 1000.0,
            }
        )
        assert tmpl["type"] == "transfer"


@pytest.mark.django_db
class TestBuildTemplateTransactionOptionalFields:
    def test_expense_stores_tags(self, rec_data):
        svc = _svc(rec_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "expense",
                "account_id": rec_data["account_id"],
                "amount": 100.0,
                "tags": "food,dining",
            }
        )
        assert tmpl["tags"] == "food,dining"

    def test_expense_stores_va_id(self, rec_data):
        svc = _svc(rec_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "expense",
                "account_id": rec_data["account_id"],
                "amount": 100.0,
                "va_id": "some-va-uuid",
            }
        )
        assert tmpl["va_id"] == "some-va-uuid"

    def test_expense_stores_fee(self, rec_data):
        svc = _svc(rec_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "expense",
                "account_id": rec_data["account_id"],
                "amount": 100.0,
                "fee_amount": 5.0,
            }
        )
        assert tmpl["fee_amount"] == 5.0

    def test_income_stores_tags_and_va_id(self, rec_data):
        svc = _svc(rec_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "income",
                "account_id": rec_data["account_id"],
                "amount": 5000.0,
                "tags": "salary",
                "va_id": "va-123",
            }
        )
        assert tmpl["tags"] == "salary"
        assert tmpl["va_id"] == "va-123"

    def test_missing_optional_fields_not_stored(self, rec_data):
        svc = _svc(rec_data["user_id"])
        tmpl = svc.build_template_transaction(
            {
                "type": "expense",
                "account_id": rec_data["account_id"],
                "amount": 100.0,
            }
        )
        assert "tags" not in tmpl
        assert "va_id" not in tmpl
        assert "fee_amount" not in tmpl


# ---------------------------------------------------------------------------
# create — exchange + auto_confirm validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreateExchangeAutoConfirm:
    def test_exchange_with_auto_confirm_raises(self, exchange_data):
        """Exchange rules cannot have auto_confirm=True (rate changes daily)."""
        svc = _svc(exchange_data["user_id"])
        with pytest.raises(
            ValueError, match="[Ee]xchange.*auto.confirm|auto.confirm.*[Ee]xchange"
        ):
            svc.create(
                {
                    "template_transaction": {
                        "type": "exchange",
                        "amount": 3000.0,
                        "currency": "EGP",
                        "account_id": exchange_data["egp_id"],
                        "counter_account_id": exchange_data["usd_id"],
                    },
                    "frequency": "monthly",
                    "next_due_date": date.today(),
                    "auto_confirm": True,
                }
            )

    def test_exchange_with_auto_confirm_false_ok(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": {
                    "type": "exchange",
                    "amount": 3000.0,
                    "currency": "EGP",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["usd_id"],
                },
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )
        assert rule.id
        assert rule.auto_confirm is False


# ---------------------------------------------------------------------------
# update — new method
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdate:
    def test_update_changes_frequency_and_due_date(self, rec_data):
        svc = _svc(rec_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": _make_template(rec_data),
                "frequency": "monthly",
                "next_due_date": date(2026, 5, 1),
                "auto_confirm": False,
            }
        )

        updated = svc.update(
            rule.id,
            {
                "template_transaction": _make_template(rec_data, amount=200.0),
                "frequency": "weekly",
                "next_due_date": date(2026, 5, 15),
                "auto_confirm": True,
            },
        )
        assert updated.frequency == "weekly"
        assert updated.next_due_date == date(2026, 5, 15)
        assert updated.auto_confirm is True
        assert updated.template_transaction["amount"] == 200.0

    def test_update_nonexistent_raises(self, rec_data):
        import uuid

        svc = _svc(rec_data["user_id"])
        with pytest.raises(ValueError, match="[Nn]ot found"):
            svc.update(str(uuid.uuid4()), {"frequency": "weekly"})

    def test_update_exchange_auto_confirm_raises(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": {
                    "type": "exchange",
                    "amount": 3000.0,
                    "currency": "EGP",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["usd_id"],
                },
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )
        with pytest.raises(
            ValueError, match="[Ee]xchange.*auto.confirm|auto.confirm.*[Ee]xchange"
        ):
            svc.update(rule.id, {"auto_confirm": True})


# ---------------------------------------------------------------------------
# _execute_rule — exchange execution + tags/va_id/fee passthrough
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecuteExchangeRule:
    def test_confirm_exchange_creates_transaction(self, exchange_data):
        """Confirming exchange rule with rate creates exchange transactions."""
        svc = _svc(exchange_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": {
                    "type": "exchange",
                    "amount": 3000.0,
                    "currency": "EGP",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["usd_id"],
                },
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        # Rate required at confirm time
        svc.confirm(rule.id, overrides={"exchange_rate": 50.0})

        txs = list(
            Transaction.objects.filter(type="exchange").order_by("balance_delta")
        )
        assert len(txs) == 2

    def test_confirm_exchange_without_rate_raises(self, exchange_data):
        """Confirming exchange rule without rate raises ValueError."""
        svc = _svc(exchange_data["user_id"])
        rule = svc.create(
            {
                "template_transaction": {
                    "type": "exchange",
                    "amount": 3000.0,
                    "currency": "EGP",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["usd_id"],
                },
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        with pytest.raises(ValueError, match="[Rr]ate.*required|[Ee]xchange.*rate"):
            svc.confirm(rule.id)

    def test_confirm_exchange_advances_due_date(self, exchange_data):
        svc = _svc(exchange_data["user_id"])
        today = date.today()
        rule = svc.create(
            {
                "template_transaction": {
                    "type": "exchange",
                    "amount": 3000.0,
                    "currency": "EGP",
                    "account_id": exchange_data["egp_id"],
                    "counter_account_id": exchange_data["usd_id"],
                },
                "frequency": "weekly",
                "next_due_date": today,
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id, overrides={"exchange_rate": 50.0})

        updated = svc.get_by_id(rule.id)
        assert updated is not None
        assert updated.next_due_date == today + timedelta(days=7)


@pytest.mark.django_db
class TestExecuteRuleTagsAndFee:
    def test_confirm_expense_with_tags_applies_tags(self, rec_data):
        """Tags stored in template are applied to created transaction."""
        svc = _svc(rec_data["user_id"])
        tmpl = _make_template(rec_data, tags="food,dining")
        rule = svc.create(
            {
                "template_transaction": tmpl,
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        tx = Transaction.objects.prefetch_related("tags").get(
            recurring_rule_id=UUID(rule.id)
        )
        tag_names = {t.name for t in tx.tags.all()}
        assert "food" in tag_names
        assert "dining" in tag_names

    def test_confirm_with_tags_override(self, rec_data):
        """Tags override at confirm time replaces template tags."""
        svc = _svc(rec_data["user_id"])
        tmpl = _make_template(rec_data, tags="old-tag")
        rule = svc.create(
            {
                "template_transaction": tmpl,
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id, overrides={"tags": "new-tag"})

        tx = Transaction.objects.prefetch_related("tags").get(
            recurring_rule_id=UUID(rule.id)
        )
        tag_names = {t.name for t in tx.tags.all()}
        assert "new-tag" in tag_names
        assert "old-tag" not in tag_names

    def test_confirm_expense_with_fee_creates_fee_tx(self, rec_data):
        """Fee stored in template is applied via apply_post_create_logic."""
        from tests.factories import CategoryFactory

        CategoryFactory(
            user_id=rec_data["user_id"],
            name={"en": "Fees & Charges"},
            type="expense",
        )

        svc = _svc(rec_data["user_id"])
        tmpl = _make_template(rec_data, fee_amount=10.0)
        rule = svc.create(
            {
                "template_transaction": tmpl,
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id)

        # Should have main tx + fee tx
        fee_txs = Transaction.objects.filter(
            note="Transaction fee",
            linked_transaction__recurring_rule_id=UUID(rule.id),
        )
        assert fee_txs.exists()

    def test_confirm_with_fee_override(self, rec_data):
        """Fee override at confirm overrides template fee."""
        from tests.factories import CategoryFactory

        CategoryFactory(
            user_id=rec_data["user_id"],
            name={"en": "Fees & Charges"},
            type="expense",
        )

        svc = _svc(rec_data["user_id"])
        tmpl = _make_template(rec_data)
        rule = svc.create(
            {
                "template_transaction": tmpl,
                "frequency": "monthly",
                "next_due_date": date.today(),
                "auto_confirm": False,
            }
        )

        svc.confirm(rule.id, overrides={"fee_amount": 15.0})

        fee_txs = Transaction.objects.filter(
            note="Transaction fee",
            linked_transaction__recurring_rule_id=UUID(rule.id),
        )
        assert fee_txs.exists()
        fee_tx = fee_txs.first()
        assert fee_tx is not None
        assert float(fee_tx.amount) == 15.0
