"""Tests for rate limiting key function."""

from django.test import RequestFactory, TestCase

from core.ratelimit import _user_or_ip


class TestUserOrIpKey(TestCase):
    """Verify rate limit key uses user_id when available, IP otherwise."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_authenticated_user_gets_user_key(self) -> None:
        request = self.factory.get("/")
        request.user_id = "abc-123"  # type: ignore[attr-defined]
        assert _user_or_ip("test", request) == "user:abc-123"

    def test_unauthenticated_falls_back_to_ip(self) -> None:
        request = self.factory.get("/")
        # No user_id attribute
        assert _user_or_ip("test", request).startswith("ip:")

    def test_ip_key_uses_remote_addr(self) -> None:
        request = self.factory.get("/", REMOTE_ADDR="1.2.3.4")
        assert _user_or_ip("test", request) == "ip:1.2.3.4"
