"""
Tests for accounts services — billing cycle math + AccountService + InstitutionService.

Billing tests are pure (no DB). AccountService/InstitutionService tests need PostgreSQL.
"""

import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from accounts.services import AccountService, InstitutionService
from conftest import SessionFactory, UserFactory
from core.billing import (
    compute_due_date,
    get_billing_cycle_info,
    get_credit_card_utilization,
    interest_free_remaining,
    parse_billing_cycle,
)
from core.models import User
from tests.factories import AccountFactory, InstitutionFactory, VirtualAccountFactory


class TestParseBillingCycle:
    def test_valid_metadata(self):
        result = parse_billing_cycle({"statement_day": 15, "due_day": 5})
        assert result == (15, 5)

    def test_empty_metadata(self):
        assert parse_billing_cycle({}) is None

    def test_none_metadata(self):
        assert parse_billing_cycle(None) is None

    def test_zero_values(self):
        assert parse_billing_cycle({"statement_day": 0, "due_day": 5}) is None

    def test_missing_keys(self):
        assert parse_billing_cycle({"statement_day": 15}) is None


class TestComputeDueDate:
    def test_before_statement_day(self):
        # Today is Mar 10, statement=15, due=5 → due Apr 5
        result = compute_due_date(15, 5, date(2026, 3, 10))
        assert result == date(2026, 4, 5)

    def test_after_statement_day(self):
        # Today is Mar 20, statement=15, due=5 → due May 5
        result = compute_due_date(15, 5, date(2026, 3, 20))
        assert result == date(2026, 5, 5)

    def test_due_day_after_statement_day(self):
        # statement=5, due=25 → due same month as period end
        result = compute_due_date(5, 25, date(2026, 3, 3))
        assert result == date(2026, 3, 25)


class TestGetBillingCycleInfo:
    def test_before_statement_day(self):
        info = get_billing_cycle_info(15, 5, date(2026, 3, 10))
        assert info.period_start == date(2026, 2, 16)
        assert info.period_end == date(2026, 3, 15)
        assert info.due_date == date(2026, 4, 5)
        assert info.days_until_due == 26
        assert info.is_due_soon is False

    def test_after_statement_day(self):
        info = get_billing_cycle_info(15, 5, date(2026, 3, 20))
        assert info.period_start == date(2026, 3, 16)
        assert info.period_end == date(2026, 4, 15)
        assert info.due_date == date(2026, 5, 5)
        assert info.days_until_due == 46

    def test_due_soon(self):
        # Mar 10: before statement day 15 → period Feb 16 - Mar 15, due Apr 5
        # days_until_due = (Apr 5 - Mar 10).days = 26 → NOT due soon
        # Use Apr 1: before statement day 15 → period Mar 16 - Apr 15, due May 5
        # days_until_due = (May 5 - Apr 1).days = 34 → NOT due soon
        # Use May 1: before statement day 15 → period Apr 16 - May 15, due Jun 5
        # days_until_due = (Jun 5 - May 1).days = 35 → NOT due soon
        # Need to find a date where due_date - today <= 7
        # Use May 2 with statement_day=5, due_day=8:
        # May 2 before statement 5 → period Apr 6 - May 5, due May 8
        # days_until_due = (May 8 - May 2).days = 6 → IS due soon!
        info = get_billing_cycle_info(5, 8, date(2026, 5, 2))
        assert info.due_date == date(2026, 5, 8)
        assert info.days_until_due == 6
        assert info.is_due_soon is True


class TestGetCreditCardUtilization:
    def test_zero_balance(self):
        assert get_credit_card_utilization(0.0, 500000.0) == 0.0

    def test_positive_balance(self):
        # balance is positive means no debt
        assert get_credit_card_utilization(1000.0, 500000.0) == 0.0

    def test_normal_usage(self):
        # balance = -120000, limit = 500000 → 24%
        result = get_credit_card_utilization(-120000.0, 500000.0)
        assert result == pytest.approx(24.0)

    def test_no_limit(self):
        assert get_credit_card_utilization(-120000.0, None) == 0.0

    def test_zero_limit(self):
        assert get_credit_card_utilization(-120000.0, 0.0) == 0.0


class TestInterestFreeRemaining:
    def test_remaining_days(self):
        remaining, urgent = interest_free_remaining(
            date(2026, 3, 15), date(2026, 3, 20)
        )
        assert remaining == 50  # 55 - 5
        assert urgent is False

    def test_expired(self):
        remaining, urgent = interest_free_remaining(date(2026, 1, 1), date(2026, 3, 20))
        assert remaining == 0
        assert urgent is False

    def test_urgent(self):
        # period_end=Mar 15, +55 days = May 9. today=May 4. remaining=5
        remaining, urgent = interest_free_remaining(date(2026, 3, 15), date(2026, 5, 4))
        assert remaining == 5
        assert urgent is True


