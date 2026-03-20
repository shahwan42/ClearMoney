"""Rate limiting decorators for the three-tier system.

Tiers:
- login_rate: 5/min — auth endpoints (brute force protection)
- api_rate: 60/min — JSON API endpoints
- general_rate: 120/min — authenticated HTML page views

Uses django-ratelimit with IP-based keys. Disabled when DISABLE_RATE_LIMIT=true.
"""

from collections.abc import Callable

from django_ratelimit.decorators import ratelimit


def login_rate[F: Callable[..., object]](view_func: F) -> F:
    """5 requests/minute — for login, register, verify, logout."""
    return ratelimit(key="ip", rate="5/m", method=ratelimit.ALL, block=True)(view_func)  # type: ignore[no-any-return]


def api_rate[F: Callable[..., object]](view_func: F) -> F:
    """60 requests/minute — for /api/* JSON endpoints."""
    return ratelimit(key="ip", rate="60/m", method=ratelimit.ALL, block=True)(view_func)  # type: ignore[no-any-return]


def general_rate[F: Callable[..., object]](view_func: F) -> F:
    """120 requests/minute — for authenticated HTML page views."""
    return ratelimit(  # type: ignore[no-any-return]
        key="ip", rate="120/m", method=ratelimit.ALL, block=True
    )(view_func)
