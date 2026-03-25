"""
CategoryService unit tests — business logic for category CRUD.

Tests run against real PostgreSQL (--reuse-db).
"""

import uuid

import pytest

from categories.services import CategoryService
from conftest import SessionFactory, UserFactory
from tests.factories import CategoryFactory

_TZ = __import__("zoneinfo").ZoneInfo("Africa/Cairo")


@pytest.fixture
def cat_svc(db):
    """CategoryService + user with seeded categories."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    # Seed a system category + a custom category
    CategoryFactory(
        user_id=user.id,
        name="Groceries",
        type="expense",
        icon="🛒",
        is_system=True,
        display_order=1,
    )
    CategoryFactory(
        user_id=user.id,
        name="Salary",
        type="income",
        icon="💵",
        is_system=True,
        display_order=1,
    )

    svc = CategoryService(user_id, _TZ)
    yield svc, user_id


@pytest.mark.django_db
class TestCategoryServiceGetAll:
    def test_returns_non_archived(self, cat_svc):
        svc, _ = cat_svc
        cats = svc.get_all()
        assert len(cats) >= 2
        assert all(not c["is_archived"] for c in cats)

    def test_sorted_by_display_order_then_name(self, cat_svc):
        """Categories ordered by display_order then name (no type grouping)."""
        svc, user_id = cat_svc
        CategoryFactory(
            user_id=user_id,
            name="Zebra",
            type="expense",
            display_order=2,
        )
        CategoryFactory(
            user_id=user_id,
            name="Alpha",
            type="expense",
            display_order=1,
        )
        cats = svc.get_all()
        orders = [c["display_order"] for c in cats]
        # display_order should be non-decreasing
        assert orders == sorted(orders)

    def test_returns_all_types_together(self, cat_svc):
        """get_all returns expense and income categories in a flat list."""
        svc, _ = cat_svc
        cats = svc.get_all()
        names = [c["name"] for c in cats]
        assert "Groceries" in names
        assert "Salary" in names


@pytest.mark.django_db
class TestCategoryServiceGetByType:
    def test_filter_expense(self, cat_svc):
        svc, _ = cat_svc
        expense_cats = svc.get_by_type("expense")
        assert all(c["type"] == "expense" for c in expense_cats)

    def test_filter_income(self, cat_svc):
        svc, _ = cat_svc
        income_cats = svc.get_by_type("income")
        assert all(c["type"] == "income" for c in income_cats)


@pytest.mark.django_db
class TestCategoryServiceCreate:
    def test_create_custom(self, cat_svc):
        svc, user_id = cat_svc
        cat = svc.create("Custom Cat", icon="🎯")
        assert cat["name"] == "Custom Cat"
        assert cat["type"] == "expense"  # default
        assert cat["icon"] == "🎯"
        assert cat["is_system"] is False
        assert cat["user_id"] == user_id

    def test_create_with_type_still_works(self, cat_svc):
        """Backward compat: type param accepted."""
        svc, _ = cat_svc
        cat = svc.create("Bonus", cat_type="income", icon="💰")
        assert cat["name"] == "Bonus"
        assert cat["type"] == "expense"  # always stored as expense

    def test_create_empty_name(self, cat_svc):
        svc, _ = cat_svc
        with pytest.raises(ValueError, match="required"):
            svc.create("")

    def test_create_duplicate_name_rejected(self, cat_svc):
        svc, _ = cat_svc
        svc.create("Coffee", icon="☕")
        with pytest.raises(ValueError, match="already exists"):
            svc.create("coffee", icon="☕")  # case-insensitive match


@pytest.mark.django_db
class TestCategoryServiceUpdate:
    def test_update_custom(self, cat_svc):
        svc, _ = cat_svc
        created = svc.create("ToUpdate")
        updated = svc.update(created["id"], "Updated Name", icon="✏️")
        assert updated is not None
        assert updated["name"] == "Updated Name"
        assert updated["icon"] == "✏️"

    def test_cannot_update_system(self, cat_svc):
        svc, _ = cat_svc
        cats = svc.get_all()
        system_cat = next(c for c in cats if c["is_system"])
        with pytest.raises(ValueError, match="system"):
            svc.update(system_cat["id"], "New Name")

    def test_update_not_found(self, cat_svc):
        svc, _ = cat_svc
        result = svc.update(str(uuid.uuid4()), "NoExist")
        assert result is None


@pytest.mark.django_db
class TestCategoryServiceArchive:
    def test_archive_custom(self, cat_svc):
        svc, _ = cat_svc
        created = svc.create("ToArchive")
        assert svc.archive(created["id"]) is True
        # Should no longer appear in get_all
        cats = svc.get_all()
        assert all(c["id"] != created["id"] for c in cats)

    def test_cannot_archive_system(self, cat_svc):
        svc, _ = cat_svc
        cats = svc.get_all()
        system_cat = next(c for c in cats if c["is_system"])
        with pytest.raises(ValueError, match="system"):
            svc.archive(system_cat["id"])

    def test_archive_not_found(self, cat_svc):
        svc, _ = cat_svc
        with pytest.raises(ValueError, match="not found"):
            svc.archive(str(uuid.uuid4()))
