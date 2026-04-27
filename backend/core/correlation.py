"""Request correlation ID middleware for distributed log tracing.

Attaches a unique correlation ID to each request and all its log records,
enabling end-to-end tracing across multiple services or log aggregation systems.
"""

import logging
import uuid
from collections.abc import Callable
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

# Per-context (thread/async task) correlation ID — safe under Django's threaded dev server.
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


class _CorrelationFilter(logging.Filter):
    """Inject the current request's correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


# Install the filter once at import time — it reads from ContextVar per-record.
_filter = _CorrelationFilter()
logging.root.addFilter(_filter)


class CorrelationIdMiddleware:
    """Attach a unique correlation ID to every request for log tracing.

    CORRELATION ID FLOW:
    1. Read X-Request-ID header from Caddy/load balancer if present.
       Fall back to a short UUID (8 chars).
    2. Store correlation_id on the request object for view-level access.
    3. Set the per-thread ContextVar so all log records during this request
       include correlation_id automatically (via %(correlation_id)s in formatters).
    4. Return correlation_id in response headers (X-Request-ID) for client tracking.
    5. Reset ContextVar after request completes (token-based, always via finally).

    LOGGING INTEGRATION:
    Configure formatters in logging config to include %(correlation_id)s:
        FORMAT = '[%(correlation_id)s] %(name)s: %(message)s'
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        token = _correlation_id.set(correlation_id)
        try:
            response = self.get_response(request)
        finally:
            _correlation_id.reset(token)

        response["X-Request-ID"] = correlation_id
        return response