# ---------------------------------------------------------------------------
# AccountService.get_for_dropdown — needs real DB
# ---------------------------------------------------------------------------


@pytest.fixture
def dropdown_data(db):
    """User with institution + 2 active accounts + 1 dormant account."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    active_id = str(uuid.uuid4())
    dormant_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', 5000, 5000)",
            [active_id, user_id, inst_id, "Active Savings"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance, initial_balance, is_dormant)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', 0, 0, true)",
            [dormant_id, user_id, inst_id, "Dormant"],
        )

    yield {"user_id": user_id, "active_id": active_id, "dormant_id": dormant_id}

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    from core.models import Session, User

    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


class TestGetForDropdown:
    """AccountService.get_for_dropdown returns lightweight account dicts."""

    tz = ZoneInfo("Africa/Cairo")

    def test_excludes_dormant(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown()
        ids = [a["id"] for a in accounts]
        assert dropdown_data["active_id"] in ids
        assert dropdown_data["dormant_id"] not in ids

    def test_without_balance(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown()
        assert len(accounts) >= 1
        acc = accounts[0]
        assert "id" in acc
        assert "name" in acc
        assert "currency" in acc
        assert "current_balance" not in acc

    def test_with_balance(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown(include_balance=True)
        acc = accounts[0]
        assert "current_balance" in acc
        assert isinstance(acc["current_balance"], float)


# ---------------------------------------------------------------------------
# InstitutionService.create() — branding (icon + color)
# ---------------------------------------------------------------------------


class TestInstitutionCreateWithBranding:
    """InstitutionService.create() accepts icon and color from presets."""

    tz = ZoneInfo("Africa/Cairo")

    def test_create_bank_with_image_icon(self, db: None) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create(
            "CIB - Commercial International Bank",
            "bank",
            icon="cib.svg",
            color="#003DA5",
        )
        assert inst["icon"] == "cib.svg"
        assert inst["color"] == "#003DA5"

    def test_create_wallet_with_emoji_icon(self, db: None) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("Pocket Wallet", "wallet", icon="👛", color="#8B5E3C")
        assert inst["icon"] == "👛"
        assert inst["color"] == "#8B5E3C"

    def test_create_without_icon_and_color_defaults_none(self, db: None) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("Custom Wallet", "wallet")
        assert inst["icon"] is None
        assert inst["color"] is None

    def test_create_custom_bank_no_preset(self, db: None) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("My Local Bank", "bank")
        assert inst["name"] == "My Local Bank"
        assert inst["icon"] is None


# ---------------------------------------------------------------------------
# AccountService.create — auto-generated name when blank
# ---------------------------------------------------------------------------


class TestAccountCreateAutoName:
    """AccountService.create() generates default name when blank."""

    tz = ZoneInfo("Africa/Cairo")

    @pytest.fixture
    def setup(self, db: None) -> dict[str, str]:
        """User + institution for auto-name tests."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id, name="CIB", type="bank")
        return {"user_id": str(user.id), "institution_id": str(inst.id)}

    def test_auto_name_savings(self, setup: dict[str, str]) -> None:
        svc = AccountService(setup["user_id"], self.tz)
        account = svc.create(
            {
                "institution_id": setup["institution_id"],
                "name": "",
                "type": "savings",
                "currency": "EGP",
            }
        )
        assert account["name"] == "CIB - Savings"

    def test_auto_name_credit_card(self, setup: dict[str, str]) -> None:
        svc = AccountService(setup["user_id"], self.tz)
        account = svc.create(
            {
                "institution_id": setup["institution_id"],
                "name": "  ",
                "type": "credit_card",
                "currency": "EGP",
                "credit_limit": 50000,
            }
        )
        assert account["name"] == "CIB - Credit Card"

    def test_explicit_name_preserved(self, setup: dict[str, str]) -> None:
        svc = AccountService(setup["user_id"], self.tz)
        account = svc.create(
            {
                "institution_id": setup["institution_id"],
                "name": "My Main Account",
                "type": "current",
                "currency": "EGP",
            }
        )
        assert account["name"] == "My Main Account"

    def test_auto_name_prepaid(self, setup: dict[str, str]) -> None:
        svc = AccountService(setup["user_id"], self.tz)
        account = svc.create(
            {
                "institution_id": setup["institution_id"],
                "name": "",
                "type": "prepaid",
                "currency": "EGP",
            }
        )
        assert account["name"] == "CIB - Prepaid"

    def test_auto_name_cash(self, setup: dict[str, str]) -> None:
        svc = AccountService(setup["user_id"], self.tz)
        account = svc.create(
            {
                "institution_id": setup["institution_id"],
                "name": "",
                "type": "cash",
                "currency": "EGP",
            }
        )
        assert account["name"] == "CIB - Cash"


