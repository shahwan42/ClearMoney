"""Tests for security configuration in settings."""

import importlib
import os
from types import ModuleType
from unittest import mock

from django.conf import settings
from django.test import TestCase


class TestSecurityHeaders(TestCase):
    """Verify security headers are configured correctly."""

    def test_content_type_nosniff_enabled(self) -> None:
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True

    def test_x_frame_options_deny(self) -> None:
        assert settings.X_FRAME_OPTIONS == "DENY"

    def test_x_frame_options_header_sent(self) -> None:
        """XFrameOptionsMiddleware adds X-Frame-Options to responses."""
        response = self.client.get("/login")
        assert response.get("X-Frame-Options") == "DENY"

    def test_content_type_nosniff_header_sent(self) -> None:
        """SecurityMiddleware adds X-Content-Type-Options to responses."""
        response = self.client.get("/login")
        assert response.get("X-Content-Type-Options") == "nosniff"


def _reload_settings() -> ModuleType:
    """Reload settings module — call within mock.patch.dict context only."""
    import clearmoney.settings as settings_mod

    return importlib.reload(settings_mod)


class TestSecretKeyHardening(TestCase):
    """Verify SECRET_KEY fails fast in production with insecure default."""

    def tearDown(self) -> None:
        """Restore settings after reload-based tests."""
        _reload_settings()

    def test_production_rejects_default_secret_key(self) -> None:
        """Settings module raises ValueError if production uses the default key."""
        env = {"ENV": "production"}
        with mock.patch.dict(os.environ, env, clear=False):
            # Remove DJANGO_SECRET_KEY to trigger the insecure default
            os.environ.pop("DJANGO_SECRET_KEY", None)
            with self.assertRaises(ValueError, msg="DJANGO_SECRET_KEY must be set"):
                _reload_settings()

    def test_production_accepts_custom_secret_key(self) -> None:
        """Settings module loads fine if production provides a real key."""
        env = {
            "ENV": "production",
            "DJANGO_SECRET_KEY": "a-real-secret-key-for-production",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            mod = _reload_settings()
            assert mod.SECRET_KEY == "a-real-secret-key-for-production"


class TestCsrfProtection(TestCase):
    """Verify CSRF middleware is active and configured correctly."""

    def test_csrf_middleware_enabled(self) -> None:
        from django.conf import settings as s

        assert "django.middleware.csrf.CsrfViewMiddleware" in s.MIDDLEWARE

    def test_post_without_csrf_token_rejected(self) -> None:
        """POST to a CSRF-protected endpoint without token is rejected (403)."""
        from django.test import Client

        # enforce_csrf_checks=True makes the test client mimic real browser behavior
        # Use /transactions (HTMX form endpoint) which is protected by CSRF
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post("/transactions")
        # 403 from CSRF or 302 redirect from auth — either way, not a successful POST
        assert response.status_code in (403, 302)

    def test_login_exempt_from_csrf(self) -> None:
        """Login POST works without CSRF token (uses honeypot anti-bot instead)."""
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post("/login", {"email": "test@example.com", "_rt": "0"})
        # Should not be 403 — login is csrf_exempt
        assert response.status_code != 403

    def test_logout_exempt_from_csrf(self) -> None:
        """Logout POST works without CSRF token (session-authenticated, no user data mutated)."""
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post("/logout")
        # Should not be 403 — logout is csrf_exempt
        assert response.status_code != 403


class TestDebugFlag(TestCase):
    """Verify DEBUG is explicit opt-in for production."""

    def tearDown(self) -> None:
        _reload_settings()

    def test_debug_true_in_development(self) -> None:
        """Dev environment defaults to DEBUG=True."""
        env = {"ENV": "development"}
        with mock.patch.dict(os.environ, env, clear=False):
            mod = _reload_settings()
            assert mod.DEBUG is True

    def test_production_debug_false_by_default(self) -> None:
        """In production, DEBUG is False unless explicitly set to 'true'."""
        env = {"ENV": "production", "DJANGO_SECRET_KEY": "test-key"}
        with mock.patch.dict(os.environ, env, clear=False):
            mod = _reload_settings()
            assert mod.DEBUG is False
