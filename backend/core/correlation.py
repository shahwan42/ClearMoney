"""Request correlation ID middleware for log tracing."""

import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware:
    """Attach a unique correlation ID to every request for log tracing.

    Reads X-Request-ID header if present (from Caddy/load balancer),
    otherwise generates a new UUID. Adds it to the response headers
    and injects it into the logging context via a filter.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # Inject into thread-local logging context
        old_factory = logging.getLogRecordFactory()

        def record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
            record = old_factory(*args, **kwargs)
            record.correlation_id = correlation_id
            return record

        logging.setLogRecordFactory(record_factory)

        response = self.get_response(request)
        response["X-Request-ID"] = correlation_id

        # Restore original factory
        logging.setLogRecordFactory(old_factory)
        return response
