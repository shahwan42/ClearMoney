"""
Critical data isolation security tests — verify per-user data boundaries.

Pattern: Create data for User A using factories, query as User B, assert empty/None.
Each test validates that Django ORM's for_user() scoping prevents cross-user data leaks.
"""

from collections.abc import Generator
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from accounts.services import AccountService, InstitutionService
from budgets.services import BudgetService
from categories.services import CategoryService
from people.services import PersonService
from tests.factories import (
    AccountFactory,
    BudgetFactory,
    CategoryFactory,
    InstitutionFactory,
    PersonFactory,
    SessionFactory,
    TransactionFactory,
    UserFactory,
    VirtualAccountFactory,
)
from transactions.services import TransactionService
from virtual_accounts.services import VirtualAccountService

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def two_users(db: Any) -> Generator[dict[str, str], None, None]:
    """Create two isolated users with sessions for cross-user isolation tests."""
    user_a = UserFactory()
    user_b = UserFactory()
    SessionFactory(user=user_a)
    SessionFactory(user=user_b)

    yield {"user_a_id": str(user_a.id), "user_b_id": str(user_b.id)}


@pytest.mark.django_db
class TestDataIsolation:
    """Verify that every service enforces per-user data isolation.

    Each test creates data for User A and confirms User B cannot access it.
    These are critical security tests — a failure here means a data leak.
    """

    # gap: data
    def test_accounts_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's accounts."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        inst = InstitutionFactory(user_id=uid_a)
        AccountFactory(user_id=uid_a, institution_id=inst.id)
        AccountFactory(user_id=uid_a, institution_id=inst.id, name="Second Account")

        svc_a = AccountService(uid_a, TZ)
        svc_b = AccountService(uid_b, TZ)

        assert len(svc_a.get_all()) == 2
        assert len(svc_b.get_all()) == 0

    # gap: data
    def test_institutions_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's institutions."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        InstitutionFactory(user_id=uid_a, name="Bank A")
        InstitutionFactory(user_id=uid_a, name="Bank B")

        svc_a = InstitutionService(uid_a, TZ)
        svc_b = InstitutionService(uid_b, TZ)

        assert len(svc_a.get_all()) == 2
        assert len(svc_b.get_all()) == 0

    # gap: data
    def test_transactions_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's transactions via get_recent_enriched."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        inst = InstitutionFactory(user_id=uid_a)
        acct = AccountFactory(user_id=uid_a, institution_id=inst.id)
        TransactionFactory(user_id=uid_a, account_id=acct.id)
        TransactionFactory(
            user_id=uid_a, account_id=acct.id, amount=200, balance_delta=-200
        )

        svc_a = TransactionService(uid_a, TZ)
        svc_b = TransactionService(uid_b, TZ)

        assert len(svc_a.get_recent_enriched()) >= 2
        assert len(svc_b.get_recent_enriched()) == 0

    # gap: data
    def test_transaction_by_id_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot fetch User A's transaction by ID."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        inst = InstitutionFactory(user_id=uid_a)
        acct = AccountFactory(user_id=uid_a, institution_id=inst.id)
        tx = TransactionFactory(user_id=uid_a, account_id=acct.id)

        svc_a = TransactionService(uid_a, TZ)
        svc_b = TransactionService(uid_b, TZ)

        assert svc_a.get_by_id(str(tx.id)) is not None
        assert svc_b.get_by_id(str(tx.id)) is None

    # gap: data
    def test_budgets_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's budgets."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        cat = CategoryFactory(user_id=uid_a, name="Food", type="expense")
        BudgetFactory(user_id=uid_a, category_id=cat.id)

        svc_a = BudgetService(uid_a, TZ)
        svc_b = BudgetService(uid_b, TZ)

        assert len(svc_a.get_all_with_spending()) == 1
        assert len(svc_b.get_all_with_spending()) == 0

    # gap: data
    def test_virtual_accounts_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's virtual accounts."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        VirtualAccountFactory(user_id=uid_a, name="Emergency Fund")
        VirtualAccountFactory(user_id=uid_a, name="Vacation")

        svc_a = VirtualAccountService(uid_a)
        svc_b = VirtualAccountService(uid_b)

        assert len(svc_a.get_all()) == 2
        assert len(svc_b.get_all()) == 0

    # gap: data
    def test_virtual_account_by_id_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot fetch User A's virtual account by ID."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        va = VirtualAccountFactory(user_id=uid_a, name="Emergency Fund")

        svc_a = VirtualAccountService(uid_a)
        svc_b = VirtualAccountService(uid_b)

        assert svc_a.get_by_id(str(va.id)) is not None
        assert svc_b.get_by_id(str(va.id)) is None

    # gap: data
    def test_people_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's people."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        PersonFactory(user_id=uid_a, name="Alice")
        PersonFactory(user_id=uid_a, name="Bob")

        svc_a = PersonService(uid_a, TZ)
        svc_b = PersonService(uid_b, TZ)

        assert len(svc_a.get_all()) == 2
        assert len(svc_b.get_all()) == 0

    # gap: data
    def test_person_by_id_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot fetch User A's person by ID."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        person = PersonFactory(user_id=uid_a, name="Alice")

        svc_a = PersonService(uid_a, TZ)
        svc_b = PersonService(uid_b, TZ)

        assert svc_a.get_by_id(str(person.id)) is not None
        assert svc_b.get_by_id(str(person.id)) is None

    # gap: data
    def test_categories_isolated(self, two_users: dict[str, str]) -> None:
        """User B cannot see User A's custom categories."""
        uid_a = two_users["user_a_id"]
        uid_b = two_users["user_b_id"]

        CategoryFactory(user_id=uid_a, name="Custom Cat A", type="expense")
        CategoryFactory(user_id=uid_a, name="Custom Cat B", type="income")

        svc_a = CategoryService(uid_a, TZ)
        svc_b = CategoryService(uid_b, TZ)

        cats_a = svc_a.get_all()
        cats_b = svc_b.get_all()

        # User A sees their custom categories
        custom_a = [c for c in cats_a if c["name"].startswith("Custom Cat")]
        assert len(custom_a) == 2

        # User B sees none of User A's custom categories
        custom_b = [c for c in cats_b if c["name"].startswith("Custom Cat")]
        assert len(custom_b) == 0
