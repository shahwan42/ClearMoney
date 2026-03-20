"""
Auth views — page handlers for /login, /register, /auth/verify, /logout.

Port of Go's internal/handler/auth.go.
Like Laravel's LoginController — handles magic link auth with honeypot
and timing anti-bot protection.

Auth pages use bare layout (no header/nav) and standard form POST
(no HTMX) for proper cookie handling.
"""

import logging
import time

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from auth_app.services import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    SendResult,
    auth_service,
    rate_limit_message,
)
from core.ratelimit import login_rate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@csrf_exempt  # Auth uses honeypot + timing anti-bot instead of CSRF tokens
@login_rate
@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """GET /login — render login form. POST /login — send magic link."""
    if request.method == "POST":
        return _login_submit(request)

    logger.info("page viewed page=login")
    return render(
        request,
        "auth_app/login.html",
        {
            "render_time": int(time.time()),
        },
    )


def _login_submit(request: HttpRequest) -> HttpResponse:
    """Process login form — send magic link if user exists.

    Always shows "Check your email" regardless of whether user exists
    (prevents email enumeration).
    """
    # Honeypot check: hidden field that bots fill
    if request.POST.get("website"):
        logger.info("login: honeypot triggered (bot detected)")
        return render(request, "auth_app/check_email.html", {})

    # Timing check: reject if submitted too fast (< 2 seconds)
    rt_str = request.POST.get("_rt", "")
    if rt_str:
        try:
            rt = int(rt_str)
            if int(time.time()) - rt < 2:
                logger.info("login: timing check failed (too fast)")
                return render(request, "auth_app/check_email.html", {})
        except (ValueError, TypeError):
            pass

    email = request.POST.get("email", "").strip()
    if not email:
        return render(
            request,
            "auth_app/login.html",
            {
                "error": "Email is required",
                "render_time": int(time.time()),
            },
        )

    result, err = auth_service.request_login_link(email)
    if err:
        logger.error("login: failed to request magic link error=%s", err)

    # Always show "check your email" — even if user doesn't exist.
    # Hint flag shows for ALL non-sent outcomes (unknown, cooldown, etc.)
    # so it reveals nothing about whether the account exists.
    ctx: dict[str, object] = {"email": email}
    if result != SendResult.SENT:
        ctx["hint"] = True
    return render(request, "auth_app/check_email.html", ctx)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@csrf_exempt  # Auth uses honeypot + timing anti-bot instead of CSRF tokens
@login_rate
@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    """GET /register — render form. POST /register — send registration link."""
    if request.method == "POST":
        return _register_submit(request)

    logger.info("page viewed page=register")
    return render(
        request,
        "auth_app/register.html",
        {
            "render_time": int(time.time()),
        },
    )


def _register_submit(request: HttpRequest) -> HttpResponse:
    """Process registration form — send magic link for new user."""
    # Honeypot check
    if request.POST.get("website"):
        logger.info("register: honeypot triggered (bot detected)")
        return render(request, "auth_app/check_email.html", {})

    # Timing check
    rt_str = request.POST.get("_rt", "")
    if rt_str:
        try:
            rt = int(rt_str)
            if int(time.time()) - rt < 2:
                logger.info("register: timing check failed (too fast)")
                return render(request, "auth_app/check_email.html", {})
        except (ValueError, TypeError):
            pass

    email = request.POST.get("email", "").strip()
    if not email:
        return render(
            request,
            "auth_app/register.html",
            {
                "error": "Email is required",
                "render_time": int(time.time()),
            },
        )

    result, err = auth_service.request_registration_link(email)
    if err:
        # Show error for registration (safe to reveal "already registered")
        return render(
            request,
            "auth_app/register.html",
            {
                "error": err,
                "render_time": int(time.time()),
            },
        )

    # Registration reveals email existence, so specific rate-limit messages are safe
    if result != SendResult.SENT:
        msg = rate_limit_message(result)
        return render(
            request,
            "auth_app/register.html",
            {
                "error": msg,
                "render_time": int(time.time()),
            },
        )

    return render(request, "auth_app/check_email.html", {"email": email})


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
