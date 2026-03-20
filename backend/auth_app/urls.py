"""
Auth URL patterns — routes for /login, /register, /auth/verify, /logout.

Each route uses a single view function that dispatches on request.method.
"""

from django.urls import path

from auth_app import views

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("register", views.register_view, name="register"),
    path("auth/verify", views.verify_magic_link, name="verify-magic-link"),
    path("logout", views.logout_view, name="logout"),
]
