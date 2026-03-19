"""
Root conftest.py — shared pytest fixtures and factory_boy factories.

Provides:
- django_db_setup override: skips test DB creation (Go owns the schema, Django never runs migrations)
- UserFactory / SessionFactory: factory_boy factories for the two most-reused models
- auth_user fixture: creates a test user + valid session, yields (user_id, email, token), cleans up after
- auth_cookie fixture: returns the HTTP_COOKIE kwarg dict for Django test client calls
"""

import uuid
from datetime import timedelta

import factory
import pytest
from django.utils import timezone

from core.middleware import COOKIE_NAME
from core.models import Session, User

# ---------------------------------------------------------------------------
# Database setup — skip test DB creation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def django_db_setup():
    """Use the real database — Go owns the schema, Django never creates it.

    Overrides pytest-django's default behaviour of creating/destroying a
    test_clearmoney database. This mirrors the --keepdb flag used with
    manage.py test: tests run directly against the real PostgreSQL schema
    that golang-migrate manages.
    """
    pass  # intentionally empty


# ---------------------------------------------------------------------------
# Factories — like Laravel's UserFactory::create()
# ---------------------------------------------------------------------------


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for the users table (Go schema, managed=False in Django)."""

    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyFunction(lambda: f"pytest-{uuid.uuid4().hex[:8]}@example.com")


class SessionFactory(factory.django.DjangoModelFactory):
    """Factory for the sessions table — creates a valid 30-day session."""

    class Meta:
        model = Session

    id = factory.LazyFunction(uuid.uuid4)
    user = factory.SubFactory(UserFactory)
    token = factory.LazyFunction(lambda: str(uuid.uuid4()))
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_user(db):
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
def auth_cookie(auth_user):
    """Return the HTTP_COOKIE kwarg dict for Django test client calls.

    Usage:
        response = client.get('/settings', **auth_cookie)
    """
    _, _, token = auth_user
    return {"HTTP_COOKIE": f"{COOKIE_NAME}={token}"}
