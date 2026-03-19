"""
GoSessionAuthMiddleware — reads Go's session cookie to authenticate requests.

This is the Django equivalent of internal/middleware/auth.go.
The Go app sets a 'clearmoney_session' cookie containing a random token.
This middleware looks up that token in the 'sessions' table and sets
request.user_id and request.user_email for downstream views.

Like Django's AuthenticationMiddleware, but reads Go's session table
instead of Django's django_session table.
"""

import logging
from collections.abc import Callable
from typing import cast

from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone

from core.types import AuthenticatedRequest

logger = logging.getLogger(__name__)

COOKIE_NAME = "clearmoney_session"

# Paths that don't require authentication
PUBLIC_PATHS = ["/healthz", "/static/", "/login", "/register", "/auth/verify"]


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

        # Validate session against database
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.user_id, u.email
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = %s AND s.expires_at > %s
                """,
                [token, timezone.now()],
            )
            row = cursor.fetchone()

        if not row:
            logger.warning("auth: invalid session, path=%s", path)
            response = HttpResponseRedirect("/login")
            response.delete_cookie(COOKIE_NAME)
            return response

        # Cast to AuthenticatedRequest — we've just verified user_id + email from DB
        auth_request = cast(AuthenticatedRequest, request)
        auth_request.user_id = str(row[0])
        auth_request.user_email = row[1]

        return self.get_response(auth_request)
