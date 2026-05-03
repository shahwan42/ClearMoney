"""
Push notification views — JSON API endpoints and notification center HTML views.

API endpoints (JSON):
1. GET  /api/push/vapid-key     — return VAPID public key for Push API subscription
2. POST /api/push/subscribe     — accept browser push subscription (acknowledged only)
3. GET  /api/push/check         — poll for pending notifications (DB-backed, priority-sorted)
4. POST /api/push/dismiss/<id>  — mark a notification as read (cross-device dismiss)

HTML endpoints:
5. GET  /notifications/badge    — HTMX badge fragment (unread count)
6. GET  /notifications           — notifications list page
7. POST /notifications/<id>/read — mark single notification as read
8. POST /notifications/mark-all-read — mark all notifications as read
"""

import json
import logging
import os
import re
import uuid
from datetime import date, datetime

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from push.models import Notification
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


def _tag_priority(tag: str, today: date) -> int:
    """Return sort priority for a notification tag (lower = higher priority)."""
    if tag.startswith("cc-due-"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})$", tag)
        if m:
            try:
                days = (date.fromisoformat(m.group(1)) - today).days
                return 0 if days <= 1 else 1
            except ValueError:
                pass
        return 0
    if tag.startswith("health-"):
        return 2
    if tag.startswith("budget-exceeded-"):
        return 3
    if tag.startswith("budget-warning-"):
        return 4
    if tag.startswith("recurring-"):
        return 5
    return 6


@general_rate
def check_notifications(request: AuthenticatedRequest) -> JsonResponse:
    """Poll for pending notifications.

    GET /api/push/check

    Syncs notification state to DB via generate_and_persist(), then returns
    unread notifications sorted by priority. Each object includes an `id` field
    so the browser can POST to /api/push/dismiss/<id> to mark as read.
    """
    svc = NotificationService(request.user_id, request.tz)
    svc.generate_and_persist()

    today = datetime.now(request.tz).date()
    unread = list(
        Notification.objects.for_user(request.user_id)
        .filter(is_read=False)
        .values("id", "title", "body", "url", "tag")
    )
    unread.sort(key=lambda n: _tag_priority(n["tag"], today))
    for n in unread:
        n["id"] = str(n["id"])

    return JsonResponse(unread, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
@general_rate
def dismiss_notification(
    request: AuthenticatedRequest, notification_id: str
) -> JsonResponse:
    """Mark a notification as read (cross-device banner dismiss).

    POST /api/push/dismiss/<uuid>

    Returns {"status": "ok"} on success.
    """
    try:
        uuid.UUID(notification_id)
    except ValueError:
        raise Http404

    notif = get_object_or_404(Notification, id=notification_id, user_id=request.user_id)
    notif.is_read = True
    notif.save(update_fields=["is_read", "updated_at"])
    return JsonResponse({"status": "ok"})


def notification_badge(request: AuthenticatedRequest) -> HttpResponse:
    """HTMX fragment: unread notification count badge.

    GET /notifications/badge

    Returns an HTML fragment used by the header bell icon to show the
    unread count. Polled every 60 seconds via hx-trigger="load, every 60s".
    """
    count = Notification.objects.for_user(request.user_id).filter(is_read=False).count()
    return render(
        request,
        "push/_badge.html",
        {"unread_notification_count": count},
    )


def notifications_page(request: AuthenticatedRequest) -> HttpResponse:
    """Notifications list page.

    GET /notifications

    Shows unread notifications first (with visual distinction),
    then read notifications in an "Earlier" section.
    """
    all_notifs = list(Notification.objects.for_user(request.user_id))
    unread = [n for n in all_notifs if not n.is_read]
    read = [n for n in all_notifs if n.is_read]
    return render(
        request,
        "push/notifications.html",
        {
            "unread": unread,
            "read": read,
            "now": timezone.now(),
        },
    )


@require_http_methods(["POST"])
def mark_read(request: AuthenticatedRequest, notification_id: str) -> HttpResponse:
    """Mark a single notification as read and redirect to its action URL.

    POST /notifications/<uuid>/read

    Returns 404 if the notification belongs to a different user.
    Idempotent — already-read notifications still redirect.
    """
    try:
        uuid.UUID(notification_id)
    except ValueError:
        raise Http404

    notif = get_object_or_404(Notification, id=notification_id, user_id=request.user_id)
    notif.is_read = True
    notif.save(update_fields=["is_read", "updated_at"])
    return redirect(notif.url or "/notifications")


@require_http_methods(["POST"])
def mark_all_read(request: AuthenticatedRequest) -> HttpResponse:
    """Mark all unread notifications as read.

    POST /notifications/mark-all-read

    For HTMX requests, re-renders the notifications page fragment.
    For standard requests, redirects to /notifications.
    """
    Notification.objects.for_user(request.user_id).filter(is_read=False).update(
        is_read=True, updated_at=timezone.now()
    )
    if request.headers.get("HX-Request"):
        all_notifs = list(Notification.objects.for_user(request.user_id))
        return render(
            request,
            "push/notifications.html",
            {
                "unread": [],
                "read": all_notifs,
                "now": timezone.now(),
            },
        )
    return redirect("/notifications")
