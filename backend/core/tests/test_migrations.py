"""Tests for data migrations."""

import importlib

import pytest

from categories.models import Category
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)

_mod = importlib.import_module("core.migrations.0007_add_system_categories")
add_system_categories = _mod.add_system_categories

pytestmark = pytest.mark.django_db

NEW_NAMES = ["Travel", "Cafe", "Restaurant", "Car"]


class TestAddSystemCategoriesMigration:
    """Data migration adds Travel, Cafe, Restaurant, Car to all users."""

    def test_adds_categories_to_existing_user(self) -> None:
        user = UserFactory()
        add_system_categories(None, None)
        cats = Category.objects.filter(user_id=user.id, name__en__in=NEW_NAMES)
        assert cats.count() == 4
        for cat in cats:
            assert cat.is_system is True
            assert cat.is_archived is False

    def test_idempotent(self) -> None:
        user = UserFactory()
        add_system_categories(None, None)
        add_system_categories(None, None)
        assert Category.objects.filter(user_id=user.id, name__en="Travel").count() == 1

    def test_correct_icons(self) -> None:
        user = UserFactory()
        add_system_categories(None, None)
        assert Category.objects.get(user_id=user.id, name__en="Travel").icon == "✈️"
        assert Category.objects.get(user_id=user.id, name__en="Cafe").icon == "☕"
        assert Category.objects.get(user_id=user.id, name__en="Restaurant").icon == "🍽️"
        assert Category.objects.get(user_id=user.id, name__en="Car").icon == "🚙"

    def test_multiple_users(self) -> None:
        user1 = UserFactory()
        user2 = UserFactory()
        add_system_categories(None, None)
        assert Category.objects.filter(user_id=user1.id, name__en="Travel").count() == 1
        assert Category.objects.filter(user_id=user2.id, name__en="Travel").count() == 1

    def test_skips_existing_same_name(self) -> None:
        """If user already has a custom 'Travel' category, don't duplicate."""
        user = UserFactory()
        CategoryFactory(
            user_id=user.id, name={"en": "Travel"}, icon="🧳", is_system=False
        )
        add_system_categories(None, None)
        assert (
            Category.objects.filter(user_id=user.id, name__en__iexact="travel").count()
            == 1
        )

    def test_existing_transactions_unaffected(self) -> None:
        user = UserFactory()
        cat = CategoryFactory(user_id=user.id, name={"en": "Food"})
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        tx = TransactionFactory(user_id=user.id, account_id=account.id, category=cat)
        add_system_categories(None, None)
        tx.refresh_from_db()
        assert tx.category_id == cat.id
