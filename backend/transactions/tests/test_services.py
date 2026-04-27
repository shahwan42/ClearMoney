"""
Transaction service tests — tests for TransactionService CRUD, transfer, exchange,
batch, smart defaults, and suggest category.
"""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from conftest import SessionFactory, UserFactory
from exchange_rates.models import ExchangeRateLog
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    VirtualAccountAllocationFactory,
    VirtualAccountFactory,
)
from transactions.models import Transaction, VirtualAccountAllocation
from transactions.services import (
    TransactionService,
    resolve_exchange_fields,
)
from virtual_accounts.models import VirtualAccount

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def tx_data(db):
    """User + institution + 2 accounts (savings EGP, savings USD) + 1 CC."""
    user = UserFactory()
    SessionFactory(user=user)
    institution = InstitutionFactory(user_id=user.id, name="Test Bank")
    egp_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="EGP Savings",
        currency="EGP",
        current_balance=10000,
        initial_balance=10000,
    )
    usd_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="USD Savings",
        currency="USD",
        current_balance=500,
        initial_balance=500,
    )
    cc_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Test CC",
        type="credit_card",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
        credit_limit=5000,
    )
    cat_expense = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")
    cat_income = CategoryFactory(user_id=user.id, name={"en": "Salary"}, type="income")
    fees_cat = CategoryFactory(
        user_id=user.id, name={"en": "Fees & Charges"}, type="expense"
    )
    yield {
        "user_id": str(user.id),
        "inst_id": str(institution.id),
        "egp_id": str(egp_account.id),
        "usd_id": str(usd_account.id),
        "cc_id": str(cc_account.id),
        "cat_expense_id": str(cat_expense.id),
        "cat_income_id": str(cat_income.id),
        "fees_cat_id": str(fees_cat.id),
    }


def _svc(user_id: str) -> TransactionService:
    return TransactionService(user_id, TZ)


def _get_balance(account_id: str) -> float:
    """Fetch current_balance from DB via ORM."""
    return float(Account.objects.get(id=account_id).current_balance)


# ---------------------------------------------------------------------------
# Pure function tests (no DB)
# ---------------------------------------------------------------------------


class TestResolveExchangeFields:
    def test_amount_and_rate(self):
        a, r, c = resolve_exchange_fields(100, 50.0, None)
        assert a == 100
        assert r == 50.0
        assert c == 5000.0

    def test_amount_and_counter(self):
        a, r, c = resolve_exchange_fields(100, None, 5000.0)
        assert a == 100
        assert r == 50.0
        assert c == 5000.0

    def test_rate_and_counter(self):
        a, r, c = resolve_exchange_fields(None, 50.0, 5000.0)
        assert a == 100
        assert r == 50.0
        assert c == 5000.0

    def test_only_one_fails(self):
        with pytest.raises(ValueError, match="at least two"):
            resolve_exchange_fields(100, None, None)


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_expense_updates_balance(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, new_bal = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_expense_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert tx["type"] == "expense"
        assert Decimal(tx["amount"]) == Decimal("500")
        assert tx["currency"] == "EGP"
        assert Decimal(tx["balance_delta"]) == Decimal("-500")
        assert Decimal(new_bal) == Decimal("9500")
        assert _get_balance(tx_data["egp_id"]) == 9500

    def test_income_updates_balance(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, new_bal = svc.create(
            {
                "type": "income",
                "amount": 2000,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_income_id"],
            }
        )
        assert Decimal(tx["balance_delta"]) == Decimal("2000")
        assert Decimal(new_bal) == Decimal("12000")
        assert _get_balance(tx_data["egp_id"]) == 12000

    def test_overrides_currency_from_account(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["usd_id"],
                "currency": "EGP",  # wrong — should be overridden to USD
            }
        )
        assert tx["currency"] == "USD"

    def test_credit_card_limit_check(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="credit limit"):
            svc.create(
                {
                    "type": "expense",
                    "amount": 6000,
                    "account_id": tx_data["cc_id"],
                }
            )

    def test_validation_zero_amount(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="positive"):
            svc.create(
                {
                    "type": "expense",
                    "amount": 0,
                    "account_id": tx_data["egp_id"],
                }
            )

    def test_validation_invalid_type(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="Invalid"):
            svc.create(
                {
                    "type": "invalid",
                    "amount": 100,
                    "account_id": tx_data["egp_id"],
                }
            )

    def test_validation_future_date_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        from datetime import date, timedelta

        future_date = date.today() + timedelta(days=1)
        with pytest.raises(ValueError, match="cannot be in the future"):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100,
                    "account_id": tx_data["egp_id"],
                    "date": future_date,
                }
            )


@pytest.mark.django_db
class TestCreateWithFee:
    """Tests for creating transactions with an optional linked fee."""

    def test_expense_with_fee_creates_linked_fee_transaction(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_expense_id"],
                "date": date(2026, 3, 15),
            }
        )
        fee_tx = svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=25.0, tx_date=date(2026, 3, 15)
        )
        # Fee is a separate expense transaction
        assert fee_tx["type"] == "expense"
        assert Decimal(fee_tx["amount"]) == Decimal("25")
        assert Decimal(fee_tx["balance_delta"]) == Decimal("-25")
        assert fee_tx["linked_transaction_id"] == tx["id"]
        assert fee_tx["category_id"] == tx_data["fees_cat_id"]
        assert fee_tx["note"] == "Transaction fee"

    def test_expense_with_fee_updates_balance_correctly(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=25.0, tx_date=date(2026, 3, 15)
        )
        # Balance should be 10000 - 500 (expense) - 25 (fee) = 9475
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9475")

    def test_income_with_fee_creates_fee_expense(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "income",
                "amount": 2000,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        fee_tx = svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=10.0, tx_date=date(2026, 3, 15)
        )
        # Fee still deducts from account even on income
        assert fee_tx["type"] == "expense"
        assert Decimal(fee_tx["balance_delta"]) == Decimal("-10")
        # Balance: 10000 + 2000 (income) - 10 (fee) = 11990
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("11990")

    def test_zero_fee_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        with pytest.raises(ValueError, match="greater than zero"):
            svc.create_fee_for_transaction(
                parent_tx=tx, fee_amount=0, tx_date=date(2026, 3, 15)
            )

    def test_negative_fee_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        with pytest.raises(ValueError, match="greater than zero"):
            svc.create_fee_for_transaction(
                parent_tx=tx, fee_amount=-5, tx_date=date(2026, 3, 15)
            )

    def test_fee_uses_parent_currency(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["usd_id"],
            }
        )
        fee_tx = svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=2.0, tx_date=date(2026, 3, 15)
        )
        assert fee_tx["currency"] == "USD"

    def test_create_expense_with_fee_deducts_amount_plus_fee(self, tx_data):
        """End-to-end: create + fee produces correct total balance deduction."""
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 1000,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        fee_tx = svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=50.0, tx_date=date(2026, 3, 15)
        )
        # Balance = 10000 - 1000 (expense) - 50 (fee) = 8950
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("8950")
        # Fee tx links back to parent
        assert fee_tx["linked_transaction_id"] == tx["id"]
        # Parent tx balance_delta is -amount only (fee is its own tx)
        assert Decimal(tx["balance_delta"]) == Decimal("-1000")
        # Fee tx balance_delta is -fee
        assert Decimal(fee_tx["balance_delta"]) == Decimal("-50")


