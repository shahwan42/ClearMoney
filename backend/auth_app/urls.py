"""Auth URL patterns — unified auth flow, token verification, logout, session status."""

from django.urls import path

from auth_app import views

urlpatterns = [
    # Unified auth entry point (handles both login and registration)
    path("login", views.auth_view, name="auth"),
    # Token verification + session creation
    path("auth/verify", views.verify_magic_link, name="verify-magic-link"),
    # Logout
    path("logout", views.logout_view, name="logout"),
    # Session status API for timeout warning
    path("api/session-status", views.session_status, name="session-status"),
]
