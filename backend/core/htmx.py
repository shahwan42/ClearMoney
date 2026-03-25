"""
HTMX response helpers — thin wrappers around django-htmx's response classes.

django-htmx provides:
- request.htmx (bool) — whether the request came from HTMX
- HttpResponseClientRedirect — sends HX-Redirect header
- HttpResponseClientRefresh — triggers full page reload

This module adds ClearMoney-specific helpers for redirects and inline
result fragments, using django-htmx under the hood.
"""

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django_htmx.http import HttpResponseClientRedirect


def htmx_redirect(request: HttpRequest, url: str) -> HttpResponse:
    """
    Redirect that works for both HTMX and standard requests.

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

    Returns an HTML fragment that HTMX swaps into the target element.

    Args:
        result_type: One of 'success', 'error', 'info'
        message: Main message text
        detail: Optional detail text shown below the message

    Returns:
        HttpResponse containing the result HTML fragment
    """
    # Color schemes for each result type
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


def error_html(message: str, field: str = "", show_retry: bool = False) -> str:
    """Return error HTML fragment string for HTMX swap targets.

    Includes aria-live for screen readers, error icon, and scroll-into-view.
    When ``field`` is provided, the named input gets a red border, aria-invalid,
    and aria-describedby linking it to the error message.
    When ``show_retry`` is True, includes a retry button for network failures.
    """
    error_id = f"error-{field}" if field else ""
    id_attr = f' id="{error_id}"' if error_id else ""
    retry_button = (
        (
            '<button type="button" onclick="location.reload()" '
            'class="ml-2 px-3 py-1 bg-red-200 dark:bg-red-900 hover:bg-red-300 dark:hover:bg-red-800 '
            'text-red-700 dark:text-red-300 rounded text-xs font-medium min-h-[44px] flex items-center">'
            "Retry"
            "</button>"
        )
        if show_retry
        else ""
    )
    html = (
        f'<div role="alert" aria-live="assertive"{id_attr} '
        'class="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 '
        'text-red-700 dark:text-red-300 p-3 rounded-lg text-sm flex items-center gap-2">'
        '<svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" '
        'stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">'
        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
        'd="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 '
        "1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 "
        '16c-.77 1.333.192 3 1.732 3z"/></svg>'
        f"<span>{message}</span>"
        f"{retry_button}"
    )
    # Field highlighting script — marks the input with red border + ARIA attributes
    if field:
        html += (
            "<script>(function(){"
            f"var f=document.querySelector('[name=\"{field}\"]');"
            "if(f){"
            "f.setAttribute('aria-invalid','true');"
            f"f.setAttribute('aria-describedby','{error_id}');"
            "f.classList.add('border-red-500','ring-1','ring-red-500');"
            "f.addEventListener('input',function h(){"
            "f.removeAttribute('aria-invalid');"
            "f.removeAttribute('aria-describedby');"
            "f.classList.remove('border-red-500','ring-1','ring-red-500');"
            "f.removeEventListener('input',h);},{once:true});"
            "f.scrollIntoView({behavior:'smooth',block:'nearest'});"
            "}"
            "})()</script>"
        )
    else:
        html += (
            "<script>(function(){var el=document.querySelector('[role=\"alert\"]');"
            "if(el) el.scrollIntoView({behavior:'smooth',block:'nearest'});})()</script>"
        )
    html += "</div>"
    return html


def success_html(message: str) -> str:
    """Return success toast HTML fragment string for HTMX swap targets.

    Includes auto-dismiss after 3 seconds and a manual dismiss button.
    """
    return (
        '<div role="status" aria-live="polite" class="bg-teal-50 border border-teal-200 '
        'rounded-xl p-3 text-center animate-toast relative" data-auto-dismiss>'
        f'<p class="text-teal-800 font-semibold text-sm">{message}</p>'
        '<button type="button" aria-label="Dismiss" '
        'class="absolute top-1 right-2 text-teal-400 hover:text-teal-600 text-lg leading-none" '
        'onclick="this.parentElement.remove()">&times;</button>'
        "<script>"
        "(function(){var el=document.querySelector('[data-auto-dismiss]');"
        "if(el) setTimeout(function(){el.style.transition='opacity 0.3s';"
        "el.style.opacity='0';setTimeout(function(){el.remove()},300)},3000);})()"
        "</script>"
        "</div>"
    )


def error_response(message: str, field: str = "") -> HttpResponse:
    """Return error HTML fragment as HttpResponse with status 400."""
    return HttpResponse(error_html(message, field=field), status=400)


def success_response(message: str) -> HttpResponse:
    """Return success toast HTML fragment as HttpResponse."""
    return HttpResponse(success_html(message))
