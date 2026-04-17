"""
Decorators for common view patterns in ClearMoney.

This module provides reusable decorators for view functions, reducing boilerplate
and improving code consistency across the backend.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from core.types import AuthenticatedRequest

R = TypeVar("R")


def inject_service(
    service_class: type[Any],
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator that instantiates a service and injects it into the view function.

    This decorator eliminates the repetitive pattern of creating a service helper
    (e.g., `_svc(request)`) in every view. Instead, the service is instantiated
    with `request.user_id` and `request.tz` and passed as the first parameter
    after the request.

    Usage:
        from transactions.services import TransactionService

        @inject_service(TransactionService)
        def transactions_list(
            request: AuthenticatedRequest,
            svc: TransactionService
        ) -> HttpResponse:
            transactions = svc.get_all()
            ...

    Args:
        service_class: The service class to instantiate (e.g., TransactionService).
                      Must accept (user_id: str, tz: ZoneInfo) in __init__.

    Returns:
        A decorator function that wraps the view.

    Raises:
        TypeError: If the service class cannot be instantiated with the given parameters.
    """

    def decorator(view_func: Callable[..., R]) -> Callable[..., R]:
        """Inner decorator that wraps the view function."""

        @wraps(view_func)
        def wrapper(request: AuthenticatedRequest, *args: Any, **kwargs: Any) -> R:
            svc = service_class(request.user_id, request.tz)
            return view_func(request, svc, *args, **kwargs)

        return wrapper

    return decorator