# ---------------------------------------------------------------------------
# AccountService.get_recent_transactions — window function + field mapping
# ---------------------------------------------------------------------------


@pytest.fixture
def recent_tx_data(db):
    """User + institution + 2 accounts + category for get_recent_transactions tests."""
    user = UserFactory()
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    other_account_id = str(uuid.uuid4())
    cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, 'My Savings', 'savings', 'EGP', 10000)",
            [account_id, user_id, inst_id],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, 'Other Account', 'savings', 'EGP', 5000)",
            [other_account_id, user_id, inst_id],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type) VALUES (%s, %s, 'Food', 'expense')",
            [cat_id, user_id],
        )

    yield {
        "user_id": user_id,
        "account_id": account_id,
        "other_account_id": other_account_id,
        "cat_id": cat_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
    User.objects.filter(id=user_id).delete()


class TestGetRecentTransactions:
    """AccountService.get_recent_transactions — field mapping, running balance, isolation."""

    tz = ZoneInfo("Africa/Cairo")

    @pytest.mark.django_db
    def test_returns_correct_fields(self, recent_tx_data: dict) -> None:
        # gap: functional — happy path field coverage was zero
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, 'expense', 300, 'EGP', %s, -300)",
                [
                    str(uuid.uuid4()),
                    recent_tx_data["user_id"],
                    recent_tx_data["account_id"],
                    recent_tx_data["cat_id"],
                    date.today(),
                ],
            )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 1
        tx = txns[0]
        assert tx["type"] == "expense"
        assert tx["amount"] == 300.0
        assert tx["currency"] == "EGP"
        assert tx["account_id"] == recent_tx_data["account_id"]
        assert tx["account_name"] == "My Savings"
        assert tx["category_name"] == "Food"
        assert tx["running_balance"] is not None
        assert isinstance(tx["tags"], list)

    @pytest.mark.django_db
    def test_running_balance_accuracy(self, recent_tx_data: dict) -> None:
        # gap: data — running balance value never verified, only checked for not-None
        # account current_balance=10000; 3 expenses ordered oldest→newest: -200, -150, -100
        # Expected running balances newest-first:
        #   tx3 (today,     delta=-100): 10000 - 0            = 10000
        #   tx2 (yesterday, delta=-150): 10000 - (-100)       = 10100
        #   tx1 (2 days ago,delta=-200): 10000 - (-100 + -150)= 10250
        today = date.today()
        with connection.cursor() as cursor:
            for days_ago, delta in [(2, -200), (1, -150), (0, -100)]:
                cursor.execute(
                    "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                    " VALUES (%s, %s, %s, 'expense', %s, 'EGP', %s, %s)",
                    [
                        str(uuid.uuid4()),
                        recent_tx_data["user_id"],
                        recent_tx_data["account_id"],
                        abs(delta),
                        today - timedelta(days=days_ago),
                        delta,
                    ],
                )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 3
        assert txns[0]["running_balance"] == pytest.approx(10000.0)
        assert txns[1]["running_balance"] == pytest.approx(10100.0)
        assert txns[2]["running_balance"] == pytest.approx(10250.0)

    @pytest.mark.django_db
    def test_account_isolation(self, recent_tx_data: dict) -> None:
        # gap: data — no test that other accounts' transactions are excluded
        today = date.today()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, -100)",
                [
                    str(uuid.uuid4()),
                    recent_tx_data["user_id"],
                    recent_tx_data["account_id"],
                    today,
                ],
            )
            # Different account — must not appear
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 999, 'EGP', %s, -999)",
                [
                    str(uuid.uuid4()),
                    recent_tx_data["user_id"],
                    recent_tx_data["other_account_id"],
                    today,
                ],
            )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 1
        assert txns[0]["amount"] == 100.0

    @pytest.mark.django_db
    def test_limit_respected(self, recent_tx_data: dict) -> None:
        # gap: functional — limit parameter was never tested
        today = date.today()
        with connection.cursor() as cursor:
            for i in range(7):
                cursor.execute(
                    "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                    " VALUES (%s, %s, %s, 'expense', 50, 'EGP', %s, -50)",
                    [
                        str(uuid.uuid4()),
                        recent_tx_data["user_id"],
                        recent_tx_data["account_id"],
                        today - timedelta(days=i),
                    ],
                )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"], limit=3)
        assert len(txns) == 3

    @pytest.mark.django_db
    def test_uncategorized_transaction(self, recent_tx_data: dict) -> None:
        # gap: data — NULL category_id must map to category_id=None, not raise
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, -100)",
                [
                    str(uuid.uuid4()),
                    recent_tx_data["user_id"],
                    recent_tx_data["account_id"],
                    date.today(),
                ],
            )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 1
        assert txns[0]["category_id"] is None
        assert txns[0]["category_name"] is None
        assert txns[0]["category_icon"] is None
        assert txns[0]["tags"] == []

    @pytest.mark.django_db
    def test_running_balance_income_transaction(self, recent_tx_data: dict) -> None:
        # gap: data — positive balance_delta (income) never tested in window expression
        # account current_balance=10000; single income tx, delta=+1000
        # No preceding rows → running_balance = 10000 - 0 = 10000
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'income', 1000, 'EGP', %s, 1000)",
                [
                    str(uuid.uuid4()),
                    recent_tx_data["user_id"],
                    recent_tx_data["account_id"],
                    date.today(),
                ],
            )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 1
        assert txns[0]["type"] == "income"
        assert txns[0]["balance_delta"] == pytest.approx(1000.0)
        # Single tx → no preceding rows → running_balance == current_balance (10000)
        assert txns[0]["running_balance"] == pytest.approx(10000.0)