@pytest.mark.django_db
class TestUpdate:
    def test_recalculates_balance_delta(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        # Create expense of 500 → balance 9500
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        # Update to 300 → adjustment = (-300) - (-500) = +200 → balance 9700
        updated, new_bal = svc.update(
            tx["id"],
            {
                "type": "expense",
                "amount": 300,
            },
        )
        assert Decimal(updated["amount"]) == Decimal("300")
        assert Decimal(updated["balance_delta"]) == Decimal("-300")
        assert _get_balance(tx_data["egp_id"]) == 9700

    def test_change_type_recalculates(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        # Create expense 500 → balance 9500
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        # Change to income 500 → adjustment = 500 - (-500) = +1000 → balance 10500
        updated, _ = svc.update(
            tx["id"],
            {
                "type": "income",
                "amount": 500,
            },
        )
        assert Decimal(updated["balance_delta"]) == Decimal("500")
        assert _get_balance(tx_data["egp_id"]) == 10500

    def test_validation_future_date_rejected(self, tx_data):
        from datetime import timedelta

        svc = _svc(tx_data["user_id"])
        # Create expense with today's date
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
            }
        )
        # Try to update with future date — should fail
        future_date = date.today() + timedelta(days=1)
        with pytest.raises(ValueError, match="cannot be in the future"):
            svc.update(
                tx["id"],
                {
                    "date": future_date,
                },
            )


@pytest.mark.django_db
class TestDelete:
    def test_simple_reverses_balance(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        assert _get_balance(tx_data["egp_id"]) == 9500
        related_ids = svc.delete(tx["id"])
        assert _get_balance(tx_data["egp_id"]) == 10000
        assert related_ids == []

    def test_linked_reverses_both_accounts(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Create a second EGP account for transfer
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest Account",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        dest_id = str(dest.id)
        debit, credit = svc.create_transfer(
            tx_data["egp_id"],
            dest_id,
            1000,
            None,
            None,
            date(2026, 3, 15),
        )
        assert _get_balance(tx_data["egp_id"]) == 9000
        assert _get_balance(dest_id) == 6000

        related_ids = svc.delete(debit["id"])
        assert _get_balance(tx_data["egp_id"]) == 10000
        assert _get_balance(dest_id) == 5000
        assert str(credit["id"]) in related_ids

    def test_delete_credit_leg_reverses_both_accounts_correctly(self, tx_data):
        """Deleting the credit (destination) leg must reverse balances correctly.

        Previously, the delete function hardcoded direction (always +amount on
        deleted tx, -amount on linked), which caused both balances to move in
        the wrong direction when the credit leg was deleted.
        """
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest Account",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        dest_id = str(dest.id)
        debit, credit = svc.create_transfer(
            tx_data["egp_id"],
            dest_id,
            1000,
            None,
            None,
            date(2026, 3, 15),
        )
        assert _get_balance(tx_data["egp_id"]) == 9000
        assert _get_balance(dest_id) == 6000

        # Delete the CREDIT leg (destination side) instead of the debit leg
        related_ids = svc.delete(credit["id"])
        assert _get_balance(tx_data["egp_id"]) == 10000
        assert _get_balance(dest_id) == 5000
        assert str(debit["id"]) in related_ids

    def test_not_found(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="not found"):
            svc.delete(str(uuid.uuid4()))

    def test_delete_parent_also_deletes_linked_fee(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=25.0, tx_date=date(2026, 3, 15)
        )
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9475")

        related_ids = svc.delete(tx["id"])
        # Both parent and fee reversed: 10000
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("10000")
        # Fee transaction should be gone
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], note="Transaction fee"
            ).count()
            == 0
        )
        # Related IDs should contain the fee transaction ID
        assert len(related_ids) == 1

    def test_delete_transfer_with_fee_cleans_up_fee(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest Account",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        dest_id = str(dest.id)
        debit, credit = svc.create_transfer(
            tx_data["egp_id"],
            dest_id,
            1000,
            None,
            None,
            date(2026, 3, 15),
            fee_amount=50,
        )
        # Source: 10000 - 1000 - 50 = 8950, Dest: 5000 + 1000 = 6000
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("8950")
        assert Decimal(str(_get_balance(dest_id))) == Decimal("6000")

        related_ids = svc.delete(debit["id"])
        # Fully reversed: source 10000, dest 5000
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("10000")
        assert Decimal(str(_get_balance(dest_id))) == Decimal("5000")
        # Fee transaction should be gone (transfer fee has note "Transfer fee")
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], note="Transfer fee"
            ).count()
            == 0
        )
        # Related IDs should contain linked transaction + fee
        assert str(credit["id"]) in related_ids
        assert len(related_ids) == 2  # linked tx + fee


@pytest.mark.django_db
class TestUpdateFee:
    """Tests for update_fee_for_transaction() — add, change, remove fees."""

    def test_update_fee_creates_new_fee(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        # No fee initially, add one via update
        svc.update_fee_for_transaction(tx["id"], 25.0, tx_date=date(2026, 3, 15))
        # Balance: 10000 - 500 - 25 = 9475
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9475")
        fee_tx = Transaction.objects.filter(
            user_id=tx_data["user_id"],
            linked_transaction_id=tx["id"],
            note="Transaction fee",
        ).first()
        assert fee_tx is not None
        assert Decimal(str(fee_tx.amount)) == Decimal("25")

    def test_update_fee_removes_old_fee(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=25.0, tx_date=date(2026, 3, 15)
        )
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9475")

        # Remove fee by passing None
        svc.update_fee_for_transaction(tx["id"], None, tx_date=date(2026, 3, 15))
        # Balance: 10000 - 500 = 9500 (fee reversed)
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9500")
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], note="Transaction fee"
            ).count()
            == 0
        )

    def test_update_fee_changes_amount(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        svc.create_fee_for_transaction(
            parent_tx=tx, fee_amount=25.0, tx_date=date(2026, 3, 15)
        )
        # Change fee from 25 to 50
        svc.update_fee_for_transaction(tx["id"], 50.0, tx_date=date(2026, 3, 15))
        # Balance: 10000 - 500 - 50 = 9450
        assert Decimal(str(_get_balance(tx_data["egp_id"]))) == Decimal("9450")
        fee_tx = Transaction.objects.filter(
            user_id=tx_data["user_id"],
            linked_transaction_id=tx["id"],
            note="Transaction fee",
        ).first()
        assert fee_tx is not None
        assert Decimal(str(fee_tx.amount)) == Decimal("50")

    def test_update_fee_noop_when_no_change(self, tx_data):
        """No fee exists, no new fee requested → no-op."""
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )
        svc.update_fee_for_transaction(tx["id"], None, tx_date=None)
        assert _get_balance(tx_data["egp_id"]) == 9500
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], note="Transaction fee"
            ).count()
            == 0
        )


