"""
Context processors — add shared variables to all template contexts.

Like Laravel's view()->share() or Django's standard context processors.
These run on every template render and inject common data.
"""

from django.http import HttpRequest

from auth_app.currency import (
    get_user_active_currencies,
    get_user_selected_display_currency,
)


def active_tab(request: HttpRequest) -> dict[str, str]:
    """Determine which bottom nav tab is active based on the URL path."""
    tab_map = {
        "/settings": "more",
        "/export": "more",
        "/reports": "reports",
        "/accounts": "accounts",
        "/institutions": "accounts",
    }
    # Root path is the dashboard (home tab)
    if request.path == "/":
        return {"active_tab": "home"}
    for prefix, tab in tab_map.items():
        if request.path.startswith(prefix):
            return {"active_tab": tab}
    return {"active_tab": ""}


def currency_preferences(request: HttpRequest) -> dict[str, object]:
    """Expose active currencies and the selected display currency to templates."""
    user_id = getattr(request, "user_id", "")
    if not user_id:
        return {
            "active_currencies": [],
            "selected_display_currency": "EGP",
        }
    return {
        "active_currencies": get_user_active_currencies(user_id),
        "selected_display_currency": get_user_selected_display_currency(user_id),
    }
