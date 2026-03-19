"""
Custom request types for type-safe view signatures.

GoSessionAuthMiddleware sets user_id and user_email on every authenticated
request. This module provides AuthenticatedRequest — an HttpRequest subclass
that declares those attributes so mypy can verify views use them safely.

Like Laravel's Request macro typing or Django REST Framework's Request class.
"""

from django.http import HttpRequest


class AuthenticatedRequest(HttpRequest):
    """HttpRequest with user_id and user_email set by GoSessionAuthMiddleware.

    Use this as the request parameter type in all view functions that are
    protected by the middleware (everything except public paths).
    """

    user_id: str
    user_email: str
