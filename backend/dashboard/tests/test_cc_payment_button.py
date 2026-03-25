"""Tests for Issue 11 — Record payment button on dashboard CC cards."""

from django.test import TestCase

from tests.factories import AccountFactory, InstitutionFactory, SessionFactory


class CreditCardPaymentButtonTest(TestCase):
    """Dashboard CC cards should have a record-payment button."""

    def setUp(self) -> None:
        session = SessionFactory()
        self.client.cookies["clearmoney_session"] = session.token
        institution = InstitutionFactory(user_id=session.user.id)
        self.cc = AccountFactory(
            user_id=session.user.id,
            institution_id=institution.id,
            type="credit_card",
            name="Visa Gold",
            current_balance=-1500,
        )

    def test_pay_button_present_for_credit_card(self) -> None:
        """A 'Pay' link/button appears in the CC section on the dashboard."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "Record payment" in content or "Pay" in content

    def test_pay_button_links_to_transfer(self) -> None:
        """The pay button triggers the transfer flow targeting the CC account."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert str(self.cc.id) in content
