"""
Transaction service tests — tests for TransactionService CRUD, transfer, exchange,
Fawry, batch, smart defaults, and suggest category.
"""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from conftest import SessionFactory, UserFactory
from core.models import (
    Account,
    ExchangeRateLog,
    VirtualAccount,
    VirtualAccountAllocation,
)
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    VirtualAccountAllocationFactory,
    VirtualAccountFactory,
)
from transactions.services import (
    TransactionService,
    calculate_instapay_fee,
    resolve_exchange_fields,
)

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
    cat_expense = CategoryFactory(user_id=user.id, name="Food", type="expense")
    cat_income = CategoryFactory(user_id=user.id, name="Salary", type="income")
    fees_cat = CategoryFactory(user_id=user.id, name="Fees & Charges", type="expense")
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


class TestInstapayFee:
    def test_normal(self):
        assert calculate_instapay_fee(1000) == 1.0

    def test_minimum(self):
        assert calculate_instapay_fee(100) == 0.5

    def test_maximum(self):
        assert calculate_instapay_fee(50000) == 20.0


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_expense_updates_balance(self, tx_data):
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
        assert tx["amount"] == 500
        assert tx["currency"] == "EGP"
        assert tx["balance_delta"] == -500
        assert new_bal == 9500
        assert _get_balance(tx_data["egp_id"]) == 9500

    def test_income_updates_balance(self, tx_data):
        svc = _svc(tx_data["user_id"])
        tx, new_bal = svc.create(
            {
                "type": "income",
                "amount": 2000,
                "account_id": tx_data["egp_id"],
                "category_id": tx_data["cat_income_id"],
            }
        )
        assert tx["balance_delta"] == 2000
        assert new_bal == 12000
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


@pytest.mark.django_db
class TestUpdate:
    def test_recalculates_balance_delta(self, tx_data):
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
        assert updated["amount"] == 300
        assert updated["balance_delta"] == -300
        assert _get_balance(tx_data["egp_id"]) == 9700

    def test_change_type_recalculates(self, tx_data):
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
        assert updated["balance_delta"] == 500
        assert _get_balance(tx_data["egp_id"]) == 10500


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
        svc.delete(tx["id"])
        assert _get_balance(tx_data["egp_id"]) == 10000

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

        svc.delete(debit["id"])
        assert _get_balance(tx_data["egp_id"]) == 10000
        assert _get_balance(dest_id) == 5000

    def test_not_found(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="not found"):
            svc.delete(str(uuid.uuid4()))


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
        assert results[0]["amount"] == 200

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
        from core.models import Transaction

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
        from core.models import Transaction

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
        assert "fee" in fee_tx.category.name.lower()

    def test_zero_fee_no_extra_transaction(self, tx_data):
        from core.models import Transaction

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


@pytest.mark.django_db
class TestInstapayTransfer:
    def test_deducts_fee_from_source(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        dest_id = str(dest.id)
        _, _, fee = svc.create_instapay_transfer(
            tx_data["egp_id"],
            dest_id,
            1000,
            None,
            "Test",
            date(2026, 3, 15),
            fees_category_id=tx_data["fees_cat_id"],
        )
        assert fee == 1.0
        # Source: 10000 - 1000 - 1 = 8999
        assert _get_balance(tx_data["egp_id"]) == 8999
        # Dest: 5000 + 1000 = 6000
        assert _get_balance(dest_id) == 6000


# ---------------------------------------------------------------------------
# Exchange tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchange:
    def test_usd_to_egp(self, tx_data):
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
        assert debit["exchange_rate"] == 50.0

    def test_egp_to_usd_inverts_rate(self, tx_data):
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
        assert debit["exchange_rate"] == 50.0

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
# Fawry tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFawryCashout:
    def test_charges_cc_credits_prepaid(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Create prepaid account
        prepaid = AccountFactory(
            user_id=tx_data["user_id"],
            institution_id=tx_data["inst_id"],
            name="Prepaid",
            type="prepaid",
            currency="EGP",
            current_balance=0,
            initial_balance=0,
        )
        prepaid_id = str(prepaid.id)
        charge, credit = svc.create_fawry_cashout(
            tx_data["cc_id"],
            prepaid_id,
            1000,
            25,
            None,
            None,
            date(2026, 3, 15),
            fees_category_id=tx_data["fees_cat_id"],
        )
        # CC: 0 - 1025 = -1025
        assert _get_balance(tx_data["cc_id"]) == -1025
        # Prepaid: 0 + 1000 = 1000
        assert _get_balance(prepaid_id) == 1000

    def test_negative_fee_rejected(self, tx_data):
        svc = _svc(tx_data["user_id"])
        with pytest.raises(ValueError, match="negative"):
            svc.create_fawry_cashout(
                tx_data["cc_id"],
                tx_data["egp_id"],
                1000,
                -10,
                None,
                None,
                None,
            )


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
            user_id=tx_data["user_id"], name="Food", type="expense", icon="🍕"
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
        svc = _svc(tx_data["user_id"])
        tx, new_bal = svc.create(
            {
                "type": "income",
                "amount": 999999999.99,
                "account_id": tx_data["egp_id"],
            }
        )
        assert tx["amount"] == 999999999.99
        assert new_bal == 10000 + 999999999.99

    def test_decimal_precision(self, tx_data: dict) -> None:
        """Amount with >2 decimal places is rounded to 2dp by NUMERIC(15,2) column."""
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
        assert refetched["amount"] == 101.0
