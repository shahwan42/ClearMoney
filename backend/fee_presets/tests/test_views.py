"""Tests for fee preset views."""

import pytest
from django.test import Client

from fee_presets.models import FeePreset
from tests.factories import FeePresetFactory, UserFactory


@pytest.mark.django_db
class TestFeePresetsPage:
    def test_renders_200(self, auth_client: Client) -> None:
        response = auth_client.get("/settings/fee-presets")
        assert response.status_code == 200

    def test_shows_presets(self, auth_client: Client, auth_user: tuple) -> None:
        user_id, _, _ = auth_user
        FeePresetFactory(user_id=user_id, name="InstaPay", currency="EGP")
        FeePresetFactory(user_id=user_id, name="ATM", currency="EGP")

        response = auth_client.get("/settings/fee-presets")
        assert response.status_code == 200
        assert b"InstaPay" in response.content
        assert b"ATM" in response.content

    def test_shows_currency_tabs(self, auth_client: Client, auth_user: tuple) -> None:
        user_id, _, _ = auth_user
        FeePresetFactory(user_id=user_id, name="ATM", currency="EGP")
        FeePresetFactory(user_id=user_id, name="Wire", currency="USD")

        response = auth_client.get("/settings/fee-presets")
        assert response.status_code == 200
        assert b"EGP" in response.content
        assert b"USD" in response.content

    def test_only_shows_own_presets(
        self, auth_client: Client, auth_user: tuple
    ) -> None:
        user_id, _, _ = auth_user
        other_user = UserFactory()
        FeePresetFactory(user_id=user_id, name="My Preset", currency="EGP")
        FeePresetFactory(
            user_id=str(other_user.id), name="Other Preset", currency="EGP"
        )

        response = auth_client.get("/settings/fee-presets")
        assert response.status_code == 200
        assert b"My Preset" in response.content
        assert b"Other Preset" not in response.content


@pytest.mark.django_db
class TestFeePresetAdd:
    def test_can_create_flat_preset(self, auth_client: Client) -> None:
        response = auth_client.post(
            "/settings/fee-presets/add",
            {
                "name": "Test ATM",
                "currency": "EGP",
                "calc_type": "flat",
                "value": "5.00",
            },
        )
        assert response.status_code == 302  # Redirect after success

        # Verify created
        preset = FeePreset.objects.filter(name="Test ATM").first()
        assert preset is not None
        assert preset.calc_type == "flat"
        assert preset.value == 5

    def test_can_create_percent_preset(self, auth_client: Client) -> None:
        response = auth_client.post(
            "/settings/fee-presets/add",
            {
                "name": "Test Percent",
                "currency": "EGP",
                "calc_type": "percent",
                "value": "0.001",
                "min_fee": "0.50",
                "max_fee": "20.00",
            },
        )
        assert response.status_code == 302

        preset = FeePreset.objects.filter(name="Test Percent").first()
        assert preset is not None
        assert preset.calc_type == "percent"
        assert preset.min_fee == 0.5
        assert preset.max_fee == 20

    def test_validation_error_returns_400(self, auth_client: Client) -> None:
        response = auth_client.post(
            "/settings/fee-presets/add",
            {
                "name": "Test",
                "currency": "EGP",
                "calc_type": "flat",
                "value": "0",  # Invalid: must be > 0
            },
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestFeePresetArchive:
    def test_can_archive_preset(self, auth_client: Client, auth_user: tuple) -> None:
        user_id, _, _ = auth_user
        preset = FeePresetFactory(user_id=user_id, name="To Archive", currency="EGP")

        response = auth_client.post(f"/settings/fee-presets/{preset.id}/archive")
        assert response.status_code == 302

        preset.refresh_from_db()
        assert preset.archived is True

    def test_can_unarchive_preset(self, auth_client: Client, auth_user: tuple) -> None:
        user_id, _, _ = auth_user
        preset = FeePresetFactory(
            user_id=user_id, name="To Unarchive", currency="EGP", archived=True
        )

        response = auth_client.post(f"/settings/fee-presets/{preset.id}/unarchive")
        assert response.status_code == 302

        preset.refresh_from_db()
        assert preset.archived is False


@pytest.mark.django_db
class TestApiFeePresets:
    def test_api_returns_presets_for_currency(
        self, auth_client: Client, auth_user: tuple
    ) -> None:
        user_id, _, _ = auth_user
        FeePresetFactory(user_id=user_id, name="EGP Fee", currency="EGP")
        FeePresetFactory(user_id=user_id, name="USD Fee", currency="USD")

        response = auth_client.get("/api/fee-presets?currency=EGP")
        assert response.status_code == 200

        data = response.json()
        assert len(data["presets"]) == 1
        assert data["presets"][0]["name"] == "EGP Fee"

    def test_api_only_returns_active_presets(
        self, auth_client: Client, auth_user: tuple
    ) -> None:
        user_id, _, _ = auth_user
        FeePresetFactory(user_id=user_id, name="Active", currency="EGP", archived=False)
        FeePresetFactory(
            user_id=user_id, name="Archived", currency="EGP", archived=True
        )

        response = auth_client.get("/api/fee-presets?currency=EGP")
        data = response.json()

        names = {p["name"] for p in data["presets"]}
        assert "Active" in names
        assert "Archived" not in names


@pytest.mark.django_db
class TestApiFeePresetCalculate:
    def test_calculates_flat_fee(self, auth_client: Client, auth_user: tuple) -> None:
        user_id, _, _ = auth_user
        preset = FeePresetFactory(
            user_id=user_id, name="Flat", currency="EGP", calc_type="flat", value="5"
        )

        response = auth_client.get(
            f"/api/fee-presets/calculate?preset_id={preset.id}&amount=1000"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["fee"] == "5.00"

    def test_calculates_percent_fee(
        self, auth_client: Client, auth_user: tuple
    ) -> None:
        user_id, _, _ = auth_user
        preset = FeePresetFactory(
            user_id=user_id,
            name="Percent",
            currency="EGP",
            calc_type="percent",
            value="0.001",  # 0.1%
            min_fee="0.50",
            max_fee="20.00",
        )

        response = auth_client.get(
            f"/api/fee-presets/calculate?preset_id={preset.id}&amount=5000"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["fee"] == "5.00"  # 0.1% of 5000 = 5

    def test_requires_preset_id(self, auth_client: Client) -> None:
        response = auth_client.get("/api/fee-presets/calculate?amount=100")
        assert response.status_code == 400
        assert "error" in response.json()
