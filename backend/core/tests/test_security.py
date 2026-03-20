"""Tests for security header configuration in settings."""

from django.conf import settings
from django.test import TestCase


class TestSecurityHeaders(TestCase):
    """Verify security headers are configured correctly."""

    def test_content_type_nosniff_enabled(self) -> None:
        assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True

    def test_x_frame_options_deny(self) -> None:
        assert settings.X_FRAME_OPTIONS == "DENY"

    def test_x_frame_options_header_sent(self) -> None:
        """SecurityMiddleware adds X-Frame-Options to responses."""
        response = self.client.get("/login")
        assert response.get("X-Frame-Options") == "DENY"

    def test_content_type_nosniff_header_sent(self) -> None:
        """SecurityMiddleware adds X-Content-Type-Options to responses."""
        response = self.client.get("/login")
        assert response.get("X-Content-Type-Options") == "nosniff"