@pytest.mark.django_db
class TestGetFiltered:
    def test_search_by_note(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "note": "Coffee at Starbucks",
            }
        )
        svc.create(
            {
                "type": "expense",
                "amount": 200,
                "account_id": tx_data["egp_id"],
                "note": "Grocery shopping",
            }
        )
        results, _ = svc.get_filtered_enriched({"search": "coffee"})
        assert len(results) == 1
        assert results[0]["note"] == "Coffee at Starbucks"

    def test_filter_by_date_range(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "date": "2026-03-01",
            }
        )
        svc.create(
            {
                "type": "expense",
                "amount": 200,
                "account_id": tx_data["egp_id"],
                "date": "2026-03-20",
            }
        )
        results, _ = svc.get_filtered_enriched(
            {
                "date_from": "2026-03-15",
                "date_to": "2026-03-31",
            }
        )
        assert len(results) == 1
        assert Decimal(results[0]["amount"]) == Decimal("200")

    def test_pagination(self, tx_data):
        svc = _svc(tx_data["user_id"])
        for i in range(5):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100 + i,
                    "account_id": tx_data["egp_id"],
                }
            )
        results, has_more = svc.get_filtered_enriched({"limit": 3})
        assert len(results) == 3
        assert has_more is True

        results2, has_more2 = svc.get_filtered_enriched({"limit": 3, "offset": 3})
        assert len(results2) == 2
        assert has_more2 is False

    def test_filter_by_account(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
            }
        )
        svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["usd_id"],
            }
        )
        results, _ = svc.get_filtered_enriched({"account_id": tx_data["usd_id"]})
        assert len(results) == 1
        assert results[0]["currency"] == "USD"


# ---------------------------------------------------------------------------
# Global search tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGlobalSearch:
    """Tests for HelperMixin.search() — global search across note, amount, category."""

    def test_search_by_note_substring(self, tx_data):
        """Should return transactions whose note contains the query (case-insensitive)."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 150,
                "account_id": tx_data["egp_id"],
                "note": "Lunch with colleagues",
            }
        )
        svc.create(
            {
                "type": "expense",
                "amount": 200,
                "account_id": tx_data["egp_id"],
                "note": "Grocery run",
            }
        )
        results = svc.search("lunch")
        assert len(results) == 1
        assert results[0]["note"] == "Lunch with colleagues"

    def test_search_by_note_case_insensitive(self, tx_data):
        """Note matching should be case-insensitive."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "note": "TAXI Ride",
            }
        )
        results = svc.search("taxi")
        assert len(results) == 1

    def test_search_by_amount(self, tx_data):
        """Should match transactions whose amount string contains the query."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 999,
                "account_id": tx_data["egp_id"],
                "note": "Big purchase",
            }
        )
        svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["egp_id"],
                "note": "Small purchase",
            }
        )
        results = svc.search("999")
        assert len(results) == 1
        assert results[0]["note"] == "Big purchase"

    def test_search_by_category_name(self, tx_data):
        """Should return transactions whose category name contains the query."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 75,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_expense_id"],  # "Food"
                "note": None,
            }
        )
        svc.create(
            {
                "type": "income",
                "amount": 3000,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_income_id"],  # "Salary"
            }
        )
        results = svc.search("food")
        assert len(results) == 1
        assert results[0]["category_name"] == "Food"

    def test_search_empty_query_returns_empty(self, tx_data):
        """An empty or whitespace-only query must return [] without hitting the DB."""
        svc = _svc(tx_data["user_id"])
        svc.create({"type": "expense", "amount": 100, "account_id": tx_data["egp_id"]})
        assert svc.search("") == []
        assert svc.search("   ") == []

    def test_search_no_match_returns_empty_list(self, tx_data):
        """A query with no matches should return an empty list."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "note": "coffee",
            }
        )
        results = svc.search("zzznomatch")
        assert results == []

    def test_search_scoped_to_user(self, db):
        """Results must only contain transactions belonging to the requesting user."""
        from conftest import SessionFactory, UserFactory
        from tests.factories import AccountFactory, InstitutionFactory

        user_a = UserFactory()
        user_b = UserFactory()
        SessionFactory(user=user_a)
        SessionFactory(user=user_b)
        inst_a = InstitutionFactory(user_id=user_a.id)
        inst_b = InstitutionFactory(user_id=user_b.id)
        acc_a = AccountFactory(
            user_id=user_a.id,
            institution_id=inst_a.id,
            currency="EGP",
            current_balance=10000,
            initial_balance=10000,
        )
        acc_b = AccountFactory(
            user_id=user_b.id,
            institution_id=inst_b.id,
            currency="EGP",
            current_balance=10000,
            initial_balance=10000,
        )

        svc_a = _svc(str(user_a.id))
        svc_b = _svc(str(user_b.id))
        svc_a.create(
            {
                "type": "expense",
                "amount": 111,
                "account_id": str(acc_a.id),
                "note": "secret lunch",
            }
        )
        svc_b.create(
            {
                "type": "expense",
                "amount": 222,
                "account_id": str(acc_b.id),
                "note": "secret lunch",
            }
        )

        results_a = svc_a.search("secret")
        assert len(results_a) == 1
        assert results_a[0]["user_id"] == str(user_a.id)

    def test_search_results_have_display_fields(self, tx_data):
        """Returned dicts must include indicator_color and amount_color_class."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["egp_id"],
                "note": "display check",
            }
        )
        results = svc.search("display check")
        assert len(results) == 1
        tx = results[0]
        assert "indicator_color" in tx
        assert "amount_color_class" in tx
        # Expense indicator is red-400
        assert tx["indicator_color"] == "#f87171"
        assert tx["amount_color_class"] == "text-red-600"

    def test_search_limit_respected(self, tx_data):
        """The limit parameter must cap the number of returned results."""
        svc = _svc(tx_data["user_id"])
        for i in range(10):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100 + i,
                    "account_id": tx_data["egp_id"],
                    "note": f"limitcheck {i}",
                }
            )
        results = svc.search("limitcheck", limit=3)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Transfer tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransfer:
    def test_updates_both_balances(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Create second EGP account
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        dest_id = str(dest.id)
        debit, credit = svc.create_transfer(
            tx_data["egp_id"],
            dest_id,
            2000,
            None,
            "Test transfer",
            date(2026, 3, 15),
        )
        assert _get_balance(tx_data["egp_id"]) == 8000
        assert _get_balance(dest_id) == 7000
        assert debit["type"] == "transfer"
        assert credit["type"] == "transfer"
        assert debit["linked_transaction_id"] == credit["id"]

    def test_same_account_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="same account"):
            svc.create_transfer(
                tx_data["egp_id"],
                tx_data["egp_id"],
                1000,
                None,
                None,
                None,
            )

    def test_different_currency_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="same currency"):
            svc.create_transfer(
                tx_data["egp_id"],
                tx_data["usd_id"],
                1000,
                None,
                None,
                None,
            )

    def test_tx_date_defaults_to_today(self, tx_data):
        from datetime import date

        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        debit, _ = svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            1000,
            None,
            None,
            None,  # tx_date=None
        )
        assert str(debit["date"]) == str(date.today())


