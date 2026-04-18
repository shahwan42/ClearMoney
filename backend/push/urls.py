"""
Push notification URL patterns.

API endpoints (/api/push/*) — JSON, called by browser push.js.
Notification center (/notifications/*) — HTML pages and HTMX fragments.
"""

from django.urls import path

from push import views

urlpatterns = [
    # JSON API
    path("api/push/vapid-key", views.vapid_key, name="push-vapid-key"),
    path("api/push/subscribe", views.subscribe, name="push-subscribe"),
    path("api/push/check", views.check_notifications, name="push-check"),
    # Notification center HTML
    path("notifications/badge", views.notification_badge, name="notifications-badge"),
    path("notifications", views.notifications_page, name="notifications-list"),
    path(
        "notifications/<str:notification_id>/read",
        views.mark_read,
        name="notifications-mark-read",
    ),
    path(
        "notifications/mark-all-read",
        views.mark_all_read,
        name="notifications-mark-all-read",
    ),
]