# ---------------------------------------------------------------------------
# get_statement_data — CC statement with billing cycle
# ---------------------------------------------------------------------------


@pytest.fixture
def statement_data(db):
    """User + institution + CC account with billing cycle + savings account."""
    user = UserFactory()
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    cc_id = str(uuid.uuid4())
    savings_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        # CC account with billing cycle metadata: statement_day=15, due_day=5
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance, credit_limit, metadata)"
            " VALUES (%s, %s, %s, 'Test CC', 'credit_card', 'EGP', -5000, 0, 50000,"
            ' \'{"statement_day": 15, "due_day": 5}\'::jsonb)',
            [cc_id, user_id, inst_id],
        )
        # Savings account — no billing cycle
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, 'My Savings', 'savings', 'EGP', 10000, 10000)",
            [savings_id, user_id, inst_id],
        )

    yield {
        "user_id": user_id,
        "cc_id": cc_id,
        "savings_id": savings_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    User.objects.filter(id=user_id).delete()


class TestGetStatementData:
    """get_statement_data — CC statement structure, None for non-CC, spending totals."""

    tz = ZoneInfo("Africa/Cairo")

    @pytest.mark.django_db
    def test_with_billing_cycle(self, statement_data: dict) -> None:
        """CC account with billing_cycle metadata returns full statement structure."""
        from accounts.services import AccountService, get_statement_data

        svc = AccountService(statement_data["user_id"], self.tz)
        account = svc.get_by_id(statement_data["cc_id"])
        assert account is not None

        result = get_statement_data(account, statement_data["user_id"], self.tz)
        assert result is not None
        # Verify top-level keys
        assert "account" in result
        assert "billing_cycle" in result
        assert "transactions" in result
        assert "opening_balance" in result
        assert "total_spending" in result
        assert "total_payments" in result
        assert "closing_balance" in result
        assert "interest_free_days" in result
        assert "interest_free_remain" in result
        assert "interest_free_urgent" in result
        assert "payment_history" in result
        # Verify types
        assert isinstance(result["transactions"], list)
        assert isinstance(result["payment_history"], list)
        assert isinstance(result["total_spending"], float)
        assert isinstance(result["total_payments"], float)
        assert result["interest_free_days"] == 55
        assert result["closing_balance"] == -5000.0

    @pytest.mark.django_db
    def test_without_billing_cycle(self, statement_data: dict) -> None:
        """Savings account (no billing cycle metadata) returns None."""
        from accounts.services import AccountService, get_statement_data

        svc = AccountService(statement_data["user_id"], self.tz)
        account = svc.get_by_id(statement_data["savings_id"])
        assert account is not None

        result = get_statement_data(account, statement_data["user_id"], self.tz)
        assert result is None

    @pytest.mark.django_db
    def test_statement_spending_calculation(self, statement_data: dict) -> None:
        """Spending total aggregates negative balance_delta transactions in period."""
        from accounts.services import AccountService, get_statement_data

        svc = AccountService(statement_data["user_id"], self.tz)
        account = svc.get_by_id(statement_data["cc_id"])
        assert account is not None

        # Compute the current billing period to place transactions within it
        result_empty = get_statement_data(account, statement_data["user_id"], self.tz)
        assert result_empty is not None
        period_start = result_empty["billing_cycle"].period_start
        period_end = result_empty["billing_cycle"].period_end

        # Insert transactions within the billing period
        mid_date = period_start + timedelta(days=5)
        # Clamp to period range
        if mid_date > period_end:
            mid_date = period_end

        with connection.cursor() as cursor:
            # Expense (negative balance_delta = spending)
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 1500, 'EGP', %s, -1500)",
                [
                    str(uuid.uuid4()),
                    statement_data["user_id"],
                    statement_data["cc_id"],
                    mid_date,
                ],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 800, 'EGP', %s, -800)",
                [
                    str(uuid.uuid4()),
                    statement_data["user_id"],
                    statement_data["cc_id"],
                    mid_date,
                ],
            )
            # Payment (positive balance_delta)
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'income', 500, 'EGP', %s, 500)",
                [
                    str(uuid.uuid4()),
                    statement_data["user_id"],
                    statement_data["cc_id"],
                    mid_date,
                ],
            )

        result = get_statement_data(account, statement_data["user_id"], self.tz)
        assert result is not None
        assert result["total_spending"] == pytest.approx(2300.0)
        assert result["total_payments"] == pytest.approx(500.0)
        assert len(result["transactions"]) == 3
        # Opening balance = closing - sum of balance_deltas
        # closing = -5000, deltas sum = -1500 + -800 + 500 = -1800
        # opening = -5000 - (-1800) = -3200
        assert result["opening_balance"] == pytest.approx(-3200.0)