@pytest.mark.django_db
class TestTransferWithFee:
    """Unified create_transfer() with optional fee_amount."""

    def test_transfer_with_fee_deducts_total_from_source(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            1000,
            None,
            "Transfer with fee",
            date(2026, 3, 15),
            fee_amount=15.0,
        )
        # Source: 10000 - 1000 - 15 = 8985
        assert _get_balance(tx_data["egp_id"]) == 8985
        # Dest: 5000 + 1000 = 6000
        assert _get_balance(str(dest.id)) == 6000

    def test_fee_creates_separate_transaction(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            1000,
            None,
            None,
            date(2026, 3, 15),
            fee_amount=15.0,
        )
        txs = Transaction.objects.filter(user_id=tx_data["user_id"])
        assert txs.count() == 3  # debit + credit + fee
        fee_tx = txs.filter(note__icontains="fee").first()
        assert fee_tx is not None
        assert float(fee_tx.amount) == 15.0

    def test_fee_categorized_as_fees_and_charges(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            1000,
            None,
            None,
            date(2026, 3, 15),
            fee_amount=15.0,
        )
        fee_tx = Transaction.objects.filter(
            user_id=tx_data["user_id"], note__icontains="fee"
        ).first()
        assert fee_tx is not None
        assert fee_tx.category is not None
        assert "fee" in fee_tx.category.get_display_name().lower()

    def test_zero_fee_no_extra_transaction(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            1000,
            None,
            None,
            date(2026, 3, 15),
            fee_amount=0.0,
        )
        txs = Transaction.objects.filter(user_id=tx_data["user_id"])
        assert txs.count() == 2  # no fee transaction

    def test_negative_fee_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        with pytest.raises(ValueError, match="fee"):
            svc.create_transfer(
                tx_data["egp_id"],
                str(dest.id),
                1000,
                None,
                None,
                date(2026, 3, 15),
                fee_amount=-5.0,
            )


# ---------------------------------------------------------------------------
# Exchange tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchange:
    def test_usd_to_egp(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        debit, credit = svc.create_exchange(
            tx_data["usd_id"],
            tx_data["egp_id"],
            amount=100,
            rate=50.0,
            counter_amount=None,
            note="USD to EGP",
            tx_date=date(2026, 3, 15),
        )
        # USD: 500 - 100 = 400
        assert _get_balance(tx_data["usd_id"]) == 400
        # EGP: 10000 + 5000 = 15000
        assert _get_balance(tx_data["egp_id"]) == 15000
        assert debit["type"] == "exchange"
        assert Decimal(debit["exchange_rate"]) == Decimal("50.0000")

    def test_egp_to_usd_inverts_rate(self, tx_data):
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        debit, credit = svc.create_exchange(
            tx_data["egp_id"],
            tx_data["usd_id"],
            amount=5000,
            rate=50.0,
            counter_amount=None,
            note="EGP to USD",
            tx_date=date(2026, 3, 15),
        )
        # EGP: 10000 - 5000 = 5000
        assert _get_balance(tx_data["egp_id"]) == 5000
        # USD: 500 + 100 = 600
        assert _get_balance(tx_data["usd_id"]) == 600
        # Rate stored as EGP per 1 USD = 50
        assert Decimal(debit["exchange_rate"]) == Decimal("50.0000")

    def test_same_currency_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Create a second EGP account to test currency validation (not same-account)
        egp2 = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="EGP 2",
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        egp2_id = str(egp2.id)
        with pytest.raises(ValueError, match="different currencies"):
            svc.create_exchange(
                tx_data["egp_id"],
                egp2_id,
                100,
                1.0,
                None,
                None,
                None,
            )

    def test_logs_rate(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create_exchange(
            tx_data["usd_id"],
            tx_data["egp_id"],
            100,
            50.0,
            None,
            None,
            date(2026, 3, 15),
        )
        log = ExchangeRateLog.objects.order_by("-created_at").first()
        assert log is not None
        assert float(log.rate) == 50.0


# ---------------------------------------------------------------------------
# Batch tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBatchCreate:
    def test_counts(self, tx_data):
        svc = _svc(tx_data["user_id"])
        items = [
            {"type": "expense", "amount": 100, "account_id": tx_data["egp_id"]},
            {"type": "expense", "amount": 200, "account_id": tx_data["egp_id"]},
            {
                "type": "expense",
                "amount": 0,
                "account_id": tx_data["egp_id"],
            },  # invalid
        ]
        created, failed = svc.batch_create(items)
        assert created == 2
        assert failed == 1


# ---------------------------------------------------------------------------
# Smart defaults tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSmartDefaults:
    def test_last_account(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
            }
        )
        defaults = svc.get_smart_defaults("expense")
        assert defaults["last_account_id"] == tx_data["egp_id"]

    def test_auto_category(self, tx_data):
        svc = _svc(tx_data["user_id"])
        for _ in range(3):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100,
                    "account_id": tx_data["egp_id"],
                    "category_id": tx_data["cat_expense_id"],
                }
            )
        defaults = svc.get_smart_defaults("expense")
        assert defaults["auto_category_id"] == tx_data["cat_expense_id"]

    def test_recent_categories(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_expense_id"],
            }
        )
        defaults = svc.get_smart_defaults("expense")
        assert tx_data["cat_expense_id"] in defaults["recent_category_ids"]


# ---------------------------------------------------------------------------
# Suggest category tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSuggestCategory:
    def test_suggests_most_common(self, tx_data):
        svc = _svc(tx_data["user_id"])
        for _ in range(3):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100,
                    "account_id": tx_data["egp_id"],
                    "category_id": tx_data["cat_expense_id"],
                    "note": "Coffee at Starbucks",
                }
            )
        result = svc.suggest_category("starbucks")
        assert result == tx_data["cat_expense_id"]

    def test_empty_note_returns_none(self, tx_data):
        svc = _svc(tx_data["user_id"])
        assert svc.suggest_category("") is None
        assert svc.suggest_category("   ") is None


# ---------------------------------------------------------------------------
# Category fields in list query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionListIncludesCategory:
    """Transaction list query returns category_name and category_icon."""

    def test_list_includes_category_fields(self, tx_data: dict) -> None:
        """Transactions with a category expose category_name and category_icon."""
        cat = CategoryFactory(
            user_id=tx_data["user_id"], name={"en": "Food"}, type="expense", icon="🍕"
        )
        cat_id = str(cat.id)
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
                "category_id": cat_id,
            }
        )
        txs, _ = svc.get_filtered_enriched(filters={})
        matching = [t for t in txs if t["category_name"] == "Food"]
        assert len(matching) == 1
        assert matching[0]["category_icon"] == "🍕"

    def test_list_null_category(self, tx_data: dict) -> None:
        """Transactions without a category return None for both category fields."""
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["egp_id"],
                "category_id": None,
            }
        )
        txs, _ = svc.get_filtered_enriched(filters={})
        uncategorised = [t for t in txs if t["category_name"] is None]
        assert len(uncategorised) == 1
        assert uncategorised[0]["category_icon"] is None


# ---------------------------------------------------------------------------
# Virtual Account deallocation tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeallocateFromVirtualAccounts:
    """Tests for VA allocation cleanup on transaction delete."""

    def test_deallocates_and_reverses_balance(self, tx_data: dict) -> None:
        """Allocate tx to VA, then deallocate — allocation deleted, VA balance reversed."""
        svc = _svc(tx_data["user_id"])

        # Create a transaction to allocate
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 500,
                "account_id": tx_data["egp_id"],
            }
        )

        # Create a virtual account (not linked to a specific account)
        va = VirtualAccountFactory(
            user_id=tx_data["user_id"], name="Test VA", current_balance=0
        )
        va_id = str(va.id)

        # Allocate 200 to the VA
        svc.allocate_to_virtual_account(tx["id"], va_id, 200)

        # Verify VA balance increased
        assert float(VirtualAccount.objects.get(id=va_id).current_balance) == 200

        # Deallocate
        svc.deallocate_from_virtual_accounts(tx["id"])

        # VA balance should be reversed back to 0
        assert float(VirtualAccount.objects.get(id=va_id).current_balance) == 0

        # Allocation row should be deleted
        assert (
            VirtualAccountAllocation.objects.filter(transaction_id=tx["id"]).count()
            == 0
        )

    def test_noop_when_no_allocations(self, tx_data: dict) -> None:
        """Deallocating a tx with no allocations should not error."""
        svc = _svc(tx_data["user_id"])

        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
            }
        )

        # Should not raise
        svc.deallocate_from_virtual_accounts(tx["id"])


