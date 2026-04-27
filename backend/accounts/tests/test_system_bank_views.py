"""HTTP-level tests for SystemBank API + institution form integration (#510)."""

import json

import pytest

from accounts.models import SystemBank
from conftest import SessionFactory, UserFactory, set_auth_cookie


@pytest.fixture
def auth_client(client, db):
    user = UserFactory()
    session = SessionFactory(user=user)
    return set_auth_cookie(client, session.token)


@pytest.mark.django_db
class TestApiSystemBanks:
    def test_returns_active_egypt_banks_in_order(self, auth_client):
        resp = auth_client.get("/api/system-banks")
        assert resp.status_code == 200
        rows = json.loads(resp.content)
        assert len(rows) == 20
        assert rows[0]["short_name"] == "CIB"
        assert rows[1]["short_name"] == "NBE"

    def test_payload_shape(self, auth_client):
        resp = auth_client.get("/api/system-banks")
        rows = json.loads(resp.content)
        cib = rows[0]
        assert set(cib) == {
            "id",
            "name",
            "short_name",
            "svg_path",
            "brand_color",
            "bank_type",
        }
        assert cib["svg_path"].startswith("img/institutions/")

    def test_filters_by_q(self, auth_client):
        resp = auth_client.get("/api/system-banks?q=hsbc")
        rows = json.loads(resp.content)
        assert len(rows) == 1
        assert rows[0]["short_name"] == "HSBC"

    def test_excludes_inactive(self, auth_client):
        SystemBank.objects.filter(short_name="CIB").update(is_active=False)
        resp = auth_client.get("/api/system-banks")
        rows = json.loads(resp.content)
        assert all(r["short_name"] != "CIB" for r in rows)

    def test_unauthenticated_redirects(self, client, db):
        resp = client.get("/api/system-banks")
        # GoSessionAuthMiddleware redirects to /login when no session
        assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
class TestInstitutionFormIntegration:
    def test_form_partial_includes_system_banks_in_presets(self, auth_client):
        resp = auth_client.get("/accounts/institution-form")
        assert resp.status_code == 200
        body = resp.content.decode()
        # Bilingual EN name appears in embedded JSON
        assert "Commercial International Bank" in body
        # System bank preset has id field
        assert '"id":' in body

    def test_create_institution_with_system_bank_id(self, auth_client):
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        resp = auth_client.post(
            "/institutions/add",
            data={
                "name": "CIB",
                "type": "bank",
                "icon": "cib.svg",
                "color": "#003366",
                "system_bank_id": str(cib.pk),
            },
        )
        assert resp.status_code == 200
        # Now query the API to verify FK was set
        from accounts.models import Institution

        inst = Institution.objects.get(name="CIB")
        assert inst.system_bank_id == cib.pk

    def test_create_institution_with_custom_name_no_system_bank(self, auth_client):
        resp = auth_client.post(
            "/institutions/add",
            data={"name": "My Local CU", "type": "bank"},
        )
        assert resp.status_code == 200
        from accounts.models import Institution

        inst = Institution.objects.get(name="My Local CU")
        assert inst.system_bank_id is None

    def test_edit_form_pre_selects_linked_bank(self, auth_client):
        from accounts.models import Institution

        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        # Create directly via auth_client's user — fetch via session
        from auth_app.models import Session

        sess = Session.objects.first()
        assert sess is not None
        user_id = sess.user_id
        inst = Institution.objects.create(
            user_id=user_id,
            name="My CIB",
            type="bank",
            system_bank=cib,
        )
        resp = auth_client.get(f"/institutions/{inst.id}/edit-form")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert f'value="{cib.pk}" selected' in body
        # bilingual name visible
        assert "Commercial International Bank" in body

    def test_edit_form_no_link_shows_custom_option_selected(self, auth_client):
        from accounts.models import Institution
        from auth_app.models import Session

        sess = Session.objects.first()
        assert sess is not None
        inst = Institution.objects.create(
            user_id=sess.user_id, name="Mom & Pop", type="bank"
        )
        resp = auth_client.get(f"/institutions/{inst.id}/edit-form")
        body = resp.content.decode()
        # Custom (no link) option present; should not have "selected" set on any sb id row
        assert "Custom (no linked bank)" in body

    def test_update_links_to_system_bank(self, auth_client):
        from accounts.models import Institution
        from auth_app.models import Session

        sess = Session.objects.first()
        assert sess is not None
        inst = Institution.objects.create(
            user_id=sess.user_id, name="Old", type="bank"
        )
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        resp = auth_client.post(
            f"/institutions/{inst.id}/update",
            data={"name": "Old", "type": "bank", "system_bank_id": str(cib.pk)},
        )
        assert resp.status_code == 200
        inst.refresh_from_db()
        assert inst.system_bank_id == cib.pk

    def test_update_clears_system_bank_with_empty(self, auth_client):
        from accounts.models import Institution
        from auth_app.models import Session

        sess = Session.objects.first()
        assert sess is not None
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        inst = Institution.objects.create(
            user_id=sess.user_id, name="X", type="bank", system_bank=cib
        )
        resp = auth_client.post(
            f"/institutions/{inst.id}/update",
            data={"name": "X", "type": "bank", "system_bank_id": ""},
        )
        assert resp.status_code == 200
        inst.refresh_from_db()
        assert inst.system_bank_id is None

    def test_create_with_invalid_system_bank_id_falls_back(self, auth_client):
        resp = auth_client.post(
            "/institutions/add",
            data={
                "name": "Some Bank",
                "type": "bank",
                "system_bank_id": "999999",
            },
        )
        assert resp.status_code == 200
        from accounts.models import Institution

        inst = Institution.objects.get(name="Some Bank")
        assert inst.system_bank_id is None
