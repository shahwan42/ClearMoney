"""Tests for Django Admin setup — registration, middleware bypass, access control."""

import pytest
from django.contrib import admin
from django.contrib.auth.models import User as DjangoUser
from django.test import Client

from core.middleware import PUBLIC_PATHS


class TestAdminMiddlewareBypass:
    def test_admin_in_public_paths(self) -> None:
        assert "/admin" in PUBLIC_PATHS

    @pytest.mark.django_db
    def test_admin_not_intercepted_by_magic_link_middleware(self) -> None:
        # Unauthenticated /admin → Django admin login (not magic link /login)
        client = Client()
        response = client.get("/admin/", follow=False)
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]


class TestAdminAccess:
    @pytest.mark.django_db
    def test_regular_user_redirected_to_admin_login_not_magic_link(self) -> None:
        user = DjangoUser.objects.create_user(
            username="regular",
            email="regular@test.com",
            password="testpass123",
        )
        client = Client()
        client.force_login(user)
        response = client.get("/admin/", follow=False)
        # Non-staff user is redirected (to /admin/login/), not magic link /login
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]


class TestAdminModelRegistration:
    def test_all_expected_models_registered(self) -> None:
        registered = {f"{m._meta.app_label}.{m.__name__}" for m in admin.site._registry}
        expected = [
            "auth_app.User",
            "auth_app.Session",
            "auth_app.AuthToken",
            "auth_app.DailySnapshot",
            "accounts.Institution",
            "accounts.Account",
            "transactions.Transaction",
            "categories.Category",
            "budgets.Budget",
            "people.Person",
            "virtual_accounts.VirtualAccount",
            "recurring.RecurringRule",
            "investments.Investment",
            "exchange_rates.ExchangeRateLog",
        ]
        for model_label in expected:
            assert model_label in registered, f"{model_label} not registered in admin"

    def test_admin_site_branding(self) -> None:
        assert admin.site.site_header == "ClearMoney Admin"
        assert admin.site.site_title == "ClearMoney"
        assert admin.site.index_title == "Dashboard"