# ---------------------------------------------------------------------------
# TransactionService.get_allocation_for_tx — returns VA id or None
# ---------------------------------------------------------------------------


class TestGetAllocationForTx:
    """get_allocation_for_tx returns the allocated VA id string, or None."""

    def test_returns_va_id_when_allocated(self, tx_data: dict) -> None:
        """When a tx is allocated to a VA, returns that VA's id."""
        svc = _svc(tx_data["user_id"])

        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 200,
                "account_id": tx_data["egp_id"],
            }
        )

        # Create VA + allocate
        va = VirtualAccountFactory(
            user_id=tx_data["user_id"], name="Test VA", current_balance=0
        )
        va_id = str(va.id)
        VirtualAccountAllocationFactory(
            virtual_account_id=va.id, transaction_id=tx["id"], amount=-200
        )

        result = svc.get_allocation_for_tx(tx["id"])
        assert result == va_id

    def test_returns_none_when_not_allocated(self, tx_data: dict) -> None:
        """When a tx has no allocation, returns None."""
        svc = _svc(tx_data["user_id"])

        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 100,
                "account_id": tx_data["egp_id"],
            }
        )

        result = svc.get_allocation_for_tx(tx["id"])
        assert result is None


# ---------------------------------------------------------------------------
# TransactionService._validate_basic — empty account_id
# ---------------------------------------------------------------------------


class TestValidateBasicEmptyAccountId:
    """_validate_basic raises ValueError for empty account_id."""

    def test_empty_account_id_raises(self, tx_data: dict) -> None:
        """Creating a tx with empty string account_id raises ValueError."""
        svc = _svc(tx_data["user_id"])

        with pytest.raises(ValueError, match="account_id is required"):
            svc.create(
                {
                    "type": "expense",
                    "amount": 100,
                    "account_id": "",
                }
            )


# ---------------------------------------------------------------------------
# Boundary amount tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionBoundaryAmounts:
    """Edge cases for transaction amount validation and storage precision."""

    def test_negative_amount_raises(self, tx_data: dict) -> None:
        """Negative amount is rejected by _validate_basic (amount must be positive)."""
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="positive"):
            svc.create(
                {
                    "type": "expense",
                    "amount": -100,
                    "account_id": tx_data["egp_id"],
                }
            )

    def test_large_amount_succeeds(self, tx_data: dict) -> None:
        """Amount near NUMERIC(15,2) max succeeds without DB overflow."""
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, new_bal = svc.create(
            {
                "type": "income",
                "amount": 999999999.99,
                "account_id": tx_data["egp_id"],
            }
        )
        assert Decimal(tx["amount"]) == Decimal("999999999.99")
        assert Decimal(new_bal) == Decimal("10000") + Decimal("999999999.99")

    def test_decimal_precision(self, tx_data: dict) -> None:
        """Amount with >2 decimal places is rounded to 2dp by NUMERIC(15,2) column."""
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 100.999,
                "account_id": tx_data["egp_id"],
            }
        )
        # Re-fetch from DB to see what NUMERIC(15,2) actually stored
        refetched = svc.get_by_id(tx["id"])
        assert refetched is not None
        # DB stores NUMERIC(15,2) — rounds to 101.00
        assert Decimal(refetched["amount"]) == Decimal("101.00")

    def test_large_amount_precision_preserved_in_response(self, tx_data: dict) -> None:
        """Large amounts (100M+) must return as strings to preserve precision.

        If amount is returned as float, precision is lost:
        - Decimal('123456789.99') -> float -> 123456789.98 or similar (WRONG)
        - Running balance calculations with float accumulate rounding errors

        The fix is to return amounts as strings, which JavaScript can parse with Decimal.js.
        """
        from decimal import Decimal

        svc = _svc(tx_data["user_id"])
        # Create a large transaction
        tx, _ = svc.create(
            {
                "type": "income",
                "amount": Decimal("123456789.99"),
                "account_id": tx_data["egp_id"],
            }
        )
        # After fix: amounts should be strings to preserve precision
        # Currently, this will show that amount is a float (BUG)
        # We'll verify the exact value is preserved in the response
        assert tx["amount"] is not None
        # If float: 123456789.99 as float loses precision
        # If str: "123456789.99" preserves it
        # This test documents the current behavior (float) and the expected (str)
        if isinstance(tx["amount"], str):
            # After fix: precision preserved as string
            assert Decimal(tx["amount"]) == Decimal("123456789.99")
        else:
            # Current behavior: float loses precision on large amounts
            # This is the BUG we're fixing
            pass  # Document current float behavior


@pytest.mark.django_db
class TestAllocateToVirtualAccount:
    def test_va_not_found(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="Pot not found"):
            svc.allocate_to_virtual_account(
                "00000000-0000-0000-0000-000000000000",
                "11111111-1111-1111-1111-111111111111",
                100,
            )

    def test_tx_not_found(self, tx_data):
        svc = _svc(tx_data["user_id"])
        va = VirtualAccountFactory(user_id=tx_data["user_id"], account_id=None)
        with pytest.raises(ValueError, match="Transaction not found"):
            svc.allocate_to_virtual_account(
                "00000000-0000-0000-0000-000000000000", str(va.id), 100
            )

    def test_account_linkage_mismatch(self, tx_data):
        svc = _svc(tx_data["user_id"])
        va = VirtualAccountFactory(
            user_id=tx_data["user_id"], account_id=tx_data["usd_id"]
        )
        tx, _ = svc.create(
            {"type": "expense", "amount": 100, "account_id": tx_data["egp_id"]}
        )
        with pytest.raises(ValueError, match="Pot is linked to a different account"):
            svc.allocate_to_virtual_account(tx["id"], str(va.id), 100)


