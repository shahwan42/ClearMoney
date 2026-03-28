"""Tests for two-step delete confirmation in account and institution templates."""

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from tests.factories import AccountFactory, InstitutionFactory


@pytest.mark.django_db
class TestAccountDeleteTwoStepConfirm:
    """Account delete uses two-step button confirmation (no typing needed)."""

    def test_account_detail_has_two_step_delete_button(self) -> None:
        """Delete button exists and is not disabled (no text input gate)."""
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
        # Button should NOT be disabled — first click arms it via JS
        assert 'id="delete-confirm-btn"' in content
        assert (
            "disabled" not in content.split('id="delete-confirm-btn"')[1].split(">")[0]
        )
        # Two-step JS pattern present
        assert "Tap again to confirm" in content
        assert "deleteArmed" in content

    def test_account_detail_has_no_text_input(self) -> None:
        """No text input for typing account name — removed in favor of two-step."""
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
        assert 'id="delete-confirm-input"' not in content


@pytest.mark.django_db
class TestInstitutionDeleteTwoStepConfirm:
    """Institution delete uses two-step button confirmation (no typing needed)."""

    def test_institution_delete_confirm_has_two_step_button(self) -> None:
        """Delete button exists and is not disabled."""
        user = UserFactory()
        session = SessionFactory(user=user)
        client = Client()
        set_auth_cookie(client, session.token)
        inst = InstitutionFactory(user_id=str(user.id), name="Test Bank")
        AccountFactory(user_id=str(user.id), institution_id=inst.id)
        response = client.get(f"/institutions/{inst.id}/delete-confirm")
        content = response.content.decode()
        assert 'id="delete-confirm-btn"' in content
        assert (
            "disabled" not in content.split('id="delete-confirm-btn"')[1].split(">")[0]
        )
        assert "Tap again to confirm" in content
        assert "instDeleteArmed" in content

    def test_institution_delete_confirm_has_no_text_input(self) -> None:
        """No text input for typing institution name."""
        user = UserFactory()
        session = SessionFactory(user=user)
        client = Client()
        set_auth_cookie(client, session.token)
        inst = InstitutionFactory(user_id=str(user.id), name="Test Bank")
        AccountFactory(user_id=str(user.id), institution_id=inst.id)
        response = client.get(f"/institutions/{inst.id}/delete-confirm")
        content = response.content.decode()
        assert 'id="delete-confirm-input"' not in content
