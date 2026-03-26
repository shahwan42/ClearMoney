"""
Session authentication middleware for ClearMoney.

Reads the 'clearmoney_session' cookie containing a random token,
looks it up in the 'sessions' table, and sets request.user_id and
request.user_email for downstream views.

Like Django's AuthenticationMiddleware, but uses the custom sessions table
instead of Django's django_session table.
"""

import logging
import os
import zoneinfo
from collections.abc import Callable
from typing import cast

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone as django_tz

from core.models import Session
from core.types import AuthenticatedRequest

logger = logging.getLogger(__name__)

COOKIE_NAME = "clearmoney_session"


class TimezoneMiddleware:
    """Attaches the app's configured timezone to every request as request.tz.

    Like Django's django.middleware.locale.LocaleMiddleware but for timezone.
    Views use request.tz for business-logic date rendering.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        tz_name = os.getenv("APP_TIMEZONE", "Africa/Cairo")
        self.tz = zoneinfo.ZoneInfo(tz_name)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.tz = self.tz  # type: ignore[attr-defined]
        return self.get_response(request)


# Paths that don't require authentication
PUBLIC_PATHS = [
    "/healthz",
    "/static/",
    "/login",
    "/auth/verify",
    "/logout",
    "/api/session-status",
]


class GoSessionAuthMiddleware:
    """
    Validates the Go session cookie on every request.
    Sets request.user_id and request.user_email for authenticated users.
    Redirects to /login for unauthenticated requests to protected paths.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path

        # Skip auth for public paths
        if any(path == p or path.startswith(p) for p in PUBLIC_PATHS):
            return self.get_response(request)

        # Read session cookie
        token = request.COOKIES.get(COOKIE_NAME, "")
        if not token:
            logger.warning("auth: no session cookie, path=%s", path)
            return HttpResponseRedirect("/login")

        # Validate session against database using ORM with select_related
        session = (
            Session.objects.select_related("user")
            .filter(token=token, expires_at__gt=django_tz.now())
            .first()
        )

        if not session:
            logger.warning("auth: invalid session, path=%s", path)
            response = HttpResponseRedirect("/login")
            response.delete_cookie(COOKIE_NAME)
            return response

        # Cast to AuthenticatedRequest — we've just verified user_id + email from DB
        auth_request = cast(AuthenticatedRequest, request)
        auth_request.user_id = str(session.user_id)
        auth_request.user_email = session.user.email

        return self.get_response(auth_request)


class ExceptionLoggingMiddleware:
    """Log unhandled exceptions with request context before Django returns 500."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """Called by Django when a view raises an unhandled exception."""
        logger.exception(
            "unhandled_exception path=%s method=%s user=%s",
            request.path,
            request.method,
            getattr(request, "user_id", "anonymous"),
        )