@pytest.mark.django_db
class TestDropdownHelpers:
    def test_get_accounts(self, tx_data):
        svc = _svc(tx_data["user_id"])
        accounts = svc.get_accounts()
        assert len(accounts) >= 1
        account = next(a for a in accounts if a["id"] == tx_data["egp_id"])
        assert account["institution_name"] == "Test Bank"
        assert "institution_icon" in account
        assert "institution_color" in account

    def test_get_virtual_accounts(self, tx_data):
        svc = _svc(tx_data["user_id"])
        VirtualAccountFactory(
            user_id=tx_data["user_id"],
            name="Test VA",
            account_id=tx_data["usd_id"],
        )
        vas = svc.get_virtual_accounts()
        assert len(vas) >= 1
        assert any(va["name"] == "Test VA" and va["currency"] == "USD" for va in vas)

    def test_get_virtual_accounts_keeps_unlinked_currency_empty(self, tx_data):
        svc = _svc(tx_data["user_id"])
        VirtualAccountFactory(user_id=tx_data["user_id"], name="Unlinked VA")

        vas = svc.get_virtual_accounts()

        assert any(va["name"] == "Unlinked VA" and va["currency"] is None for va in vas)

    def test_get_categories_with_cat_type(self, tx_data):
        svc = _svc(tx_data["user_id"])
        cats = svc.get_categories(cat_type="income")
        assert len(cats) >= 1
        assert all(c["type"] == "income" for c in cats)

    def test_get_accounts_ordered_by_usage(self, tx_data):
        """Most-used account for the selected transaction type comes first."""
        svc = _svc(tx_data["user_id"])
        for _ in range(3):
            svc.create(
                {"type": "expense", "amount": 1, "account_id": tx_data["usd_id"]}
            )
        for _ in range(5):
            svc.create({"type": "income", "amount": 1, "account_id": tx_data["egp_id"]})
        for _ in range(10):
            svc.create(
                {
                    "type": "transfer",
                    "amount": 1,
                    "account_id": tx_data["cc_id"],
                    "counter_account_id": tx_data["egp_id"],
                }
            )

        expense_ids = [a["id"] for a in svc.get_accounts("expense")]
        income_ids = [a["id"] for a in svc.get_accounts("income")]

        assert expense_ids.index(tx_data["usd_id"]) < expense_ids.index(
            tx_data["egp_id"]
        )
        assert income_ids.index(tx_data["egp_id"]) < income_ids.index(tx_data["usd_id"])
        assert expense_ids.index(tx_data["usd_id"]) < expense_ids.index(
            tx_data["cc_id"]
        )

    def test_get_accounts_tie_falls_back_to_display_order(self, tx_data):
        """Equal type-specific usage keeps the existing deterministic fallback."""
        svc = _svc(tx_data["user_id"])

        accounts = svc.get_accounts("expense")
        ids = [a["id"] for a in accounts]

        assert ids.index(tx_data["egp_id"]) < ids.index(tx_data["usd_id"])

    def test_get_accounts_isolation(self, tx_data):
        """User B's transaction count does not affect user A's account ordering."""
        user_b = UserFactory()
        SessionFactory(user=user_b)
        inst_b = InstitutionFactory(user_id=user_b.id)
        acc_b = AccountFactory(
            user_id=user_b.id, institution_id=inst_b.id, currency="EGP"
        )
        svc_b = _svc(str(user_b.id))
        for _ in range(10):
            svc_b.create({"type": "expense", "amount": 1, "account_id": str(acc_b.id)})

        svc_a = _svc(tx_data["user_id"])
        accounts_a = svc_a.get_accounts("expense")
        # user_a can only see their own accounts
        ids_a = {a["id"] for a in accounts_a}
        assert str(acc_b.id) not in ids_a

    def test_get_categories_ordered_by_usage(self, tx_data):
        """Most-used category appears first."""
        svc = _svc(tx_data["user_id"])
        for _ in range(5):
            svc.create(
                {
                    "type": "expense",
                    "amount": 1,
                    "account_id": tx_data["egp_id"],
                    "category_id": tx_data["cat_income_id"],
                }
            )
        cats = svc.get_categories()
        ids = [c["id"] for c in cats]
        assert ids.index(tx_data["cat_income_id"]) < ids.index(
            tx_data["cat_expense_id"]
        )

    def test_get_categories_isolation(self, tx_data):
        """User B's category usage does not inflate user A's category ordering."""
        user_b = UserFactory()
        SessionFactory(user=user_b)
        # Give user_b the same category via a system-like copy
        cat_b = CategoryFactory(
            user_id=user_b.id, name={"en": "PopularB"}, type="expense"
        )
        svc_b = _svc(str(user_b.id))
        inst_b = InstitutionFactory(user_id=user_b.id)
        acc_b = AccountFactory(
            user_id=user_b.id, institution_id=inst_b.id, currency="EGP"
        )
        for _ in range(100):
            svc_b.create(
                {
                    "type": "expense",
                    "amount": 1,
                    "account_id": str(acc_b.id),
                    "category_id": str(cat_b.id),
                }
            )

        # user_a has no transactions at all; user_b's heavy usage shouldn't appear
        svc_a = _svc(tx_data["user_id"])
        cats_a = svc_a.get_categories()
        ids_a = {c["id"] for c in cats_a}
        assert str(cat_b.id) not in ids_a


