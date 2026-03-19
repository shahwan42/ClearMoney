"""
Context processors — add shared variables to all template contexts.

Like Laravel's view()->share() or Django's standard context processors.
These run on every template render and inject common data.
"""

from django.http import HttpRequest


def active_tab(request: HttpRequest) -> dict[str, str]:
    """Determine which bottom nav tab is active based on the URL path."""
    tab_map = {
        "/settings": "more",
        "/export": "more",
        "/reports": "reports",
    }
    # Root path is the dashboard (home tab)
    if request.path == "/":
        return {"active_tab": "home"}
    for prefix, tab in tab_map.items():
        if request.path.startswith(prefix):
            return {"active_tab": tab}
    return {"active_tab": ""}
