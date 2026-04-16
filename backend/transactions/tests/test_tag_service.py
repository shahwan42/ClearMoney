"""Tests for TagService."""

from zoneinfo import ZoneInfo

import pytest

from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)
from transactions.models import Tag
from transactions.services import TagService


@pytest.mark.django_db
class TestTagService:
    def test_create_tag(self):
        user = UserFactory()
        svc = TagService(str(user.id), ZoneInfo("UTC"))
        tag = svc.create("vacation", color="#ff0000")

        assert tag.name == "vacation"
        assert tag.color == "#ff0000"
        assert Tag.objects.filter(user_id=user.id, name="vacation").exists()

    def test_get_all_with_usage(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = TagService(str(user.id), ZoneInfo("UTC"))

        tag1 = svc.create("tag1")
        svc.create("tag2")

        tx = TransactionFactory(user_id=user.id, account_id=account.id)
        tx.tags.add(tag1)

        tags = svc.get_all_with_usage()
        assert len(tags) == 2

        t1 = next(t for t in tags if t["name"] == "tag1")
        t2 = next(t for t in tags if t["name"] == "tag2")

        assert t1["count"] == 1
        assert t2["count"] == 0

    def test_update_tag(self):
        user = UserFactory()
        svc = TagService(str(user.id), ZoneInfo("UTC"))
        tag = svc.create("old-name")

        svc.update(str(tag.id), name="new-name", color="#00ff00")
        tag.refresh_from_db()

        assert tag.name == "new-name"
        assert tag.color == "#00ff00"

    def test_delete_tag(self):
        user = UserFactory()
        svc = TagService(str(user.id), ZoneInfo("UTC"))
        tag = svc.create("to-delete")

        svc.delete(str(tag.id))
        assert not Tag.objects.filter(id=tag.id).exists()

    def test_merge_tags(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = TagService(str(user.id), ZoneInfo("UTC"))

        source = svc.create("source")
        target = svc.create("target")

        tx = TransactionFactory(user_id=user.id, account_id=account.id)
        tx.tags.add(source)

        svc.merge(str(source.id), str(target.id))

        assert not Tag.objects.filter(id=source.id).exists()
        tx.refresh_from_db()
        assert target in tx.tags.all()
        assert source not in tx.tags.all()