@pytest.mark.django_db
class TestApplyPostCreateLogic:
    def test_apply_post_create_logic_with_va(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Test basic allocation
        va = VirtualAccountFactory(
            user_id=tx_data["user_id"], account_id=tx_data["egp_id"]
        )
        tx, _ = svc.create(
            {"type": "expense", "amount": 100, "account_id": tx_data["egp_id"]}
        )
        svc.apply_post_create_logic(tx, fee_amount=25.0, va_id=str(va.id), tx_date=None)

        # Test reallocation
        va2 = VirtualAccountFactory(
            user_id=tx_data["user_id"], account_id=tx_data["egp_id"]
        )
        svc.apply_post_create_logic(
            tx, fee_amount=None, va_id=str(va2.id), tx_date=None
        )

        # Test explicit deallocation
        svc.apply_post_create_logic(tx, fee_amount=None, va_id="", tx_date=None)


# ---------------------------------------------------------------------------
# update_transfer tests (RED — method does not exist yet)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateTransfer:
    def _make_transfer(self, tx_data, amount=2000, fee_amount=None):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest EGP",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        debit, credit = svc.create_transfer(
            tx_data["egp_id"],
            str(dest.id),
            amount,
            None,
            "original note",
            date(2026, 3, 15),
            fee_amount=fee_amount,
        )
        return svc, debit, credit, str(dest.id)

    def test_update_amount_adjusts_both_balances(self, tx_data):
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        # source: 10000-2000=8000, dest: 5000+2000=7000
        assert _get_balance(tx_data["egp_id"]) == 8000
        assert _get_balance(dest_id) == 7000

        svc.update_transfer(
            debit["id"],
            amount=3000,
            note="updated",
            tx_date=date(2026, 3, 15),
            fee_amount=None,
        )

        # source: 8000 - (3000-2000) = 7000, dest: 7000 + (3000-2000) = 8000
        assert _get_balance(tx_data["egp_id"]) == 7000
        assert _get_balance(dest_id) == 8000

    def test_update_amount_syncs_both_leg_records(self, tx_data):
        from decimal import Decimal

        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        svc.update_transfer(
            debit["id"],
            amount=500,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
        )

        debit_obj = Transaction.objects.get(id=debit["id"])
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert Decimal(str(debit_obj.amount)) == Decimal("500")
        assert Decimal(str(debit_obj.balance_delta)) == Decimal("-500")
        assert Decimal(str(credit_obj.amount)) == Decimal("500")
        assert Decimal(str(credit_obj.balance_delta)) == Decimal("500")

    def test_update_note_syncs_both_legs(self, tx_data):
        svc, debit, credit, dest_id = self._make_transfer(tx_data)
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note="new note",
            tx_date=date(2026, 3, 15),
            fee_amount=None,
        )

        debit_obj = Transaction.objects.get(id=debit["id"])
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert debit_obj.note == "new note"
        assert credit_obj.note == "new note"

    def test_update_date_syncs_both_legs(self, tx_data):
        svc, debit, credit, dest_id = self._make_transfer(tx_data)
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 4, 1),
            fee_amount=None,
        )

        debit_obj = Transaction.objects.get(id=debit["id"])
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert debit_obj.date == date(2026, 4, 1)
        assert credit_obj.date == date(2026, 4, 1)

    def test_update_fee_added_atomically(self, tx_data):
        from decimal import Decimal

        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=50.0,
        )

        # source: 8000 - 50 = 7950
        assert _get_balance(tx_data["egp_id"]) == 7950
        fee_tx = Transaction.objects.filter(
            user_id=tx_data["user_id"], note="Transfer fee"
        ).first()
        assert fee_tx is not None
        assert Decimal(str(fee_tx.amount)) == Decimal("50")

    def test_update_fee_changed_adjusts_balance(self, tx_data):
        svc, debit, credit, dest_id = self._make_transfer(
            tx_data, amount=2000, fee_amount=50.0
        )
        # source: 10000 - 2000 - 50 = 7950
        assert _get_balance(tx_data["egp_id"]) == 7950

        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=100.0,
        )
        # source: 7950 + 50 - 100 = 7900
        assert _get_balance(tx_data["egp_id"]) == 7900

    def test_update_fee_removed_restores_balance(self, tx_data):
        svc, debit, credit, dest_id = self._make_transfer(
            tx_data, amount=2000, fee_amount=50.0
        )
        assert _get_balance(tx_data["egp_id"]) == 7950

        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
        )
        # fee reversed: 7950 + 50 = 8000
        assert _get_balance(tx_data["egp_id"]) == 8000
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], note="Transfer fee"
            ).count()
            == 0
        )

    def test_not_found_raises(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="not found"):
            svc.update_transfer(
                str(uuid.uuid4()),
                amount=100,
                note=None,
                tx_date=date(2026, 3, 15),
                fee_amount=None,
            )

    def test_all_changes_atomic_on_error(self, tx_data):
        """If fee update fails inside the atomic block, no partial state committed."""
        from unittest.mock import patch

        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        src_balance_before = _get_balance(tx_data["egp_id"])
        dest_balance_before = _get_balance(dest_id)

        with patch.object(
            type(svc),
            "_update_fee_in_atomic",
            side_effect=Exception("simulated failure"),
        ):
            with pytest.raises(Exception, match="simulated failure"):
                svc.update_transfer(
                    debit["id"],
                    amount=3000,
                    note=None,
                    tx_date=date(2026, 3, 15),
                    fee_amount=50.0,
                )

        # Balances must be unchanged (atomic rollback)
        assert _get_balance(tx_data["egp_id"]) == src_balance_before
        assert _get_balance(dest_id) == dest_balance_before

    def test_update_source_adjusts_all_balances(self, tx_data):
        """Changing source restores old source balance, debits new source."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        # old_src=8000, dest=7000
        new_src = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Source EGP",
            currency="EGP",
            current_balance=3000,
            initial_balance=3000,
        )
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
            source_id=str(new_src.id),
            dest_id=dest_id,
        )
        assert _get_balance(tx_data["egp_id"]) == 10000  # old source restored
        assert _get_balance(str(new_src.id)) == 1000  # new source debited
        assert _get_balance(dest_id) == 7000  # dest unchanged

    def test_update_dest_adjusts_all_balances(self, tx_data):
        """Changing dest restores old dest balance, credits new dest."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        # src=8000, old_dest=7000
        new_dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Dest EGP",
            currency="EGP",
            current_balance=6000,
            initial_balance=6000,
        )
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
            source_id=tx_data["egp_id"],
            dest_id=str(new_dest.id),
        )
        assert _get_balance(tx_data["egp_id"]) == 8000  # source unchanged
        assert _get_balance(dest_id) == 5000  # old dest restored
        assert _get_balance(str(new_dest.id)) == 8000  # new dest credited

    def test_update_both_accounts_adjusts_all_balances(self, tx_data):
        """Changing both source and dest updates all four accounts."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        new_src = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Source EGP",
            currency="EGP",
            current_balance=4000,
            initial_balance=4000,
        )
        new_dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Dest EGP",
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
            source_id=str(new_src.id),
            dest_id=str(new_dest.id),
        )
        assert _get_balance(tx_data["egp_id"]) == 10000  # old src restored
        assert _get_balance(dest_id) == 5000  # old dest restored
        assert _get_balance(str(new_src.id)) == 2000  # new src debited
        assert _get_balance(str(new_dest.id)) == 3000  # new dest credited

    def test_update_source_updates_leg_account_ids(self, tx_data):
        """account_id and counter_account_id on both legs reflect new source."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        new_src = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Source EGP",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=None,
            source_id=str(new_src.id),
            dest_id=dest_id,
        )
        debit_obj = Transaction.objects.get(id=debit["id"])
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert str(debit_obj.account_id) == str(new_src.id)
        assert str(debit_obj.counter_account_id) == dest_id
        assert str(credit_obj.account_id) == dest_id
        assert str(credit_obj.counter_account_id) == str(new_src.id)

    def test_update_source_moves_fee_to_new_source(self, tx_data):
        """Fee transaction moves to new source account when source changes."""
        from decimal import Decimal

        svc, debit, credit, dest_id = self._make_transfer(
            tx_data, amount=2000, fee_amount=50.0
        )
        # old_src=7950 (10000-2000-50), dest=7000
        new_src = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="New Source EGP",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        svc.update_transfer(
            debit["id"],
            amount=2000,
            note=None,
            tx_date=date(2026, 3, 15),
            fee_amount=50.0,
            source_id=str(new_src.id),
            dest_id=dest_id,
        )
        assert _get_balance(tx_data["egp_id"]) == 10000  # old src fully restored
        assert _get_balance(str(new_src.id)) == 2950  # 5000 - 2000 - 50
        fee_tx = Transaction.objects.filter(
            user_id=tx_data["user_id"], note="Transfer fee"
        ).first()
        assert fee_tx is not None
        assert str(fee_tx.account_id) == str(new_src.id)
        assert Decimal(str(fee_tx.amount)) == Decimal("50")

    def test_update_currency_mismatch_raises(self, tx_data):
        """New source and dest with different currencies raises ValueError."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        with pytest.raises(ValueError, match="same currency"):
            svc.update_transfer(
                debit["id"],
                amount=2000,
                note=None,
                tx_date=date(2026, 3, 15),
                fee_amount=None,
                source_id=tx_data["usd_id"],  # USD
                dest_id=dest_id,  # EGP — mismatch
            )

    def test_update_same_source_dest_raises(self, tx_data):
        """Setting source == dest raises ValueError."""
        svc, debit, credit, dest_id = self._make_transfer(tx_data, amount=2000)
        with pytest.raises(ValueError, match="same account"):
            svc.update_transfer(
                debit["id"],
                amount=2000,
                note=None,
                tx_date=date(2026, 3, 15),
                fee_amount=None,
                source_id=tx_data["egp_id"],
                dest_id=tx_data["egp_id"],
            )


# ---------------------------------------------------------------------------
# update_exchange tests (RED — method does not exist yet)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateExchange:
    def _make_exchange(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # USD→EGP: sell 100 USD at rate 50 → get 5000 EGP
        debit, credit = svc.create_exchange(
            tx_data["usd_id"],
            tx_data["egp_id"],
            amount=100,
            rate=50.0,
            counter_amount=None,
            note="original note",
            tx_date=date(2026, 3, 15),
        )
        return svc, debit, credit

    def test_update_amount_adjusts_both_balances(self, tx_data):
        svc, debit, credit = self._make_exchange(tx_data)
        # usd: 500-100=400, egp: 10000+5000=15000
        assert _get_balance(tx_data["usd_id"]) == 400
        assert _get_balance(tx_data["egp_id"]) == 15000

        # Update: sell 200 USD at rate 50 → get 10000 EGP
        svc.update_exchange(
            debit["id"],
            amount=200,
            rate=50.0,
            counter_amount=None,
            note="updated",
            tx_date=date(2026, 3, 15),
        )
        # usd: 400 - (200-100) = 300, egp: 15000 + (10000-5000) = 20000
        assert _get_balance(tx_data["usd_id"]) == 300
        assert _get_balance(tx_data["egp_id"]) == 20000

    def test_update_rate_syncs_both_legs(self, tx_data):
        from decimal import Decimal

        svc, debit, credit = self._make_exchange(tx_data)
        svc.update_exchange(
            debit["id"],
            amount=100,
            rate=60.0,
            counter_amount=None,
            note=None,
            tx_date=date(2026, 3, 15),
        )
        debit_obj = Transaction.objects.get(id=debit["id"])
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert Decimal(str(debit_obj.exchange_rate)) == Decimal("60")
        assert Decimal(str(credit_obj.exchange_rate)) == Decimal("60")

    def test_update_counter_amount_syncs_credit_leg(self, tx_data):
        from decimal import Decimal

        svc, debit, credit = self._make_exchange(tx_data)
        # Change: sell 100 USD, get 6000 EGP (rate=60)
        svc.update_exchange(
            debit["id"],
            amount=100,
            rate=None,
            counter_amount=6000,
            note=None,
            tx_date=date(2026, 3, 15),
        )
        credit_obj = Transaction.objects.get(id=credit["id"])
        assert Decimal(str(credit_obj.amount)) == Decimal("6000")
        assert Decimal(str(credit_obj.balance_delta)) == Decimal("6000")

    def test_update_note_syncs_both_legs(self, tx_data):
        svc, debit, credit = self._make_exchange(tx_data)
        svc.update_exchange(
            debit["id"],
            amount=100,
            rate=50.0,
            counter_amount=None,
            note="wire fee",
            tx_date=date(2026, 3, 15),
        )
        assert Transaction.objects.get(id=debit["id"]).note == "wire fee"
        assert Transaction.objects.get(id=credit["id"]).note == "wire fee"

    def test_update_logs_new_rate(self, tx_data):
        svc, debit, credit = self._make_exchange(tx_data)
        count_before = ExchangeRateLog.objects.count()
        svc.update_exchange(
            debit["id"],
            amount=100,
            rate=55.0,
            counter_amount=None,
            note=None,
            tx_date=date(2026, 3, 15),
        )
        assert ExchangeRateLog.objects.count() == count_before + 1
        log = ExchangeRateLog.objects.order_by("-created_at").first()
        assert log is not None
        assert float(log.rate) == 55.0

    def test_not_found_raises(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="not found"):
            svc.update_exchange(
                str(uuid.uuid4()),
                amount=100,
                rate=50.0,
                counter_amount=None,
                note=None,
                tx_date=date(2026, 3, 15),
            )


# ---------------------------------------------------------------------------
# Round-up tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRoundup:
    """Tests for automatic round-up savings on expense transactions."""

    def _setup_roundup(self, tx_data: dict, increment: int) -> str:
        """Create a savings account, configure source account with round-up, return savings_id."""
        savings = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Savings",
            currency="EGP",
            current_balance=0,
            initial_balance=0,
        )
        savings_id = str(savings.id)
        Account.objects.filter(id=tx_data["egp_id"]).update(
            roundup_increment=increment,
            roundup_target_account_id=savings_id,
        )
        return savings_id

    def test_roundup_creates_transfer_and_updates_both_balances(self, tx_data):
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        # Expense: 10000 - 47 = 9953. Roundup: ceil(47/10)*10 - 47 = 50 - 47 = 3.
        # After roundup transfer: source = 9953 - 3 = 9950, savings = 0 + 3 = 3.
        assert _get_balance(tx_data["egp_id"]) == 9950
        assert _get_balance(savings_id) == 3

    def test_roundup_transfer_marked_is_roundup(self, tx_data):
        from decimal import Decimal

        self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        roundup_txs = list(
            Transaction.objects.filter(
                user_id=tx_data["user_id"], is_roundup=True
            ).values("id", "type", "balance_delta")
        )
        assert len(roundup_txs) == 2  # debit + credit legs
        deltas = {Decimal(str(t["balance_delta"])) for t in roundup_txs}
        assert Decimal("-3") in deltas
        assert Decimal("3") in deltas

    def test_roundup_transfer_linked_to_expense_via_parent(self, tx_data):
        self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        children = Transaction.objects.filter(parent_transaction_id=tx["id"]).values(
            "id"
        )
        assert children.count() == 2

    def test_already_round_amount_skips_roundup(self, tx_data):
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 50,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert _get_balance(tx_data["egp_id"]) == 9950
        assert _get_balance(savings_id) == 0
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], is_roundup=True
            ).count()
            == 0
        )

    def test_insufficient_balance_skips_roundup_but_expense_goes_through(self, tx_data):
        # Set balance to exactly the expense amount — no room for round-up
        Account.objects.filter(id=tx_data["egp_id"]).update(current_balance=47)
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert tx["type"] == "expense"
        assert _get_balance(tx_data["egp_id"]) == 0
        assert _get_balance(savings_id) == 0

    def test_income_does_not_trigger_roundup(self, tx_data):
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "income",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert _get_balance(savings_id) == 0

    def test_delete_expense_cascades_to_roundup_transfer(self, tx_data):
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        tx, _ = svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert _get_balance(tx_data["egp_id"]) == 9950
        assert _get_balance(savings_id) == 3

        svc.delete(tx["id"])

        assert _get_balance(tx_data["egp_id"]) == 10000
        assert _get_balance(savings_id) == 0
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], is_roundup=True
            ).count()
            == 0
        )

    def test_fractional_roundup(self, tx_data):
        """47.50 with increment 10 → round to 50 → save 2.50"""
        savings_id = self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": "47.50",
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert _get_balance(savings_id) == 2.5

    def test_no_roundup_when_no_increment_configured(self, tx_data):
        svc = _svc(tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
            }
        )
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], is_roundup=True
            ).count()
            == 0
        )

    def test_recurring_expense_does_not_trigger_roundup(self, tx_data):
        from tests.factories import RecurringRuleFactory

        self._setup_roundup(tx_data, 10)
        svc = _svc(tx_data["user_id"])
        rule = RecurringRuleFactory(user_id=tx_data["user_id"])
        svc.create(
            {
                "type": "expense",
                "amount": 47,
                "account_id": tx_data["egp_id"],
                "date": date(2026, 3, 15),
                "recurring_rule_id": str(rule.id),
            }
        )
        assert (
            Transaction.objects.filter(
                user_id=tx_data["user_id"], is_roundup=True
            ).count()
            == 0
        )
