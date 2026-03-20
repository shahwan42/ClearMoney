"""Core views — custom error handlers for 404, 500, and 429 responses."""

import logging

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def custom_404(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Custom 404 page matching app design. Returns inline HTML for HTMX requests."""
    if getattr(request, "htmx", False):
        return HttpResponse(
            '<div class="p-4 text-center text-gray-500">Page not found</div>',
            status=404,
        )
    return render(request, "404.html", status=404)


def custom_500(request: HttpRequest) -> HttpResponse:
    """Custom 500 page. Uses standalone template (no extends) as a safety net."""
    return render(request, "500.html", status=500)


def ratelimited_error(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    """Custom 429 response — HTMX-aware rate limit handler."""
    logger.warning(
        "rate_limit.denied path=%s method=%s ip=%s",
        request.path,
        request.method,
        request.META.get("REMOTE_ADDR"),
    )
    if getattr(request, "htmx", False):
        return HttpResponse(
            '<div class="p-4 text-center text-amber-600 dark:text-amber-400">'
            "Too many requests. Please wait a moment."
            "</div>",
            status=429,
        )
    return render(request, "429.html", status=429)
