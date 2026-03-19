"""
CategoryService unit tests — business logic for category CRUD.

Tests run against real PostgreSQL (--reuse-db).
"""

import uuid

import pytest
from django.db import connection

from categories.services import CategoryService
from conftest import SessionFactory, UserFactory
from core.models import Session, User

_TZ = __import__("zoneinfo").ZoneInfo("Africa/Cairo")


@pytest.fixture
def cat_svc(db):
    """CategoryService + user with seeded categories."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    # Seed a system category + a custom category
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO categories (user_id, name, type, icon, is_system, display_order) "
            "VALUES (%s, 'Groceries', 'expense', '🛒', true, 1)",
            [user_id],
        )
        cursor.execute(
            "INSERT INTO categories (user_id, name, type, icon, is_system, display_order) "
            "VALUES (%s, 'Salary', 'income', '💵', true, 1)",
            [user_id],
        )

    svc = CategoryService(user_id, _TZ)
    yield svc, user_id

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user.id).delete()
    User.objects.filter(id=user.id).delete()


@pytest.mark.django_db
class TestCategoryServiceGetAll:
    def test_returns_non_archived(self, cat_svc):
        svc, _ = cat_svc
        cats = svc.get_all()
        assert len(cats) >= 2
        assert all(not c["is_archived"] for c in cats)

    def test_sorted_by_type_then_display_order(self, cat_svc):
        svc, _ = cat_svc
        cats = svc.get_all()
        types = [c["type"] for c in cats]
        assert types == sorted(types)


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
        cat = svc.create("Custom Cat", "expense", icon="🎯")
        assert cat["name"] == "Custom Cat"
        assert cat["type"] == "expense"
        assert cat["icon"] == "🎯"
        assert cat["is_system"] is False
        assert cat["user_id"] == user_id

    def test_create_invalid_type(self, cat_svc):
        svc, _ = cat_svc
        with pytest.raises(ValueError, match="expense.*income"):
            svc.create("Bad Type", "invalid")

    def test_create_empty_name(self, cat_svc):
        svc, _ = cat_svc
        with pytest.raises(ValueError, match="required"):
            svc.create("", "expense")


@pytest.mark.django_db
class TestCategoryServiceUpdate:
    def test_update_custom(self, cat_svc):
        svc, _ = cat_svc
        created = svc.create("ToUpdate", "expense")
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
        created = svc.create("ToArchive", "expense")
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
