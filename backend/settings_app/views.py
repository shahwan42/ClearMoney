"""
Settings views — page handlers for /settings and /export/transactions.

Like Laravel's SettingsController or Django's function-based views.
"""

import csv
import logging
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from auth_app.currency import (
    get_user_display_currency_context,
    get_supported_currencies,
    set_user_active_currencies,
    set_user_selected_display_currency,
)
from auth_app.models import User
from categories.services import CategoryService
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from transactions.models import Transaction
from transactions.services import TagService

...
# ---------------------------------------------------------------------------
# Tag Management
# ---------------------------------------------------------------------------


def _tag_svc(request: AuthenticatedRequest) -> TagService:
    """Create a TagService scoped to the authenticated user."""
    return TagService(request.user_id, request.tz)


@general_rate
@require_http_methods(["GET"])
def tags_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /settings/tags - tag management page."""
    svc = _tag_svc(request)
    tags = svc.get_all_with_usage()

    logger.info("page viewed: tags, user=%s", request.user_email)
    return render(
        request,
        "settings_app/tags.html",
        {
            "tags": tags,
        },
    )


@general_rate
@require_http_methods(["POST"])
def tag_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /settings/tags/add - create a new tag."""
    svc = _tag_svc(request)
    name = request.POST.get("name", "")
    color = request.POST.get("color", "#64748b")

    try:
        svc.create(name=name, color=color)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("tags_settings")


@general_rate
@require_http_methods(["POST"])
def tag_update(request: AuthenticatedRequest, tag_id: str) -> HttpResponse:
    """POST /settings/tags/<id>/update - edit name/color."""
    svc = _tag_svc(request)
    name = request.POST.get("name", "")
    color = request.POST.get("color", "")

    try:
        svc.update(str(tag_id), name=name, color=color or None)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("tags_settings")


@general_rate
@require_http_methods(["POST"])
def tag_delete(request: AuthenticatedRequest, tag_id: str) -> HttpResponse:
    """POST /settings/tags/<id>/delete - delete a tag."""
    svc = _tag_svc(request)
    svc.delete(str(tag_id))
    return redirect("tags_settings")


@general_rate
@require_http_methods(["POST"])
def tag_merge(request: AuthenticatedRequest) -> HttpResponse:
    """POST /settings/tags/merge - merge two tags."""
    svc = _tag_svc(request)
    source_id = request.POST.get("source_id", "")
    target_id = request.POST.get("target_id", "")

    try:
        svc.merge(source_id, target_id)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("tags_settings")


logger = logging.getLogger(__name__)


@general_rate
def settings_page(request: AuthenticatedRequest) -> HttpResponse:
    """
    Render the settings page.

    GET /settings — shows dark mode toggle, CSV export form, push
    notifications toggle, quick links, and logout button.

    No server data needed — all interactivity is client-side JS.
    """
    logger.info("page viewed: settings, user=%s", request.user_email)
    display_currency = get_user_display_currency_context(request.user_id)
    return render(
        request,
        "settings_app/settings.html",
        {
            "supported_currencies": get_supported_currencies(),
            "display_currency": display_currency,
            "current_display_currency": display_currency.selected_currency,
        },
    )


@general_rate
@require_http_methods(["POST"])
def set_active_currencies(request: AuthenticatedRequest) -> HttpResponse:
    """Update the user's active currency list."""
    codes = request.POST.getlist("active_currency_codes")
    try:
        set_user_active_currencies(request.user_id, codes)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    logger.info("settings.active_currencies_updated user=%s", request.user_email)
    return redirect("settings")


@general_rate
@require_http_methods(["POST"])
def set_display_currency(request: AuthenticatedRequest) -> HttpResponse:
    """Update the user's selected display currency."""
    next_url = request.POST.get("next", "").strip() or "/settings"
    try:
        set_user_selected_display_currency(
            request.user_id,
            request.POST.get("currency", ""),
        )
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    logger.info("settings.display_currency_updated user=%s", request.user_email)
    return redirect(next_url)


@general_rate
@require_http_methods(["POST"])
def set_language(request: AuthenticatedRequest) -> HttpResponse:
    """
    Update the authenticated user's language preference.

    POST /settings/language — expects 'language' in POST data ("en" or "ar").
    After updating, redirects back to /settings to trigger a full page reload
    so the LanguageMiddleware applies the new lang/dir on the next request.
    """
    lang = request.POST.get("language", "en")
    if lang not in ("en", "ar"):
        logger.warning(
            "set_language: invalid language=%s, user=%s", lang, request.user_email
        )
        return HttpResponse("Invalid language", status=400)

    updated = User.objects.filter(id=request.user_id).update(language=lang)
    if not updated:
        return HttpResponse("User not found", status=404)

    logger.info("set_language: user=%s language=%s", request.user_email, lang)
    return redirect("settings")


