"""Tests for reports views (HTTP layer)."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestReportsPage:
    def test_renders_200(self, auth_client: Client) -> None:
        response = auth_client.get("/reports")
        assert response.status_code == 200

    def test_accepts_year_month_params(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?year=2026&month=1")
        assert response.status_code == 200

    def test_accepts_currency_filter(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?currency=EGP")
        assert response.status_code == 200

    def test_invalid_year_defaults_gracefully(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?year=abc")
        assert response.status_code == 200

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/reports")
        assert response.status_code == 302
