"""Rate limiting decorators for the three-tier system.

Tiers:
- login_rate: 5/min — auth endpoints (brute force protection, keyed by IP)
- api_rate: 60/min — JSON API endpoints (keyed by user_id)
- general_rate: 120/min — authenticated HTML page views (keyed by user_id)

login_rate uses IP since the user isn't authenticated yet.
api_rate and general_rate use user_id from the auth middleware, so rate limits
work correctly behind Caddy reverse proxy (where all IPs would be the same).
"""

from collections.abc import Callable

from django.http import HttpRequest
from django_ratelimit.decorators import ratelimit


def _user_or_ip(group: str, request: HttpRequest) -> str:
    """Rate limit key: user_id if authenticated, else IP.

    This ensures per-user limits for authenticated endpoints and prevents
    all users sharing a single IP rate limit bucket behind a reverse proxy.
    """
    user_id = getattr(request, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def login_rate[F: Callable[..., object]](view_func: F) -> F:
    """5 requests/minute — for login, register, verify, logout."""
    return ratelimit(key="ip", rate="5/m", method=ratelimit.ALL, block=True)(view_func)  # type: ignore[no-any-return]


def api_rate[F: Callable[..., object]](view_func: F) -> F:
    """60 requests/minute — for /api/* JSON endpoints."""
    decorated = ratelimit(
        key=_user_or_ip, rate="60/m", method=ratelimit.ALL, block=True
    )
    return decorated(view_func)  # type: ignore[no-any-return]


def general_rate[F: Callable[..., object]](view_func: F) -> F:
    """120 requests/minute — for authenticated HTML page views."""
    decorated = ratelimit(
        key=_user_or_ip, rate="120/m", method=ratelimit.ALL, block=True
    )
    return decorated(view_func)  # type: ignore[no-any-return]
