"""Tests for Institution.system_bank FK + display resolution (#509)."""

from zoneinfo import ZoneInfo

import pytest

from accounts.models import Institution, SystemBank
from accounts.services import InstitutionService
from tests.factories import UserFactory


@pytest.mark.django_db
class TestInstitutionSystemBankLink:
    tz = ZoneInfo("Africa/Cairo")

    def test_create_with_system_bank_links_fk(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("CIB", "bank", system_bank_id=cib.pk)
        assert inst["system_bank_id"] == cib.pk
        assert inst["system_bank_short_name"] == "CIB"

    def test_create_without_system_bank_keeps_fk_null(self):
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("My Custom Bank", "bank")
        assert inst["system_bank_id"] is None

    def test_create_invalid_system_bank_id_falls_back_to_null(self):
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("X", "bank", system_bank_id=999999)
        assert inst["system_bank_id"] is None

    def test_dict_resolves_bilingual_name_from_system_bank(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        svc.create("ignored-typed-name", "bank", system_bank_id=cib.pk)
        rows = svc.get_all()
        assert len(rows) == 1
        # default lang is "en-us" in tests
        assert rows[0]["name"] == "Commercial International Bank"

    def test_dict_resolves_icon_from_system_bank(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        svc.create("CIB", "bank", system_bank_id=cib.pk)
        rows = svc.get_all()
        assert rows[0]["icon"] == "cib.svg"
        assert rows[0]["color"] == "#003366"

    def test_unlinked_institution_uses_own_fields(self):
        user = UserFactory()
        svc = InstitutionService(str(user.id), self.tz)
        svc.create("My Bank", "bank", icon="custom.svg", color="#abcdef")
        rows = svc.get_all()
        assert rows[0]["name"] == "My Bank"
        assert rows[0]["icon"] == "custom.svg"
        assert rows[0]["color"] == "#abcdef"
        assert rows[0]["system_bank_id"] is None

    def test_update_links_system_bank(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("My Bank", "bank")
        updated = svc.update(inst["id"], "Linked", "bank", system_bank_id=cib.pk)
        assert updated is not None
        assert updated["system_bank_id"] == cib.pk

    def test_update_clears_system_bank_with_none(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("CIB", "bank", system_bank_id=cib.pk)
        updated = svc.update(inst["id"], "Reverted", "bank", system_bank_id=None)
        assert updated is not None
        assert updated["system_bank_id"] is None
        assert updated["name"] == "Reverted"

    def test_update_clears_system_bank_with_empty_string(self):
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("CIB", "bank", system_bank_id=cib.pk)
        updated = svc.update(inst["id"], "X", "bank", system_bank_id="")
        assert updated is not None
        assert updated["system_bank_id"] is None

    def test_update_without_system_bank_arg_preserves_link(self):
        """Omitting system_bank_id leaves the existing FK untouched."""
        user = UserFactory()
        cib = SystemBank.objects.get(short_name="CIB", country="EG")
        svc = InstitutionService(str(user.id), self.tz)
        inst = svc.create("CIB", "bank", system_bank_id=cib.pk)
        updated = svc.update(inst["id"], "Renamed only", "bank")
        assert updated is not None
        assert updated["system_bank_id"] == cib.pk

    def test_system_bank_set_null_on_bank_delete(self):
        """on_delete=SET_NULL: deleting system bank does not cascade to institutions."""
        user = UserFactory()
        sb = SystemBank.objects.create(
            name={"en": "Throwaway"}, short_name="TMP", country="EG"
        )
        svc = InstitutionService(str(user.id), self.tz)
        inst_dict = svc.create("TMP", "bank", system_bank_id=sb.pk)
        inst_id = inst_dict["id"]
        sb.delete()
        # Institution still exists, FK is null
        inst = Institution.objects.get(id=inst_id)
        assert inst.system_bank_id is None
