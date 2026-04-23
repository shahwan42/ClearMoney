"""
Tests for accounts services — billing cycle math + AccountService + InstitutionService.

Billing tests are pure (no DB). AccountService/InstitutionService tests need PostgreSQL.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Institution
from accounts.services import AccountService, InstitutionService
from conftest import SessionFactory, UserFactory
from core.billing import (
    compute_due_date,
    get_billing_cycle_info,
    get_credit_card_utilization,
    interest_free_remaining,
    parse_billing_cycle,
)
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    CurrencyFactory,
    InstitutionFactory,
    TransactionFactory,
    VirtualAccountFactory,
)


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


@pytest.mark.django_db
class TestDynamicCurrencies:
    def test_create_accepts_user_active_currency(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        SessionFactory(user=user)
        inst = InstitutionFactory(user_id=user.id)
        from auth_app.currency import set_user_active_currencies

        set_user_active_currencies(str(user.id), ["EGP", "EUR"])
        svc = AccountService(str(user.id), ZoneInfo("Africa/Cairo"))

        account = svc.create(
            {
                "institution_id": str(inst.id),
                "name": "Euro Savings",
                "type": "savings",
                "currency": "EUR",
                "initial_balance": 10.0,
            }
        )

        assert account["currency"] == "EUR"

    def test_create_rejects_inactive_currency(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        SessionFactory(user=user)
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("Africa/Cairo"))

        with pytest.raises(ValueError, match="invalid currency"):
            svc.create(
                {
                    "institution_id": str(inst.id),
                    "name": "Euro Savings",
                    "type": "savings",
                    "currency": "EUR",
                    "initial_balance": 10.0,
                }
            )


# ---------------------------------------------------------------------------
# AccountService.get_for_dropdown — needs real DB
# ---------------------------------------------------------------------------


@pytest.fixture
def dropdown_data(db):
    """User with institution + 1 active account + 1 dormant account."""
    user = UserFactory()
    SessionFactory(user=user)
    institution = InstitutionFactory(user_id=user.id, name="Bank")
    active = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Active Savings",
        currency="EGP",
        current_balance=5000,
        initial_balance=5000,
    )
    dormant = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Dormant",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
        is_dormant=True,
    )
    yield {
        "user_id": str(user.id),
        "active_id": str(active.id),
        "dormant_id": str(dormant.id),
    }


class TestGetForDropdown:
    """AccountService.get_for_dropdown returns lightweight account dicts."""

    tz = ZoneInfo("Africa/Cairo")

    def test_excludes_dormant(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown()
        ids = [a.id for a in accounts]
        assert dropdown_data["active_id"] in ids
        assert dropdown_data["dormant_id"] not in ids

    def test_without_balance(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown()
        assert len(accounts) >= 1
        acc = accounts[0]
        assert acc.id
        assert acc.name
        assert acc.currency
        assert acc.current_balance is None

    def test_with_balance(self, dropdown_data: dict) -> None:
        svc = AccountService(dropdown_data["user_id"], self.tz)
        accounts = svc.get_for_dropdown(include_balance=True)
        acc = accounts[0]
        assert acc.current_balance is not None
        assert isinstance(acc.current_balance, float)

    def test_ordered_by_usage(self, dropdown_data: dict) -> None:
        """Account with more transactions comes first in the dropdown."""
        user_id = dropdown_data["user_id"]
        # Add 3 transactions to the active account so it has higher usage than zero
        for _ in range(3):
            TransactionFactory(
                user_id=user_id,
                account_id=dropdown_data["active_id"],
            )
        svc = AccountService(user_id, self.tz)
        accounts = svc.get_for_dropdown()
        ids = [a.id for a in accounts]
        assert ids[0] == dropdown_data["active_id"]

    def test_isolation_ordering(self, dropdown_data: dict) -> None:
        """User B's transaction volume does not affect user A's ordering."""
        user_b = UserFactory()
        SessionFactory(user=user_b)
        inst_b = InstitutionFactory(user_id=user_b.id)
        acc_b = AccountFactory(
            user_id=user_b.id, institution_id=inst_b.id, currency="EGP"
        )
        for _ in range(50):
            TransactionFactory(user_id=user_b.id, account_id=acc_b.id)

        svc_a = AccountService(dropdown_data["user_id"], self.tz)
        accounts_a = svc_a.get_for_dropdown()
        ids_a = {a.id for a in accounts_a}
        assert str(acc_b.id) not in ids_a


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
    institution = InstitutionFactory(user_id=user.id, name="Test Bank")
    account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="My Savings",
        currency="EGP",
        current_balance=10000,
    )
    other_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Other Account",
        currency="EGP",
        current_balance=5000,
    )
    category = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")
    yield {
        "user_id": str(user.id),
        "account_id": str(account.id),
        "other_account_id": str(other_account.id),
        "cat_id": str(category.id),
    }


class TestGetRecentTransactions:
    """AccountService.get_recent_transactions — field mapping, running balance, isolation."""

    tz = ZoneInfo("Africa/Cairo")

    @pytest.mark.django_db
    def test_returns_correct_fields(self, recent_tx_data: dict) -> None:
        # gap: functional — happy path field coverage was zero
        TransactionFactory(
            user_id=recent_tx_data["user_id"],
            account_id=recent_tx_data["account_id"],
            category_id=recent_tx_data["cat_id"],
            type="expense",
            amount=300,
            currency="EGP",
            date=date.today(),
            balance_delta=-300,
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
        for days_ago, delta in [(2, -200), (1, -150), (0, -100)]:
            TransactionFactory(
                user_id=recent_tx_data["user_id"],
                account_id=recent_tx_data["account_id"],
                type="expense",
                amount=abs(delta),
                currency="EGP",
                date=today - timedelta(days=days_ago),
                balance_delta=delta,
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
        TransactionFactory(
            user_id=recent_tx_data["user_id"],
            account_id=recent_tx_data["account_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=today,
            balance_delta=-100,
        )
        # Different account — must not appear
        TransactionFactory(
            user_id=recent_tx_data["user_id"],
            account_id=recent_tx_data["other_account_id"],
            type="expense",
            amount=999,
            currency="EGP",
            date=today,
            balance_delta=-999,
        )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"])
        assert len(txns) == 1
        assert txns[0]["amount"] == 100.0

    @pytest.mark.django_db
    def test_limit_respected(self, recent_tx_data: dict) -> None:
        # gap: functional — limit parameter was never tested
        today = date.today()
        for i in range(7):
            TransactionFactory(
                user_id=recent_tx_data["user_id"],
                account_id=recent_tx_data["account_id"],
                type="expense",
                amount=50,
                currency="EGP",
                date=today - timedelta(days=i),
                balance_delta=-50,
            )
        svc = AccountService(recent_tx_data["user_id"], self.tz)
        txns = svc.get_recent_transactions(recent_tx_data["account_id"], limit=3)
        assert len(txns) == 3

    @pytest.mark.django_db
    def test_uncategorized_transaction(self, recent_tx_data: dict) -> None:
        # gap: data — NULL category_id must map to category_id=None, not raise
        TransactionFactory(
            user_id=recent_tx_data["user_id"],
            account_id=recent_tx_data["account_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date.today(),
            balance_delta=-100,
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
        TransactionFactory(
            user_id=recent_tx_data["user_id"],
            account_id=recent_tx_data["account_id"],
            type="income",
            amount=1000,
            currency="EGP",
            date=date.today(),
            balance_delta=1000,
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
    institution = InstitutionFactory(user_id=user.id, name="Test Bank")
    # CC account with billing cycle metadata: statement_day=15, due_day=5
    cc = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Test CC",
        type="credit_card",
        currency="EGP",
        current_balance=-5000,
        initial_balance=0,
        credit_limit=50000,
        metadata={"statement_day": 15, "due_day": 5},
    )
    savings = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="My Savings",
        currency="EGP",
        current_balance=10000,
        initial_balance=10000,
    )
    yield {
        "user_id": str(user.id),
        "cc_id": str(cc.id),
        "savings_id": str(savings.id),
    }


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

        # Expense (negative balance_delta = spending)
        TransactionFactory(
            user_id=statement_data["user_id"],
            account_id=statement_data["cc_id"],
            type="expense",
            amount=1500,
            currency="EGP",
            date=mid_date,
            balance_delta=-1500,
        )
        TransactionFactory(
            user_id=statement_data["user_id"],
            account_id=statement_data["cc_id"],
            type="expense",
            amount=800,
            currency="EGP",
            date=mid_date,
            balance_delta=-800,
        )
        # Payment (positive balance_delta)
        TransactionFactory(
            user_id=statement_data["user_id"],
            account_id=statement_data["cc_id"],
            type="income",
            amount=500,
            currency="EGP",
            date=mid_date,
            balance_delta=500,
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


# ---------------------------------------------------------------------------
# InstitutionService.get_or_create
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# load_health_warnings — account health constraint checking
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoadHealthWarnings:
    """load_health_warnings checks min_balance and min_monthly_deposit constraints."""

    tz = ZoneInfo("Africa/Cairo")

    def test_min_balance_warning_fires_when_below_threshold(self) -> None:
        """Account below min_balance threshold returns HealthWarning."""
        from accounts.services import load_health_warnings

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Savings",
            current_balance=500,
            health_config={"min_balance": 1000},
        )

        all_accounts = [
            {
                "id": str(account.id),
                "name": account.name,
                "current_balance": 500,
                "health_config": {"min_balance": 1000},
            }
        ]

        warnings = load_health_warnings(str(user.id), all_accounts, self.tz)

        assert len(warnings) == 1
        assert warnings[0].account_name == "Savings"
        assert warnings[0].account_id == str(account.id)
        assert warnings[0].rule == "min_balance"
        assert "below minimum" in warnings[0].message
        assert "500.00" in warnings[0].message
        assert "1,000.00" in warnings[0].message

    def test_min_balance_no_warning_when_above_threshold(self) -> None:
        """Account above min_balance threshold returns empty list."""
        from accounts.services import load_health_warnings

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Savings",
            current_balance=2000,
            health_config={"min_balance": 1000},
        )

        all_accounts = [
            {
                "id": str(account.id),
                "name": account.name,
                "current_balance": 2000,
                "health_config": {"min_balance": 1000},
            }
        ]

        warnings = load_health_warnings(str(user.id), all_accounts, self.tz)

        assert len(warnings) == 0

    def test_min_monthly_deposit_warning_fires_when_no_deposit(self) -> None:
        """Account without required monthly deposit returns HealthWarning."""
        from accounts.services import load_health_warnings

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Checking",
            current_balance=1000,
            health_config={"min_monthly_deposit": 5000},
        )

        all_accounts = [
            {
                "id": str(account.id),
                "name": account.name,
                "current_balance": 1000,
                "health_config": {"min_monthly_deposit": 5000},
            }
        ]

        warnings = load_health_warnings(str(user.id), all_accounts, self.tz)

        assert len(warnings) == 1
        assert warnings[0].account_name == "Checking"
        assert warnings[0].account_id == str(account.id)
        assert warnings[0].rule == "min_monthly_deposit"
        assert "missing required monthly deposit" in warnings[0].message
        assert "5,000.00" in warnings[0].message

    def test_min_monthly_deposit_no_warning_when_deposit_exists(self) -> None:
        """Account with required deposit in current month returns empty list."""
        from accounts.services import load_health_warnings

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Checking",
            current_balance=10000,
            health_config={"min_monthly_deposit": 5000},
        )

        today = date.today()
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            type="income",
            amount=5000,
            currency="EGP",
            date=today,
            balance_delta=5000,
        )

        all_accounts = [
            {
                "id": str(account.id),
                "name": account.name,
                "current_balance": 10000,
                "health_config": {"min_monthly_deposit": 5000},
            }
        ]

        warnings = load_health_warnings(str(user.id), all_accounts, self.tz)

        assert len(warnings) == 0

    def test_returns_empty_for_accounts_without_health_config(self) -> None:
        """Account with no health_config returns empty list."""
        from accounts.services import load_health_warnings

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Savings",
            current_balance=500,
            health_config=None,
        )

        all_accounts = [
            {
                "id": str(account.id),
                "name": account.name,
                "current_balance": 500,
                "health_config": None,
            }
        ]

        warnings = load_health_warnings(str(user.id), all_accounts, self.tz)

        assert len(warnings) == 0


@pytest.mark.django_db
class TestInstitutionServiceGetOrCreate:
    """InstitutionService.get_or_create() deduplicates by name+type."""

    tz = ZoneInfo("Africa/Cairo")

    def test_creates_new_institution(self) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        result = svc.get_or_create("CIB", "bank", icon="cib.svg")
        assert result["name"] == "CIB"
        assert result["type"] == "bank"
        assert Institution.objects.filter(user_id=user.id, name="CIB").count() == 1

    def test_reuses_existing_same_name_and_type(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id, name="CIB", type="bank")
        svc = InstitutionService(str(user.id), self.tz)
        result = svc.get_or_create("CIB", "bank")
        assert result["id"] == str(inst.id)
        assert (
            Institution.objects.filter(user_id=user.id, name__iexact="CIB").count() == 1
        )

    def test_case_insensitive_match(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id, name="CIB", type="bank")
        svc = InstitutionService(str(user.id), self.tz)
        result = svc.get_or_create("cib", "bank")
        assert result["id"] == str(inst.id)

    def test_different_type_creates_new(self) -> None:
        user = UserFactory()
        InstitutionFactory(user_id=user.id, name="Vodafone", type="fintech")
        svc = InstitutionService(str(user.id), self.tz)
        svc.get_or_create("Vodafone", "wallet")
        assert Institution.objects.filter(user_id=user.id, name="Vodafone").count() == 2

    def test_empty_name_raises(self) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        with pytest.raises(ValueError):
            svc.get_or_create("", "bank")

    def test_invalid_type_raises(self) -> None:
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        with pytest.raises(ValueError):
            svc.get_or_create("CIB", "invalid")

    def test_user_isolation(self) -> None:
        """User A's institution is not reused for User B."""
        user_a = UserFactory()
        user_b = UserFactory()
        InstitutionFactory(user_id=user_a.id, name="CIB", type="bank")
        svc_b = InstitutionService(str(user_b.id), self.tz)
        svc_b.get_or_create("CIB", "bank")
        assert Institution.objects.filter(name="CIB").count() == 2
