"""Tests for the Notification model — creation, constraints, manager, ordering."""

import pytest
from django.db import IntegrityError

from push.models import Notification
from tests.factories import UserFactory


@pytest.mark.django_db
class TestNotificationModel:
    def test_create_notification(self) -> None:
        user = UserFactory()
        notif = Notification.objects.create(
            user=user,
            title="Test Title",
            body="Test body",
            url="/accounts",
            tag="test-tag-1",
        )
        assert notif.id is not None
        assert notif.title == "Test Title"
        assert notif.is_read is False
        assert notif.created_at is not None

    def test_unique_constraint_user_tag(self) -> None:
        user = UserFactory()
        Notification.objects.create(user=user, title="A", body="B", tag="dup-tag")
        with pytest.raises(IntegrityError):
            Notification.objects.create(user=user, title="C", body="D", tag="dup-tag")

    def test_same_tag_different_users_allowed(self) -> None:
        user1 = UserFactory()
        user2 = UserFactory()
        Notification.objects.create(user=user1, title="A", body="B", tag="shared-tag")
        # Should not raise
        Notification.objects.create(user=user2, title="C", body="D", tag="shared-tag")
        assert Notification.objects.for_user(str(user1.id)).count() == 1
        assert Notification.objects.for_user(str(user2.id)).count() == 1

    def test_for_user_scoping(self) -> None:
        user1 = UserFactory()
        user2 = UserFactory()
        Notification.objects.create(user=user1, title="A", body="B", tag="tag-1")
        Notification.objects.create(user=user2, title="C", body="D", tag="tag-2")
        assert Notification.objects.for_user(str(user1.id)).count() == 1
        assert Notification.objects.for_user(str(user2.id)).count() == 1

    def test_ordering_newest_first(self) -> None:
        user = UserFactory()
        n1 = Notification.objects.create(user=user, title="A", body="B", tag="tag-a")
        n2 = Notification.objects.create(user=user, title="C", body="D", tag="tag-b")
        qs = list(Notification.objects.for_user(str(user.id)))
        assert qs[0].id == n2.id
        assert qs[1].id == n1.id

    def test_str_representation(self) -> None:
        user = UserFactory()
        notif = Notification.objects.create(
            user=user, title="Budget Alert", body="Over budget", tag="budget-1"
        )
        assert "Budget Alert" in str(notif)
        assert "unread" in str(notif)
        notif.is_read = True
        notif.save()
        assert "read" in str(notif)
