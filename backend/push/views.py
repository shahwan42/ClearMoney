"""
Push notification API views — JSON-only endpoints for the service worker.

Three endpoints:
1. GET  /api/push/vapid-key  — return VAPID public key for Push API subscription
2. POST /api/push/subscribe  — accept browser push subscription (acknowledged only)
3. GET  /api/push/check      — poll for pending notifications

No templates — all responses are JSON. The browser's push.js calls these
endpoints to manage push notification state.
"""

import json
import logging
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from push.services import NotificationService

logger = logging.getLogger(__name__)


@general_rate
def vapid_key(request: AuthenticatedRequest) -> JsonResponse:
    """Return the VAPID public key for browser Push API subscription.

    GET /api/push/vapid-key

    The browser needs this key to create a PushSubscription via
    navigator.serviceWorker.pushManager.subscribe().
    """
    return JsonResponse({"publicKey": os.environ.get("VAPID_PUBLIC_KEY", "")})


@csrf_exempt  # JS fetch() API — authenticated via session, rate-limited
@general_rate
def subscribe(request: AuthenticatedRequest) -> JsonResponse:
    """Accept a push subscription from the browser.

    POST /api/push/subscribe

    In a full implementation, this would store the subscription in the database
    for server-initiated push. Currently, we acknowledge receipt — the app uses
    polling via /api/push/check instead of server-push.
    """
    try:
        json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "invalid subscription"}, status=400)

    return JsonResponse({"status": "ok"})


@general_rate
def check_notifications(request: AuthenticatedRequest) -> JsonResponse:
    """Poll for pending notifications.

    GET /api/push/check

    Returns a JSON array of notification objects, each with:
    title, body, url, tag (dedup key).

    The browser's push.js displays these as in-app banners and/or
    browser notifications via the Push API.
    """
    svc = NotificationService(request.user_id, request.tz)
    notifications = svc.get_pending_notifications()

    # safe=False because top-level JSON is an array, not a dict
    return JsonResponse(notifications, safe=False)
