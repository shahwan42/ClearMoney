"""
Push notification API URL patterns.

Maps /api/push/* endpoints to JSON view functions.
These are called by the browser's push.js for notification management.
"""

from django.urls import path

from push import views

urlpatterns = [
    path("api/push/vapid-key", views.vapid_key, name="push-vapid-key"),
    path("api/push/subscribe", views.subscribe, name="push-subscribe"),
    path("api/push/check", views.check_notifications, name="push-check"),
]
