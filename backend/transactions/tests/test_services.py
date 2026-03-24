"""
Transaction service tests — tests for TransactionService CRUD, transfer, exchange,
Fawry, batch, smart defaults, and suggest category.

Uses raw SQL fixtures for test data setup. Tests run against
the real database with --reuse-db.
"""

import uuid
from datetime import date
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from transactions.services import (
    TransactionService,
    calculate_instapay_fee,
    resolve_exchange_fields,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def tx_data(db):
    """User + institution + 2 accounts (savings EGP, savings USD) + 1 CC.

    Creates minimal test data for transaction service tests.
    """
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    usd_id = str(uuid.uuid4())
    cc_id = str(uuid.uuid4())
    cat_expense_id = str(uuid.uuid4())
    cat_income_id = str(uuid.uuid4())
    fees_cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s, %s)",
            [egp_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'USD', %s, %s)",
            [usd_id, user_id, inst_id, "USD Savings", 500, 500],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance, credit_limit)"
            " VALUES (%s, %s, %s, %s, 'credit_card', 'EGP',"
            " %s, %s, %s)",
            [cc_id, user_id, inst_id, "Test CC", 0, 0, 5000],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type)"
            " VALUES (%s, %s, %s, 'expense')",
            [cat_expense_id, user_id, "Food"],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type)"
            " VALUES (%s, %s, %s, 'income')",
            [cat_income_id, user_id, "Salary"],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type)"
            " VALUES (%s, %s, %s, 'expense')",
            [fees_cat_id, user_id, "Fees & Charges"],
        )

    yield {
        "user_id": user_id,
        "egp_id": egp_id,
        "usd_id": usd_id,
        "cc_id": cc_id,
        "cat_expense_id": cat_expense_id,
        "cat_income_id": cat_income_id,
        "fees_cat_id": fees_cat_id,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM virtual_account_allocations WHERE transaction_id IN (SELECT id FROM transactions WHERE user_id = %s)",
            [user_id],
        )
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _svc(user_id: str) -> TransactionService:
    return TransactionService(user_id, TZ)


def _get_balance(account_id: str) -> float:
    """Fetch current_balance directly from DB."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_balance FROM accounts WHERE id = %s", [account_id]
        )
        row = cursor.fetchone()
    return float(row[0]) if row else 0


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
        dest_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [
                    dest_id,
                    tx_data["user_id"],
                    tx_data["user_id"],
                    "Dest Account",
                    5000,
                    5000,
                ],
            )
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
        dest_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [dest_id, tx_data["user_id"], tx_data["user_id"], "Dest", 5000, 5000],
            )
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
class TestInstapayTransfer:
    def test_deducts_fee_from_source(self, tx_data):
        svc = _svc(tx_data["user_id"])
        dest_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [dest_id, tx_data["user_id"], tx_data["user_id"], "Dest", 5000, 5000],
            )
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
        egp2_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [egp2_id, tx_data["user_id"], tx_data["user_id"], "EGP 2", 1000, 1000],
            )
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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rate FROM exchange_rate_log ORDER BY created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
        assert row is not None
        assert float(row[0]) == 50.0


# ---------------------------------------------------------------------------
# Fawry tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFawryCashout:
    def test_charges_cc_credits_prepaid(self, tx_data):
        svc = _svc(tx_data["user_id"])
        # Create prepaid account
        prepaid_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'prepaid', 'EGP', %s, %s)",
                [prepaid_id, tx_data["user_id"], tx_data["user_id"], "Prepaid", 0, 0],
            )
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
        cat_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Food', 'expense', '🍕')",
                [cat_id, tx_data["user_id"]],
            )
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
