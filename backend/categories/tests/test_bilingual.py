"""Tests for bilingual create/update on CategoryService (#513)."""

from zoneinfo import ZoneInfo

import pytest

from categories.services import CategoryService
from tests.factories import UserFactory


@pytest.fixture
def svc(db):
    user = UserFactory()
    return CategoryService(str(user.id), ZoneInfo("Africa/Cairo"))


@pytest.mark.django_db
class TestCategoryBilingualCreate:
    def test_create_with_both_names(self, svc):
        from categories.models import Category

        cat = svc.create(name_en="Coffee", name_ar="قهوة", cat_type="expense")
        stored = Category.objects.get(id=cat["id"])
        assert stored.name == {"en": "Coffee", "ar": "قهوة"}

    def test_create_with_only_en_autofills_ar(self, svc):
        from categories.models import Category

        cat = svc.create(name_en="Coffee", cat_type="expense")
        stored = Category.objects.get(id=cat["id"])
        assert stored.name == {"en": "Coffee", "ar": "Coffee"}

    def test_create_with_only_ar_autofills_en(self, svc):
        from categories.models import Category

        cat = svc.create(name_ar="قهوة", cat_type="expense")
        stored = Category.objects.get(id=cat["id"])
        assert stored.name == {"en": "قهوة", "ar": "قهوة"}

    def test_create_with_legacy_name_param(self, svc):
        """Existing callers using `name=` still work."""
        from categories.models import Category

        cat = svc.create(name="Coffee", cat_type="expense")
        stored = Category.objects.get(id=cat["id"])
        assert stored.name["en"] == "Coffee"

    def test_create_with_blank_both_raises(self, svc):
        with pytest.raises(ValueError):
            svc.create(name_en="", name_ar="")

    def test_create_with_only_whitespace_raises(self, svc):
        with pytest.raises(ValueError):
            svc.create(name_en="   ", name_ar="")


@pytest.mark.django_db
class TestCategoryBilingualUpdate:
    def test_update_with_both_names(self, svc):
        from categories.models import Category

        cat = svc.create(name_en="X", cat_type="expense")
        updated = svc.update(cat["id"], name_en="Coffee", name_ar="قهوة")
        assert updated is not None
        stored = Category.objects.get(id=cat["id"])
        assert stored.name == {"en": "Coffee", "ar": "قهوة"}

    def test_update_only_ar_keeps_legacy_compat(self, svc):
        from categories.models import Category

        cat = svc.create(name_en="X", cat_type="expense")
        updated = svc.update(cat["id"], name_ar="جديد")
        assert updated is not None
        stored = Category.objects.get(id=cat["id"])
        assert stored.name["ar"] == "جديد"
        assert stored.name["en"] == "جديد"


@pytest.mark.django_db
class TestApiAcceptsBilingualPayload:
    def test_post_with_name_en_and_name_ar(self, client):

        from conftest import SessionFactory, UserFactory, set_auth_cookie

        user = UserFactory()
        session = SessionFactory(user=user)
        c = set_auth_cookie(client, session.token)

        import json

        resp = c.post(
            "/api/categories",
            data=json.dumps(
                {
                    "name_en": "Coffee",
                    "name_ar": "قهوة",
                    "type": "expense",
                    "icon": "☕",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201, resp.content
        from categories.models import Category

        cat = Category.objects.get(user_id=user.id, type="expense")
        assert cat.name == {"en": "Coffee", "ar": "قهوة"}
