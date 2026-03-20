"""
HTMX response helpers — thin wrappers around django-htmx's response classes.

django-htmx provides:
- request.htmx (bool) — whether the request came from HTMX
- HttpResponseClientRedirect — sends HX-Redirect header
- HttpResponseClientRefresh — triggers full page reload

This module adds ClearMoney-specific helpers that match the Go app's patterns
(htmxRedirect, renderHTMXResult) using django-htmx under the hood.

Like Go's htmxRedirect(w, r, url) in internal/handler/pages.go.
"""

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django_htmx.http import HttpResponseClientRedirect


def htmx_redirect(request: HttpRequest, url: str) -> HttpResponse:
    """
    Redirect that works for both HTMX and standard requests.

    Equivalent of Go's htmxRedirect(w, r, url).
    Uses django-htmx's HttpResponseClientRedirect for HTMX requests,
    standard HTTP 302 for regular requests.

    Args:
        request: Django HttpRequest (must have request.htmx from HtmxMiddleware)
        url: Target URL to redirect to

    Returns:
        HttpResponse with appropriate redirect mechanism
    """
    if request.htmx:  # type: ignore[attr-defined]
        return HttpResponseClientRedirect(url)
    return HttpResponseRedirect(url)


def render_htmx_result(
    result_type: str, message: str, detail: str = ""
) -> HttpResponse:
    """
    Render an inline result partial (success/error/info toast).

    Equivalent of Go's renderHTMXResult(w, type, msg, detail).
    Returns an HTML fragment that HTMX swaps into the target element.

    Args:
        result_type: One of 'success', 'error', 'info'
        message: Main message text
        detail: Optional detail text shown below the message

    Returns:
        HttpResponse containing the result HTML fragment
    """
    # Color schemes matching Go's htmx-result partial
    colors = {
        "success": ("bg-green-50 border-green-200", "text-green-800"),
        "error": ("bg-red-50 border-red-200", "text-red-800"),
        "info": ("bg-blue-50 border-blue-200", "text-blue-800"),
    }
    bg, text = colors.get(result_type, colors["info"])

    role = "alert" if result_type == "error" else "status"
    detail_html = f'<p class="text-xs {text} mt-1">{detail}</p>' if detail else ""
    html = (
        f'<div role="{role}" class="rounded-lg border p-3 {bg}">'
        f'<p class="text-sm font-medium {text}">{message}</p>'
        f"{detail_html}"
        f"</div>"
    )
    return HttpResponse(html)


def error_html(message: str) -> str:
    """Return error HTML fragment string for HTMX swap targets."""
    return f'<div role="alert" class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{message}</div>'


def success_html(message: str) -> str:
    """Return success toast HTML fragment string for HTMX swap targets."""
    return (
        '<div role="status" class="bg-teal-50 border border-teal-200 rounded-xl p-3 '
        'text-center animate-toast">'
        f'<p class="text-teal-800 font-semibold text-sm">{message}</p>'
        "</div>"
    )


def error_response(message: str) -> HttpResponse:
    """Return error HTML fragment as HttpResponse with status 400."""
    return HttpResponse(error_html(message), status=400)


def success_response(message: str) -> HttpResponse:
    """Return success toast HTML fragment as HttpResponse."""
    return HttpResponse(success_html(message))
