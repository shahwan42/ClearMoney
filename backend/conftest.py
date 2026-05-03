"""
Root conftest.py — shared pytest fixtures for all Django test files.

Provides:
- auth_user fixture: creates a test user + valid session, yields (user_id, email, token)
- auth_cookie fixture: returns the HTTP_COOKIE kwarg dict for Django test client calls
- auth_client fixture: returns an authenticated Django test client (cookie pre-set)

Database setup:
- pytest-django creates isolated test databases (test_clearmoney, or
  test_clearmoney_gw0/gw1/... with xdist) and runs Django migrations.
- --reuse-db keeps test DBs between runs for speed.
- Each test is wrapped in a transaction that rolls back automatically.
"""

from collections.abc import Generator
from typing import Any

import pytest
from django.test import Client

from core.middleware import COOKIE_NAME

# Re-export factories so existing tests that import from conftest still work.
# New tests should import directly from tests.factories.
from tests.factories import AuthTokenFactory, SessionFactory, UserFactory

__all__ = ["UserFactory", "SessionFactory", "AuthTokenFactory"]

# ---------------------------------------------------------------------------
# Shared auth fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_user(db: Any) -> Generator[tuple[str, str, str], None, None]:
    """Create a test user and valid session. Yields (user_id, email, token).

    Cleanup is automatic — pytest-django rolls back the transaction at test end.
    Use this fixture in any test that needs an authenticated user.
    """
    user = UserFactory()
    session = SessionFactory(user=user)
    yield str(user.id), user.email, session.token


@pytest.fixture
def auth_cookie(auth_user: tuple[str, str, str]) -> dict[str, str]:
    """Return the HTTP_COOKIE kwarg dict for Django test client calls.

    Lower-level than auth_client — use when you need to control client setup.
    Usage:
        response = client.get('/settings', **auth_cookie)
    """
    _, _, token = auth_user
    return {"HTTP_COOKIE": f"{COOKIE_NAME}={token}"}


@pytest.fixture
def auth_client(client: Client, auth_user: tuple[str, str, str]) -> Client:
    """Return an authenticated Django test client with session cookie pre-set.

    More ergonomic than auth_cookie — the cookie is already applied.

    Usage:
        response = auth_client.get('/settings')
        response = auth_client.post('/some/path', data={'key': 'value'})
    """
    _, _, token = auth_user
    client.cookies[COOKIE_NAME] = token
    return client


@pytest.fixture(autouse=True)
def _disable_rate_limit(settings: Any) -> None:
    """Unit tests should not be rate-limited."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture(autouse=True)
def _ensure_seed_data(django_db_blocker: Any, django_db_setup: Any) -> None:
    """Re-seed global registry tables if a transactional test truncated them.

    `@pytest.mark.django_db(transaction=True)` issues TRUNCATE between tests,
    wiping migration-seeded data. This fixture re-seeds when missing so that
    view/service tests can rely on a stable baseline:
    - `system_banks` (20 Egypt banks, ticket #508)
    - `currencies` (6 bilingual currencies, ticket #512)
    """
    with django_db_blocker.unblock():
        from accounts.models import SystemBank
        from auth_app.models import Currency

        if not SystemBank.objects.filter(country="EG").exists():
            from importlib import import_module

            module = import_module("accounts.migrations.0011_seed_egypt_system_banks")
            from django.apps import apps as real_apps

            class _StubApps:
                def get_model(self, *args: Any, **kwargs: Any) -> Any:
                    return real_apps.get_model(*args, **kwargs)

            module.seed_banks(_StubApps(), None)

        egp = Currency.objects.filter(code="EGP").first()
        needs_reseed = egp is None or not (
            isinstance(egp.name, dict) and egp.name.get("ar")
        )
        if needs_reseed:
            seed_currencies = [
                ("EGP", {"en": "Egyptian Pound", "ar": "الجنيه المصري"}, "EGP", 0),
                ("USD", {"en": "US Dollar", "ar": "الدولار الأمريكي"}, "$", 1),
                ("EUR", {"en": "Euro", "ar": "اليورو"}, "EUR", 2),
                (
                    "GBP",
                    {"en": "British Pound", "ar": "الجنيه الإسترليني"},
                    "GBP",
                    3,
                ),
                ("AED", {"en": "UAE Dirham", "ar": "الدرهم الإماراتي"}, "AED", 4),
                ("SAR", {"en": "Saudi Riyal", "ar": "الريال السعودي"}, "SAR", 5),
            ]
            for code, name, symbol, order in seed_currencies:
                Currency.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "symbol": symbol,
                        "is_enabled": True,
                        "display_order": order,
                    },
                )


def set_auth_cookie(c: Client, token: str) -> Client:
    """Set session cookie on a Django test client. Import in test files.

    Usage:
        from conftest import set_auth_cookie
        c = set_auth_cookie(client, data["session_token"])
    """
    c.cookies[COOKIE_NAME] = token
    return c
