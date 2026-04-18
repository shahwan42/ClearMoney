"""Context processor — inject unread notification count into every template."""

from django.http import HttpRequest

from push.models import Notification


def unread_notification_count(request: HttpRequest) -> dict[str, int]:
    """Return the unread notification count for the authenticated user.

    Returns an empty dict for unauthenticated requests so the header template
    can conditionally show the badge.
    """
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return {}
    count = Notification.objects.for_user(user_id).filter(is_read=False).count()
    return {"unread_notification_count": count}
