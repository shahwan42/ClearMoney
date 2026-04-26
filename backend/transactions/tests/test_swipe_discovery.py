"""Tests for transaction history deletion affordances."""

from django.test import TestCase

from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    SessionFactory,
    TransactionFactory,
)


class TransactionHistoryDeleteAffordanceTest(TestCase):
    """Transaction rows should expose explicit deletion without swipe affordances."""

    def setUp(self) -> None:
        session = SessionFactory()
        self.client.cookies["clearmoney_session"] = session.token
        institution = InstitutionFactory(user_id=session.user.id)
        self.account = AccountFactory(
            user_id=session.user.id, institution_id=institution.id
        )
        TransactionFactory(user_id=session.user.id, account_id=self.account.id)

    def test_transaction_row_has_no_swipe_delete_attr(self) -> None:
        """Transaction rows on the list page do not include data-swipe-delete."""
        resp = self.client.get("/transactions")
        content = resp.content.decode()
        assert "data-swipe-delete" not in content

    def test_swipe_hint_text_absent(self) -> None:
        """The transactions page does not render the removed swipe hint."""
        resp = self.client.get("/transactions")
        content = resp.content.decode()
        assert "swipe-hint" not in content
        assert "Swipe left on a transaction to delete" not in content

    def test_explicit_delete_control_remains_available(self) -> None:
        """History rows still include the explicit menu delete control."""
        resp = self.client.get("/transactions")
        content = resp.content.decode()
        assert 'hx-delete="/transactions/' in content
        assert "Delete this transaction?" in content

    def test_dashboard_rows_no_swipe_delete(self) -> None:
        """Dashboard compact rows should NOT have data-swipe-delete."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "data-swipe-delete" not in content
