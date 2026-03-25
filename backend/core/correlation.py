"""Request correlation ID middleware for distributed log tracing.

Attaches a unique correlation ID to each request and all its log records,
enabling end-to-end tracing across multiple services or log aggregation systems.
"""

import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware:
    """Attach a unique correlation ID to every request for log tracing.

    CORRELATION ID FLOW:
    1. Read X-Request-ID header from Caddy/load balancer if present (preserves
       trace across reverse proxies). Fall back to generating a short UUID (8 chars).
    2. Store correlation_id on the request object for view-level access.
    3. Inject into logging context by replacing the LogRecordFactory. Each LogRecord
       created during request processing will automatically get the correlation_id
       attribute, making it available in log formatters via %(correlation_id)s.
    4. Return correlation_id in response headers (X-Request-ID) for client tracking.
    5. Restore original LogRecordFactory after request completes to avoid memory leaks.

    LOGGING INTEGRATION:
    Configure formatters in logging config to include %(correlation_id)s:
        FORMAT = '[%(correlation_id)s] %(name)s: %(message)s'

    This enables queries like `grep correlation_id=abc123 /var/log/app.log`
    to follow a single request through all app logs.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Use X-Request-ID header if present (from Caddy/load balancer), else generate
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # Save original LogRecordFactory and replace with a version that injects correlation_id
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
            """Factory that adds correlation_id to every LogRecord created during this request."""
            record = old_factory(*args, **kwargs)
            record.correlation_id = correlation_id
            return record

        logging.setLogRecordFactory(record_factory)

        # Process the request — all LogRecords created will include correlation_id
        response = self.get_response(request)
        response["X-Request-ID"] = correlation_id

        # Critical: restore original factory to avoid leaking the correlation_id
        # into logs from other requests
        logging.setLogRecordFactory(old_factory)
        return response