# ---------------------------------------------------------------------------
# AccountService.get_excluded_va_balance — sum of excluded VA balances
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetExcludedVaBalance:
    """AccountService.get_excluded_va_balance returns total of excluded VAs."""

    tz = ZoneInfo("Africa/Cairo")

    def test_returns_sum_of_excluded_va_balances(self, db: None) -> None:
        """Only excluded (non-archived) VA balances are summed."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        # Excluded VA — should be counted
        VirtualAccountFactory(
            user_id=user.id,
            account=account,
            current_balance=500,
            exclude_from_net_worth=True,
            is_archived=False,
        )
        # Non-excluded VA — should be ignored
        VirtualAccountFactory(
            user_id=user.id,
            account=account,
            current_balance=300,
            exclude_from_net_worth=False,
            is_archived=False,
        )

        svc = AccountService(str(user.id), self.tz)
        result = svc.get_excluded_va_balance(str(account.id))
        assert result == pytest.approx(500.0)

    def test_returns_zero_when_no_excluded_vas(self, db: None) -> None:
        """Returns 0.0 when no VAs are excluded from net worth."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        VirtualAccountFactory(
            user_id=user.id,
            account=account,
            current_balance=200,
            exclude_from_net_worth=False,
        )

        svc = AccountService(str(user.id), self.tz)
        result = svc.get_excluded_va_balance(str(account.id))
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# AccountService.get_linked_virtual_accounts — VA list with progress_pct
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetLinkedVirtualAccounts:
    """AccountService.get_linked_virtual_accounts returns non-archived VAs."""

    tz = ZoneInfo("Africa/Cairo")

    def test_returns_linked_vas_with_progress(self, db: None) -> None:
        """Progress pct is computed from current_balance / target_amount."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        va = VirtualAccountFactory(
            user_id=user.id,
            account=account,
            current_balance=750,
            target_amount=1000,
            is_archived=False,
        )

        svc = AccountService(str(user.id), self.tz)
        result = svc.get_linked_virtual_accounts(str(account.id))

        assert len(result) == 1
        assert result[0]["id"] == str(va.id)
        assert result[0]["progress_pct"] == pytest.approx(75.0)

    def test_excludes_archived_vas(self, db: None) -> None:
        """Archived VAs are filtered out."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        VirtualAccountFactory(
            user_id=user.id,
            account=account,
            is_archived=True,
        )

        svc = AccountService(str(user.id), self.tz)
        result = svc.get_linked_virtual_accounts(str(account.id))
        assert result == []

    def test_empty_when_no_vas(self, db: None) -> None:
        """Returns empty list when account has no linked VAs."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)

        svc = AccountService(str(user.id), self.tz)
        result = svc.get_linked_virtual_accounts(str(account.id))
        assert result == []