@general_rate
def export_transactions(request: AuthenticatedRequest) -> HttpResponse:
    """
    Export transactions as a CSV file download.

    GET /export/transactions?from=2026-01-01&to=2026-03-31

    The Content-Disposition header triggers a browser file download.
    Like Laravel's Response::download() or Django's StreamingHttpResponse.
    """
    user_id = request.user_id
    from_str = request.GET.get("from", "")
    to_str = request.GET.get("to", "")

    # Validate date parameters
    try:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning(
            "export: invalid date params, from=%s, to=%s, user=%s",
            from_str,
            to_str,
            request.user_email,
        )
        return HttpResponse("Invalid 'from' or 'to' date", status=400)

    # Query transactions in date range for this user
    qs = (
        Transaction.objects.for_user(user_id)
        .filter(date__gte=from_date, date__lte=to_date)
        .order_by("-date", "-created_at")
        .values(
            "date",
            "type",
            "amount",
            "currency",
            "account_id",
            "category_id",
            "note",
            "created_at",
        )
    )

    # Build CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f"attachment; filename=transactions_{from_str}_{to_str}.csv"
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "Date",
            "Type",
            "Amount",
            "Currency",
            "Account ID",
            "Category ID",
            "Note",
            "Created At",
        ]
    )

    rows = list(qs)  # evaluate once so len(rows) below doesn't re-query
    for row in rows:
        date_val = row["date"]
        created_at = row["created_at"]
        writer.writerow(
            [
                date_val.strftime("%Y-%m-%d")
                if hasattr(date_val, "strftime")
                else str(date_val),
                row["type"],
                f"{float(row['amount']):.2f}",
                row["currency"],
                str(row["account_id"]),
                str(row["category_id"]) if row["category_id"] else "",
                row["note"] or "",
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at),
            ]
        )

    row_count = len(rows)
    logger.info(
        "export.csv_downloaded: rows=%d, from=%s, to=%s, user=%s",
        row_count,
        from_str,
        to_str,
        request.user_email,
    )
    return response


# ---------------------------------------------------------------------------
# Category Management
# ---------------------------------------------------------------------------


def _cat_svc(request: AuthenticatedRequest) -> CategoryService:
    """Create a CategoryService scoped to the authenticated user."""
    return CategoryService(request.user_id, request.tz)


@general_rate
@require_http_methods(["GET"])
def categories_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /settings/categories — category management page."""
    svc = _cat_svc(request)
    categories = svc.get_all_with_usage()
    archived = svc.get_archived_with_usage()

    logger.info("page viewed: categories, user=%s", request.user_email)
    return render(
        request,
        "settings_app/categories.html",
        {
            "categories": categories,
            "archived": archived,
        },
    )


@general_rate
@require_http_methods(["POST"])
def category_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /settings/categories/add — create a new custom category."""
    svc = _cat_svc(request)
    name = request.POST.get("name", "")
    icon = request.POST.get("icon", "")

    try:
        svc.create(name=name, icon=icon or None)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("categories")


@general_rate
@require_http_methods(["POST"])
def category_update(request: AuthenticatedRequest, cat_id: str) -> HttpResponse:
    """POST /settings/categories/<id>/update — edit name/icon."""
    svc = _cat_svc(request)
    name = request.POST.get("name", "")
    icon = request.POST.get("icon", "")

    try:
        result = svc.update(str(cat_id), name=name, icon=icon or None)
    except ValueError as e:
        msg = str(e)
        if "system" in msg:
            return HttpResponse(msg, status=403)
        return HttpResponse(msg, status=400)

    if not result:
        return HttpResponse("Category not found", status=404)

    return redirect("categories")


@general_rate
@require_http_methods(["POST"])
def category_archive(request: AuthenticatedRequest, cat_id: str) -> HttpResponse:
    """POST /settings/categories/<id>/archive — soft-delete a category."""
    svc = _cat_svc(request)
    try:
        svc.archive(str(cat_id))
    except ObjectDoesNotExist:
        return HttpResponse("Category not found", status=404)
    except ValueError as e:
        msg = str(e)
        if "system" in msg:
            return HttpResponse(msg, status=403)
        return HttpResponse(msg, status=400)

    return redirect("categories")


@general_rate
@require_http_methods(["POST"])
def category_unarchive(request: AuthenticatedRequest, cat_id: str) -> HttpResponse:
    """POST /settings/categories/<id>/unarchive — restore a category."""
    svc = _cat_svc(request)
    svc.unarchive(str(cat_id))
    return redirect("categories")
