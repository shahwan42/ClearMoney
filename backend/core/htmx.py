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

from django.http import HttpResponse, HttpResponseRedirect
from django_htmx.http import HttpResponseClientRedirect


def htmx_redirect(request, url):
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
    if request.htmx:
        return HttpResponseClientRedirect(url)
    return HttpResponseRedirect(url)


def render_htmx_result(result_type, message, detail=""):
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

    detail_html = f'<p class="text-xs {text} mt-1">{detail}</p>' if detail else ""
    html = (
        f'<div class="rounded-lg border p-3 {bg}">'
        f'<p class="text-sm font-medium {text}">{message}</p>'
        f"{detail_html}"
        f"</div>"
    )
    return HttpResponse(html)
