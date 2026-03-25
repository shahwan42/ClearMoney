"""
Auth URL patterns — routes for /login, /register (redirect), /auth/verify, /logout.

/register redirects to /login for backward compatibility (unified auth flow).
"""

from django.urls import path
from django.views.generic import RedirectView

from auth_app import views

urlpatterns = [
    # Unified auth entry point (login + registration)
    path("login", views.auth_view, name="auth"),
    # Backward-compatible redirect for /register bookmarks
    path(
        "register", RedirectView.as_view(url="/login", permanent=False), name="register"
    ),
    # Token verification + session creation (unchanged)
    path("auth/verify", views.verify_magic_link, name="verify-magic-link"),
    # Logout (unchanged)
    path("logout", views.logout_view, name="logout"),
]
