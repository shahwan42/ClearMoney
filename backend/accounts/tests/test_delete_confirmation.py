"""Tests for case-insensitive delete confirmation in account and institution templates."""

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from tests.factories import AccountFactory, InstitutionFactory


@pytest.mark.django_db
class TestAccountDeleteConfirmCaseInsensitive:
    """Account delete confirmation must be case-insensitive."""

    def test_account_detail_has_case_insensitive_check(self) -> None:
        """The JS checkDeleteConfirmation uses toLowerCase() for comparison."""
        user = UserFactory()
        session = SessionFactory(user=user)
        client = Client()
        set_auth_cookie(client, session.token)
        inst = InstitutionFactory(user_id=str(user.id))
        acct = AccountFactory(
            user_id=str(user.id), institution_id=inst.id, name="My Savings"
        )
        response = client.get(f"/accounts/{acct.id}")
        content = response.content.decode()
        assert "toLowerCase()" in content


@pytest.mark.django_db
class TestInstitutionDeleteConfirmCaseInsensitive:
    """Institution delete confirmation must be case-insensitive."""

    def test_institution_delete_confirm_has_case_insensitive_check(self) -> None:
        """The JS checkDeleteConfirm uses toLowerCase() for comparison."""
        user = UserFactory()
        session = SessionFactory(user=user)
        client = Client()
        set_auth_cookie(client, session.token)
        inst = InstitutionFactory(user_id=str(user.id), name="Test Bank")
        AccountFactory(user_id=str(user.id), institution_id=inst.id)
        response = client.get(f"/institutions/{inst.id}/delete-confirm")
        content = response.content.decode()
        assert "toLowerCase()" in content
