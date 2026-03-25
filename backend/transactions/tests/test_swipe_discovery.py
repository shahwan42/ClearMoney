"""Tests for Issue 09 — Swipe-to-delete discovery: attribute + hint text."""

from django.test import TestCase

from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    SessionFactory,
    TransactionFactory,
)


class SwipeDeleteDiscoveryTest(TestCase):
    """Transaction rows should have data-swipe-delete attribute and hint text."""

    def setUp(self) -> None:
        session = SessionFactory()
        self.client.cookies["clearmoney_session"] = session.token
        institution = InstitutionFactory(user_id=session.user.id)
        self.account = AccountFactory(
            user_id=session.user.id, institution_id=institution.id
        )
        TransactionFactory(user_id=session.user.id, account_id=self.account.id)

    def test_transaction_row_has_swipe_delete_attr(self) -> None:
        """Transaction rows on the list page include data-swipe-delete."""
        resp = self.client.get("/transactions")
        content = resp.content.decode()
        assert "data-swipe-delete" in content

    def test_swipe_hint_text_present(self) -> None:
        """A swipe hint element is rendered on the transactions page."""
        resp = self.client.get("/transactions")
        content = resp.content.decode()
        assert "swipe-hint" in content

    def test_dashboard_rows_no_swipe_delete(self) -> None:
        """Dashboard compact rows should NOT have data-swipe-delete."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "data-swipe-delete" not in content
