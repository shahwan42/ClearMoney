"""
Person service tests — CRUD, loan/repayment, multi-currency, debt summary.
"""

import uuid
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from conftest import SessionFactory, UserFactory
from people.models import Person
from people.services import PersonService
from tests.factories import AccountFactory, InstitutionFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def people_data(db):
    """User + institution + EGP account (10000) + USD account (500) + person."""
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
    yield {
        "user_id": str(user.id),
        "egp_id": str(egp_account.id),
        "usd_id": str(usd_account.id),
    }


def _svc(user_id: str) -> PersonService:
    return PersonService(user_id, TZ)


def _get_balance(account_id: str) -> float:
    """Fetch current_balance from DB via ORM."""
    return float(Account.objects.get(id=account_id).current_balance)


def _get_person_balance(person_id: str) -> dict[str, float]:
    """Fetch person balance columns via ORM."""
    p = Person.objects.get(id=person_id)
    return {
        "net_balance": float(p.net_balance),
        "net_balance_egp": float(p.net_balance_egp),
        "net_balance_usd": float(p.net_balance_usd),
    }


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPersonCRUD:
    def test_create_person(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Ahmed")
        assert person["name"] == "Ahmed"
        assert person["net_balance_egp"] == 0
        assert person["net_balance_usd"] == 0

    def test_create_empty_name_fails(self, people_data):
        svc = _svc(people_data["user_id"])
        with pytest.raises(ValueError, match="name is required"):
            svc.create("")

    def test_get_all_sorted_by_name(self, people_data):
        svc = _svc(people_data["user_id"])
        svc.create("Zara")
        svc.create("Ahmed")
        persons = svc.get_all()
        assert len(persons) == 2
        assert persons[0]["name"] == "Ahmed"
        assert persons[1]["name"] == "Zara"

    def test_update_person(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Omar")
        updated = svc.update(person["id"], "Omar Updated", "a friend")
        assert updated is not None
        assert updated["name"] == "Omar Updated"
        assert updated["note"] == "a friend"

    def test_delete_person(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("ToDelete")
        assert svc.delete(person["id"]) is True
        assert svc.get_by_id(person["id"]) is None

    def test_update_nonexistent_returns_none(self, people_data):
        svc = _svc(people_data["user_id"])
        assert svc.update(str(uuid.uuid4()), "New Name") is None


# ---------------------------------------------------------------------------
# Loan Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecordLoan:
    def test_loan_out_updates_balances(self, people_data):
        """I lent 1000 EGP → account -1000, person +1000."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Ali")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 1000
        assert bal["net_balance_usd"] == 0
        assert _get_balance(people_data["egp_id"]) == 9000  # 10000 - 1000

    def test_loan_in_updates_balances(self, people_data):
        """I borrowed 2000 EGP → account +2000, person -2000."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Sara")

        svc.record_loan(person["id"], people_data["egp_id"], 2000, "loan_in")

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == -2000
        assert _get_balance(people_data["egp_id"]) == 12000  # 10000 + 2000

    def test_multi_currency_isolation(self, people_data):
        """Lend EGP + borrow USD — tracked independently."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Mixed")

        svc.record_loan(person["id"], people_data["egp_id"], 5000, "loan_out")
        svc.record_loan(person["id"], people_data["usd_id"], 200, "loan_in")

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 5000
        assert bal["net_balance_usd"] == -200
        # Legacy net_balance = sum of deltas: +5000 + (-200) = 4800
        assert bal["net_balance"] == 4800

    def test_invalid_amount_fails(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Test")
        with pytest.raises(ValueError, match="amount must be positive"):
            svc.record_loan(person["id"], people_data["egp_id"], -100, "loan_out")

    def test_invalid_type_fails(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Test")
        with pytest.raises(ValueError, match="type must be loan_out or loan_in"):
            svc.record_loan(person["id"], people_data["egp_id"], 100, "expense")

    def test_account_not_found_raises_value_error(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("AccountMiss")
        with pytest.raises(ValueError, match="Account not found"):
            svc.record_loan(person["id"], str(uuid.uuid4()), 100, "loan_out")

    def test_record_loan_date_parsing(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("DateParse")
        tx = svc.record_loan(
            person["id"], people_data["egp_id"], 100, "loan_out", tx_date="2026-04-01"
        )
        assert str(tx["date"]) == "2026-04-01"


# ---------------------------------------------------------------------------
# Repayment Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecordRepayment:
    def test_repayment_reduces_positive_balance(self, people_data):
        """They owe me 1000 → repay 500 → balance drops to 500."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Debtor")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 500)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 500
        # Account: 10000 - 1000 (loan out) + 500 (repayment enters) = 9500
        assert _get_balance(people_data["egp_id"]) == 9500

    def test_repayment_reduces_negative_balance(self, people_data):
        """I owe them 1000 → I repay 400 → balance goes from -1000 to -600."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Creditor")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_in")
        svc.record_repayment(person["id"], people_data["egp_id"], 400)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == -600
        # Account: 10000 + 1000 (loan in) - 400 (repayment leaves) = 10600
        assert _get_balance(people_data["egp_id"]) == 10600

    def test_multi_currency_repayment(self, people_data):
        """Lend 1000 EGP + borrow 500 USD → repay 300 USD → USD debt -200."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Multi")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")
        svc.record_loan(person["id"], people_data["usd_id"], 500, "loan_in")
        svc.record_repayment(person["id"], people_data["usd_id"], 300)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 1000  # unchanged
        assert bal["net_balance_usd"] == -200  # -500 + 300

    def test_full_lifecycle_lend_repay_settle(self, people_data):
        """Lend 1000 → repay 500 → repay 500 → settled (0)."""
        svc = _svc(people_data["user_id"])
        person = svc.create("Lifecycle")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 500)
        svc.record_repayment(person["id"], people_data["egp_id"], 500)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 0
        assert bal["net_balance"] == 0

    def test_record_repayment_date_parsing(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("RepayDateParse")
        svc.record_loan(person["id"], people_data["egp_id"], 100, "loan_out")
        tx = svc.record_repayment(
            person["id"], people_data["egp_id"], 50, tx_date="2026-04-02"
        )
        assert str(tx["date"]) == "2026-04-02"

    def test_person_not_found_raises_value_error(self, people_data):
        svc = _svc(people_data["user_id"])
        with pytest.raises(ValueError, match="Person not found"):
            svc.record_repayment(str(uuid.uuid4()), people_data["egp_id"], 50)

    def test_repayment_direction_zero_balance(self, people_data):
        """Zero balance -> defaults to 'else' block (money leaves, person delta positive)."""
        svc = _svc(people_data["user_id"])
        person = svc.create("ZeroBal")
        svc.record_repayment(person["id"], people_data["usd_id"], 50)
        bal = _get_person_balance(person["id"])
        assert bal["net_balance_usd"] == 50
        assert _get_balance(people_data["usd_id"]) == 450


# ---------------------------------------------------------------------------
# Debt Summary Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDebtSummary:
    def test_by_currency_breakdown(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Summary")

        svc.record_loan(person["id"], people_data["egp_id"], 2000, "loan_out")
        svc.record_loan(person["id"], people_data["usd_id"], 100, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 500)

        summary = svc.get_debt_summary(person["id"])
        assert summary is not None
        assert summary["total_lent"] == 2100
        assert summary["total_repaid"] == 500

        # EGP first, then USD
        assert len(summary["by_currency"]) == 2
        egp = summary["by_currency"][0]
        assert egp["currency"] == "EGP"
        assert egp["total_lent"] == 2000
        assert egp["total_repaid"] == 500
        usd = summary["by_currency"][1]
        assert usd["currency"] == "USD"
        assert usd["total_lent"] == 100
        assert usd["total_repaid"] == 0

    def test_progress_percentage(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Progress")

        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 250)

        summary = svc.get_debt_summary(person["id"])
        assert summary is not None
        assert summary["progress_pct"] == 25.0

    def test_returns_none_for_nonexistent(self, people_data):
        svc = _svc(people_data["user_id"])
        assert svc.get_debt_summary(str(uuid.uuid4())) is None

    def test_transactions_included(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("TxList")

        svc.record_loan(person["id"], people_data["egp_id"], 500, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 200)

        summary = svc.get_debt_summary(person["id"])
        assert summary is not None
        assert len(summary["transactions"]) == 2
        # Both transactions present (order: date DESC, created_at DESC)
        types = {tx["type"] for tx in summary["transactions"]}
        assert types == {"loan_out", "loan_repayment"}

    def test_summary_zero_debt(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Zero")
        summary = svc.get_debt_summary(person["id"])
        assert summary["total_lent"] == 0
        assert summary["total_borrowed"] == 0
        assert summary["total_repaid"] == 0
        assert summary["progress_pct"] == 0.0
        assert summary["projected_payoff"] is None

    def test_summary_single_transaction(self, people_data):
        svc = _svc(people_data["user_id"])
        person = svc.create("Single")
        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out")
        summary = svc.get_debt_summary(person["id"])
        assert summary["total_lent"] == 1000
        assert summary["progress_pct"] == 0.0
        assert summary["projected_payoff"] is None

    def test_projected_payoff_calculation_and_zero_division(self, people_data):
        from datetime import date, timedelta
        svc = _svc(people_data["user_id"])
        person = svc.create("Payoff")

        # Repayments on the same day -> total_days = 0 avoids division by zero
        svc.record_loan(person["id"], people_data["egp_id"], 1000, "loan_out", tx_date="2026-04-01")
        svc.record_repayment(person["id"], people_data["egp_id"], 100, tx_date="2026-04-02")
        svc.record_repayment(person["id"], people_data["egp_id"], 100, tx_date="2026-04-02")

        summary = svc.get_debt_summary(person["id"])
        assert summary["projected_payoff"] is None

        # Add payment on different day to allow calculation
        svc.record_repayment(person["id"], people_data["egp_id"], 100, tx_date="2026-04-04")
        summary = svc.get_debt_summary(person["id"])
        # Dates: 04-02, 04-02, 04-04 -> len = 3
        # total_repaid = 300, avg_repayment = 100
        # first = 04-02, last = 04-04 -> total_days = 2
        # avg_interval_days = 2 / 2 = 1.0
        # remaining = 700, payments_needed = 7.0
        # days_to_payoff = 7
        assert summary["projected_payoff"] == date.today() + timedelta(days=7)


# ---------------------------------------------------------------------------
# Over-Repayment Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOverRepayment:
    """Tests for repaying more than owed — balance flips sign."""

    def test_over_repay_positive_flips_to_negative(self, people_data: dict) -> None:
        """Person owes me 500 EGP, repay 800 → net_balance_egp = -300 (now I owe them)."""
        svc = _svc(people_data["user_id"])
        person = svc.create("OverPayPos")

        svc.record_loan(person["id"], people_data["egp_id"], 500, "loan_out")
        svc.record_repayment(person["id"], people_data["egp_id"], 800)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == -300
        assert bal["net_balance"] == -300
        # Account: 10000 - 500 (loan out) + 800 (repayment enters) = 10300
        assert _get_balance(people_data["egp_id"]) == 10300

    def test_over_repay_negative_flips_to_positive(self, people_data: dict) -> None:
        """I owe person 500 EGP, repay 800 → net_balance_egp = 300 (now they owe me)."""
        svc = _svc(people_data["user_id"])
        person = svc.create("OverPayNeg")

        svc.record_loan(person["id"], people_data["egp_id"], 500, "loan_in")
        svc.record_repayment(person["id"], people_data["egp_id"], 800)

        bal = _get_person_balance(person["id"])
        assert bal["net_balance_egp"] == 300
        assert bal["net_balance"] == 300
        # Account: 10000 + 500 (loan in) - 800 (repayment leaves) = 9700
        assert _get_balance(people_data["egp_id"]) == 9700
