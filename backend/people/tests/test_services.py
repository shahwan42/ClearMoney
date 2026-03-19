"""
Person service tests — CRUD, loan/repayment, multi-currency, debt summary.

Port of Go's internal/service/person_test.go (9 test cases → 16 Django tests).
Uses raw SQL fixtures for PostgreSQL enum columns. Tests run against the real
database with --reuse-db (Go owns schema).
"""

import uuid
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from people.services import PersonService

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def people_data(db):
    """User + institution + EGP account (10000) + USD account (500) + person.

    Creates minimal test data for person service tests.
    """
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    usd_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s, %s)",
            [egp_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'USD'::currency_type, %s, %s)",
            [usd_id, user_id, inst_id, "USD Savings", 500, 500],
        )

    yield {
        "user_id": user_id,
        "egp_id": egp_id,
        "usd_id": usd_id,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM persons WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _svc(user_id: str) -> PersonService:
    return PersonService(user_id, TZ)


def _get_balance(account_id: str) -> float:
    """Fetch current_balance directly from DB."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_balance FROM accounts WHERE id = %s", [account_id])
        row = cursor.fetchone()
    return float(row[0]) if row else 0


def _get_person_balance(person_id: str) -> dict[str, float]:
    """Fetch person balance columns directly from DB."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT net_balance, net_balance_egp, net_balance_usd FROM persons WHERE id = %s",
            [person_id],
        )
        row = cursor.fetchone()
    assert row is not None
    return {"net_balance": float(row[0]), "net_balance_egp": float(row[1]), "net_balance_usd": float(row[2])}


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
