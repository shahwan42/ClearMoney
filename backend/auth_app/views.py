"""
Auth views — page handlers for /login, /auth/verify, /logout.

Like Laravel's LoginController — handles magic link auth with honeypot
and timing anti-bot protection. Unified flow: /login handles both
sign-in and registration via auto-detect.

Auth pages use bare layout (no header/nav) and standard form POST
(no HTMX) for proper cookie handling.
"""

import logging
import time

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone as django_tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from auth_app.models import Session
from auth_app.services import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SendResult,
    auth_service,
)
from core.ratelimit import login_rate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified Auth (login + registration)
# ---------------------------------------------------------------------------


@csrf_exempt  # Auth uses honeypot + timing anti-bot instead of CSRF tokens
@login_rate
@require_http_methods(["GET", "POST"])
def auth_view(request: HttpRequest) -> HttpResponse:
    """GET /login — render unified auth page. POST /login — request magic link."""
    if request.method == "POST":
        return _auth_submit(request)

    logger.info("page viewed page=auth")
    return render(
        request,
        "auth_app/auth.html",
        {"render_time": int(time.time())},
    )


def _auth_submit(request: HttpRequest) -> HttpResponse:
    """Handle unified magic link request — auto-detects login vs registration."""
    # Honeypot check: hidden field that bots fill — show check_email so bots
    # think the submission succeeded (silent trap, not a visible rejection)
    if request.POST.get("website"):
        logger.info("auth: honeypot triggered (bot detected)")
        return render(request, "auth_app/check_email.html", {})

    # Timing check: reject if submitted too fast (< 2 seconds)
    try:
        render_time = int(request.POST.get("_rt", "0"))
    except ValueError:
        render_time = 0
    if int(time.time()) - render_time < 2:
        logger.info("auth: timing check failed (too fast)")
        return render(request, "auth_app/auth.html", {"render_time": int(time.time())})

    email = request.POST.get("email", "").strip()
    if not email:
        return render(
            request,
            "auth_app/auth.html",
            {
                "render_time": int(time.time()),
                "error": "Email is required",
            },
        )

    result, _error, is_new_user = auth_service.request_access_link(
        email, accept_language=request.META.get("HTTP_ACCEPT_LANGUAGE")
    )

    hint = result != SendResult.SENT
    return render(
        request,
        "auth_app/check_email.html",
        {
            "email": email,
            "hint": hint,
            "is_new_user": is_new_user,
        },
    )


# ---------------------------------------------------------------------------
# Verify Magic Link
# ---------------------------------------------------------------------------


@login_rate
@require_http_methods(["GET"])
def verify_magic_link(request: HttpRequest) -> HttpResponse:
    """GET /auth/verify?token=xxx — verify token, create session, redirect."""
    token = request.GET.get("token", "")
    if not token:
        return render(request, "auth_app/link_expired.html", {})

    result, err = auth_service.verify_magic_link(token)
    if err:
        logger.warning("auth: magic link verification failed error=%s", err)
        return render(request, "auth_app/link_expired.html", {"error": err})

    assert result is not None  # err is None → result is not None

    # Set session cookie and redirect to home
    session_token = str(result["session_token"])
    response = HttpResponseRedirect("/")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@csrf_exempt  # Session-authenticated; no user-controlled data mutated, CSRF not required
@login_rate
@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    """POST /logout — delete session, clear cookie, redirect to /login."""
    token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if token:
        auth_service.logout(token)

    response = HttpResponseRedirect("/login")
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


# ---------------------------------------------------------------------------
# Session status API — for timeout warning JS
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def session_status(request: HttpRequest) -> HttpResponse:
    """GET /api/session-status — return session expiry for timeout warning.

    Returns JSON with expires_in_seconds. Used by session-warning.js
    to show a warning banner before the session expires.
    """
    token = request.COOKIES.get(SESSION_COOKIE_NAME, "")
    if not token:
        return JsonResponse({"error": "not authenticated"}, status=401)

    session = Session.objects.filter(
        token=token, expires_at__gt=django_tz.now()
    ).first()
    if not session:
        return JsonResponse({"error": "session expired"}, status=401)

    remaining = (session.expires_at - django_tz.now()).total_seconds()
    return JsonResponse({"expires_in_seconds": int(remaining)})
