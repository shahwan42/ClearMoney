"""
Root conftest.py — shared pytest fixtures for all Django test files.

Provides:
- django_db_setup override: uses the real DB with --reuse-db (migrations already applied)
- UserFactory / SessionFactory: re-exported from tests/factories.py for backward compat
- auth_user fixture: creates a test user + valid session, yields (user_id, email, token), cleans up
- auth_cookie fixture: returns the HTTP_COOKIE kwarg dict for Django test client calls
- auth_client fixture: returns an authenticated Django test client (cookie pre-set)
"""

from collections.abc import Generator
from typing import Any

import pytest
from django.test import Client

from core.middleware import COOKIE_NAME
from core.models import Session, User

# Re-export factories so existing tests that import from conftest still work.
# New tests should import directly from tests.factories.
from tests.factories import AuthTokenFactory, SessionFactory, UserFactory

__all__ = ["UserFactory", "SessionFactory", "AuthTokenFactory"]

# ---------------------------------------------------------------------------
# Database setup — skip test DB creation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def django_db_setup() -> None:
    """Use the real database — migrations are already applied.

    Overrides pytest-django's default behaviour of creating/destroying a
    test database. Combined with --reuse-db in pyproject.toml, tests run
    directly against the real PostgreSQL schema.
    """
    pass  # intentionally empty


# ---------------------------------------------------------------------------
# Shared auth fixtures — like Go's testutil.SetupAuth(t, db)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_user(db: Any) -> Generator[tuple[str, str, str], None, None]:
    """Create a test user and valid session. Yields (user_id, email, token).

    Mirrors Go's testutil.SetupAuth(t, db) pattern. Cleans up after the test.
    Use this fixture in any test that needs an authenticated user.
    """
    user = UserFactory()
    session = SessionFactory(user=user)
    yield str(user.id), user.email, session.token
    # Explicit cleanup — needed because django_db_setup skips transaction rollback
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


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
    Like Go's testutil.SetupAuth returning a client with the cookie header.

    Usage:
        response = auth_client.get('/settings')
        response = auth_client.post('/some/path', data={'key': 'value'})
    """
    _, _, token = auth_user
    client.cookies[COOKIE_NAME] = token
    return client
