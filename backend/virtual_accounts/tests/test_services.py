"""
Virtual account service tests — CRUD, allocations, and balance recalculation.

Port of Go's internal/repository/virtual_account_test.go +
internal/service/virtual_account_test.go. Tests run against the real
database with --reuse-db (Go owns schema).
"""

import uuid
from datetime import date

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from tests.factories import AccountFactory, InstitutionFactory
from virtual_accounts.services import VirtualAccountService


@pytest.fixture
def va_data(db):
    """User + institution + bank account (balance 50000) for VA tests."""
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

    yield {
        "user_id": user_id,
        "account_id": str(acct.id),
    }

    # Cleanup — order matters for FK constraints
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM virtual_account_allocations WHERE virtual_account_id IN "
            "(SELECT id FROM virtual_accounts WHERE user_id = %s)",
            [user_id],
        )
        cursor.execute("DELETE FROM virtual_accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _svc(user_id: str) -> VirtualAccountService:
    return VirtualAccountService(user_id)


# ---------------------------------------------------------------------------
# get_all
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAll:
    def test_empty(self, va_data):
        svc = _svc(va_data["user_id"])
        assert svc.get_all() == []

    def test_returns_active_only(self, va_data):
        svc = _svc(va_data["user_id"])
        svc.create(name="Active VA", account_id=va_data["account_id"])
        archived = svc.create(name="Archived VA", account_id=va_data["account_id"])
        svc.archive(archived["id"])

        result = svc.get_all()
        assert len(result) == 1
        assert result[0]["name"] == "Active VA"

    def test_ordered_by_display_order(self, va_data):
        svc = _svc(va_data["user_id"])
        # Create VAs — display_order defaults to 0, so both have same order
        va1 = svc.create(name="Second", account_id=va_data["account_id"])
        va2 = svc.create(name="First", account_id=va_data["account_id"])

        # Manually set display_order to verify ordering
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE virtual_accounts SET display_order = 2 WHERE id = %s",
                [va1["id"]],
            )
            cursor.execute(
                "UPDATE virtual_accounts SET display_order = 1 WHERE id = %s",
                [va2["id"]],
            )

        result = svc.get_all()
        assert len(result) == 2
        assert result[0]["name"] == "First"
        assert result[1]["name"] == "Second"


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetByID:
    def test_found(self, va_data):
        svc = _svc(va_data["user_id"])
        created = svc.create(name="Test VA", account_id=va_data["account_id"])
        result = svc.get_by_id(created["id"])

        assert result is not None
        assert result["name"] == "Test VA"

    def test_not_found(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.get_by_id(str(uuid.uuid4()))
        assert result is None

    def test_other_user_not_found(self, va_data):
        svc = _svc(va_data["user_id"])
        created = svc.create(name="My VA", account_id=va_data["account_id"])

        other_svc = _svc(str(uuid.uuid4()))
        result = other_svc.get_by_id(created["id"])
        assert result is None


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_creates_va(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.create(
            name="Emergency Fund",
            target_amount=100000,
            icon="🏥",
            color="#ff0000",
            account_id=va_data["account_id"],
        )

        assert result["id"] is not None
        assert result["name"] == "Emergency Fund"
        assert result["target_amount"] == 100000.0
        assert result["icon"] == "🏥"
        assert result["color"] == "#ff0000"
        assert result["current_balance"] == 0.0
        assert result["is_archived"] is False
        assert result["account_id"] == va_data["account_id"]

    def test_validates_name_required(self, va_data):
        svc = _svc(va_data["user_id"])
        with pytest.raises(ValueError, match="name is required"):
            svc.create(name="")

    def test_validates_blank_name(self, va_data):
        svc = _svc(va_data["user_id"])
        with pytest.raises(ValueError, match="name is required"):
            svc.create(name="   ")

    def test_defaults_color(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.create(name="No Color")
        assert result["color"] == "#0d9488"

    def test_optional_target(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.create(name="No Target")
        assert result["target_amount"] is None
        assert result["progress_pct"] == 0.0

    def test_with_exclude(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.create(
            name="Held Money",
            exclude_from_net_worth=True,
        )
        assert result["exclude_from_net_worth"] is True


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdate:
    def test_updates_fields(self, va_data):
        svc = _svc(va_data["user_id"])
        created = svc.create(name="Old Name")

        updated = svc.update(
            va_id=created["id"],
            name="New Name",
            target_amount=50000,
            icon="🎯",
            color="#ff0000",
            account_id=va_data["account_id"],
            exclude_from_net_worth=True,
        )
        assert updated is True

        result = svc.get_by_id(created["id"])
        assert result is not None
        assert result["name"] == "New Name"
        assert result["target_amount"] == 50000.0
        assert result["icon"] == "🎯"
        assert result["color"] == "#ff0000"
        assert result["exclude_from_net_worth"] is True
        assert result["account_id"] == va_data["account_id"]

    def test_validates_name_required(self, va_data):
        svc = _svc(va_data["user_id"])
        created = svc.create(name="Test")

        with pytest.raises(ValueError, match="name is required"):
            svc.update(va_id=created["id"], name="")

    def test_nonexistent_returns_false(self, va_data):
        svc = _svc(va_data["user_id"])
        result = svc.update(va_id=str(uuid.uuid4()), name="Nope")
        assert result is False


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchive:
    def test_archives_va(self, va_data):
        svc = _svc(va_data["user_id"])
        created = svc.create(name="To Archive")

        assert svc.archive(created["id"]) is True

        # Should not appear in get_all
        assert len(svc.get_all()) == 0

        # But should still be fetchable by ID
        va = svc.get_by_id(created["id"])
        assert va is not None
        assert va["is_archived"] is True

    def test_nonexistent_returns_false(self, va_data):
        svc = _svc(va_data["user_id"])
        assert svc.archive(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# direct_allocate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDirectAllocate:
    def test_contribution_increases_balance(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        svc.direct_allocate(va["id"], 5000, "Initial deposit", date.today())

        result = svc.get_by_id(va["id"])
        assert result is not None
        assert result["current_balance"] == 5000.0

    def test_withdrawal_decreases_balance(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        svc.direct_allocate(va["id"], 5000, "Deposit", date.today())
        svc.direct_allocate(va["id"], -2000, "Withdrawal", date.today())

        result = svc.get_by_id(va["id"])
        assert result is not None
        assert result["current_balance"] == 3000.0

    def test_zero_amount_raises(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        with pytest.raises(ValueError, match="cannot be zero"):
            svc.direct_allocate(va["id"], 0, "", date.today())

    def test_with_note(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        svc.direct_allocate(va["id"], 1000, "Salary allocation", date.today())

        allocs = svc.get_allocations(va["id"])
        assert len(allocs) == 1
        assert allocs[0]["note"] == "Salary allocation"
        assert allocs[0]["amount"] == 1000.0
        assert allocs[0]["transaction_id"] is None

    def test_multiple_allocations_sum(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        svc.direct_allocate(va["id"], 1000, "", date.today())
        svc.direct_allocate(va["id"], 2000, "", date.today())
        svc.direct_allocate(va["id"], 500, "", date.today())

        result = svc.get_by_id(va["id"])
        assert result is not None
        assert result["current_balance"] == 3500.0


# ---------------------------------------------------------------------------
# toggle_exclude
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestToggleExclude:
    def test_toggles_false_to_true(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund", exclude_from_net_worth=False)

        assert svc.toggle_exclude(va["id"]) is True

        result = svc.get_by_id(va["id"])
        assert result is not None
        assert result["exclude_from_net_worth"] is True

    def test_toggles_true_to_false(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund", exclude_from_net_worth=True)

        assert svc.toggle_exclude(va["id"]) is True

        result = svc.get_by_id(va["id"])
        assert result is not None
        assert result["exclude_from_net_worth"] is False

    def test_nonexistent_returns_false(self, va_data):
        svc = _svc(va_data["user_id"])
        assert svc.toggle_exclude(str(uuid.uuid4())) is False


# ---------------------------------------------------------------------------
# get_allocations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAllocations:
    def test_returns_direct_allocations(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        svc.direct_allocate(va["id"], 1000, "First", date.today())
        svc.direct_allocate(va["id"], 2000, "Second", date.today())

        allocs = svc.get_allocations(va["id"])
        assert len(allocs) == 2

    def test_respects_limit(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Fund")

        for i in range(5):
            svc.direct_allocate(va["id"], 100, f"Alloc {i}", date.today())

        allocs = svc.get_allocations(va["id"], limit=3)
        assert len(allocs) == 3


# ---------------------------------------------------------------------------
# get_by_account_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetByAccountID:
    def test_returns_linked_vas(self, va_data):
        svc = _svc(va_data["user_id"])
        svc.create(name="Linked", account_id=va_data["account_id"])
        svc.create(name="Unlinked")  # no account_id

        result = svc.get_by_account_id(va_data["account_id"])
        assert len(result) == 1
        assert result[0]["name"] == "Linked"

    def test_excludes_archived(self, va_data):
        svc = _svc(va_data["user_id"])
        va = svc.create(name="Linked Archived", account_id=va_data["account_id"])
        svc.archive(va["id"])

        result = svc.get_by_account_id(va_data["account_id"])
        assert len(result) == 0
