"""
Recurring rules views — page handlers for /recurring*.

Like Laravel's RecurringRuleController — handles the list page, create form,
confirm/skip pending rules, and delete. All HTMX mutations return the
_rule_list.html partial which swaps into #recurring-list.

HTMX pattern: form submits target #recurring-list with innerHTML swap.
Success returns the updated rule list partial. Errors return inline HTML.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.services import AccountService
from categories.models import Category
from core.decorators import inject_service
from core.htmx import success_html
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_none
from recurring.services import RecurringService
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def _get_categories(request: AuthenticatedRequest) -> list[dict[str, Any]]:
    """Fetch categories for the form dropdown, grouped by type.

    Returns all non-archived categories with type info for optgroup rendering.
    """
    usage_sq = Subquery(
        Transaction.objects.filter(category_id=OuterRef("id"))
        .values("category_id")
        .annotate(cnt=Count("id"))
        .values("cnt")[:1]
    )
    qs = (
        Category.objects.for_user(request.user_id)
        .filter(is_archived=False)
        .annotate(
            usage_count=Coalesce(usage_sq, Value(0)),
            name_en=KeyTextTransform("en", "name"),
        )
        .order_by("-usage_count", "name_en")
        .values("id", "name", "type", "icon")
    )
    return [
        {
            "id": str(row["id"]),
            "name": row["name"].get("en", "")
            if isinstance(row["name"], dict)
            else row["name"],
            "type": row["type"],
            "icon": row["icon"],
        }
        for row in qs
    ]


@inject_service(RecurringService)
def _render_rule_list(
    request: AuthenticatedRequest, svc: RecurringService
) -> HttpResponse:
    """Render the _rule_list.html partial for HTMX swap."""
    rules = svc.get_all()
    rule_views = [svc.rule_to_view(r) for r in rules]
    return render(request, "recurring/_rule_list.html", {"rules": rule_views})


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------


@inject_service(RecurringService)
@general_rate
@require_http_methods(["GET"])
def recurring_calendar(
    request: AuthenticatedRequest, svc: RecurringService
) -> HttpResponse:
    """GET /recurring/calendar - monthly view of upcoming recurring transactions."""
    year_str = request.GET.get("year", "")
    month_str = request.GET.get("month", "")
    now = datetime.now(request.tz)
    year = int(year_str) if year_str.isdigit() else now.year
    month = int(month_str) if month_str.isdigit() else now.month

    # Clamp month/year
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    occurrences = svc.get_calendar_data(year, month)

    today_date = now.date()

    # Group by day; mark occurrences due on or before today as confirmable
    calendar_days: dict[int, list[dict[str, Any]]] = {}
    for occ in occurrences:
        day = occ["day"]
        if day not in calendar_days:
            calendar_days[day] = []
        occ["is_due"] = occ["due_date"] <= today_date
        calendar_days[day].append(occ)

    import calendar

    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    month_days = cal.monthdayscalendar(year, month)

    month_name = datetime(year, month, 1).strftime("%B")

    # Navigation
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year += 1

    logger.info("page viewed: recurring-calendar, year=%d month=%d", year, month)
    return render(
        request,
        "recurring/calendar.html",
        {
            "calendar_days": calendar_days,
            "month_days": month_days,
            "year": year,
            "month": month,
            "month_name": month_name,
            "prev_month": prev_month,
            "prev_year": prev_year,
            "next_month": next_month,
            "next_year": next_year,
            "today": now.date(),
            "active_tab": "more",
        },
    )


@inject_service(RecurringService)
@general_rate
@require_http_methods(["GET"])
def recurring_page(
    request: AuthenticatedRequest, svc: RecurringService
) -> HttpResponse:
    """GET /recurring — recurring rules page with pending, form, and active list."""
    logger.info("page viewed: recurring, user=%s", request.user_email)

    rules = svc.get_all()
    pending = svc.get_due_pending()

    rule_views = [svc.rule_to_view(r) for r in rules]
    pending_views = [svc.rule_to_view(r) for r in pending]

    accounts = AccountService(request.user_id, request.tz).get_for_dropdown()
    categories = _get_categories(request)

    return render(
        request,
        "recurring/recurring.html",
        {
            "rules": rule_views,
            "pending_rules": pending_views,
            "accounts": accounts,
            "categories": categories,
            "today": datetime.now(request.tz).date(),
            "active_tab": "more",
        },
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


_FREQUENCY_LABELS = {
    "weekly": "weekly",
    "biweekly": "bi-weekly",
    "monthly": "monthly",
    "quarterly": "quarterly",
    "yearly": "yearly",
}


def _build_summary_line(rule_view: dict[str, Any]) -> str:
    """Build the success-sheet summary line for a freshly-created rule.

    Format: "[Type: ]{amount_display} — {note or category} — {frequency}"
    Type prefix is shown only when type ≠ expense.
    """
    tmpl = rule_view.get("template_transaction") or {}
    amount_display = rule_view.get("amount_display") or ""
    note = (tmpl.get("note") or "").strip()
    descriptor = note or rule_view.get("category_name") or ""
    if not descriptor and rule_view.get("is_transfer"):
        src = rule_view.get("source_account_name") or ""
        dst = rule_view.get("counter_account_name") or ""
        descriptor = f"{src} → {dst}".strip(" →")
    frequency_label = _FREQUENCY_LABELS.get(rule_view.get("frequency", ""), "")

    parts = [amount_display]
    if descriptor:
        parts.append(descriptor)
    if frequency_label:
        parts.append(frequency_label)
    summary = " — ".join(p for p in parts if p)

    type_str = tmpl.get("type", "expense")
    if type_str and type_str != "expense":
        return f"{type_str.capitalize()}: {summary}"
    return summary


@inject_service(RecurringService)
@general_rate
@require_http_methods(["POST"])
def recurring_add(request: AuthenticatedRequest, svc: RecurringService) -> HttpResponse:
    """POST /recurring/add — create new recurring rule.

    On success returns the success sheet (replaces #recurring-form-container)
    plus an OOB swap that refreshes #recurring-list.
    """
    # Parse next_due_date
    next_due_str = request.POST.get("next_due_date", "")
    next_due = None
    if next_due_str:
        try:
            next_due = datetime.strptime(next_due_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    try:
        template = svc.build_template_transaction(request.POST)
        rule = svc.create(
            {
                "template_transaction": template,
                "frequency": request.POST.get("frequency", ""),
                "next_due_date": next_due,
                "auto_confirm": request.POST.get("auto_confirm") == "true",
            }
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{e}</div>',
            status=400,
        )

    rule_view = svc.rule_to_view(rule)
    summary_line = _build_summary_line(rule_view)

    # Sticky values for "Add another" — carry over account/frequency/auto_confirm
    sticky = {
        "account_id": template.get("account_id", ""),
        "frequency": rule.frequency,
        "auto_confirm": rule.auto_confirm,
    }

    rules = svc.get_all()
    rules_for_oob = [svc.rule_to_view(r) for r in rules]

    return render(
        request,
        "recurring/_create_success.html",
        {
            "rule": rule_view,
            "summary_line": summary_line,
            "sticky": sticky,
            "rules_for_oob": rules_for_oob,
        },
    )


@inject_service(RecurringService)
@general_rate
@require_http_methods(["GET"])
def recurring_form(
    request: AuthenticatedRequest, svc: RecurringService
) -> HttpResponse:
    """GET /recurring/form — return the create-rule form partial.

    Optional query params for sticky prefill: account_id, frequency, auto_confirm.
    Used by the success sheet's "Done" (no params → blank form) and
    "Add another" (params → sticky prefill) buttons.
    """
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown()
    categories = _get_categories(request)
    sticky = {
        "account_id": request.GET.get("account_id", ""),
        "frequency": request.GET.get("frequency", ""),
        "auto_confirm": request.GET.get("auto_confirm") == "true",
    }
    return render(
        request,
        "recurring/_form.html",
        {
            "accounts": accounts,
            "categories": categories,
            "today": datetime.now(request.tz).date(),
            "sticky": sticky,
        },
    )


# ---------------------------------------------------------------------------
# Confirm / Skip / Delete
# ---------------------------------------------------------------------------


@inject_service(RecurringService)
@general_rate
@require_http_methods(["GET"])
def recurring_confirm_form(
    request: AuthenticatedRequest, svc: RecurringService, rule_id: UUID
) -> HttpResponse:
    """GET /recurring/{id}/confirm — load confirmation sheet partial."""
    rule = svc.get_by_id(str(rule_id))
    if not rule:
        return HttpResponse("Not found", status=404)

    rule_view = svc.rule_to_view(rule)
    accounts = AccountService(request.user_id, request.tz).get_for_dropdown()
    categories = _get_categories(request)

    return render(
        request,
        "recurring/_confirm_form.html",
        {
            "rule": rule_view,
            "accounts": accounts,
            "categories": categories,
            "today": datetime.now(request.tz).date(),
        },
    )


@inject_service(RecurringService)
@general_rate
@require_http_methods(["POST"])
def recurring_confirm(
    request: AuthenticatedRequest, svc: RecurringService, rule_id: UUID
) -> HttpResponse:
    """POST /recurring/{id}/confirm — confirm pending rule, create transaction.

    Supports optional overrides: actual_amount, account_id, category_id, note, date.
    """
    overrides: dict[str, Any] = {}

    # Extract amount
    amount_raw = request.POST.get("amount") or request.POST.get("actual_amount")
    if amount_raw:
        amount = parse_float_or_none(amount_raw)
        if amount is None:
            return HttpResponse("Amount must be a number", status=400)
        overrides["amount"] = amount

    # Extract other fields
    if "account_id" in request.POST:
        overrides["account_id"] = request.POST.get("account_id")
    if "category_id" in request.POST:
        overrides["category_id"] = request.POST.get("category_id")
    if "note" in request.POST:
        overrides["note"] = request.POST.get("note")
    if "date" in request.POST:
        overrides["date"] = request.POST.get("date")
    if "counter_account_id" in request.POST:
        overrides["counter_account_id"] = request.POST.get("counter_account_id")

    try:
        svc.confirm(str(rule_id), overrides=overrides)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    # If it's a sheet submission, return success toast
    if request.headers.get("HX-Target") == "recurring-calendar-list":
        # We need to refresh the calendar list, so we might want to return the whole list
        # but for individual row confirmation, returning empty or toast is enough if we use OOB
        # However, the current calendar.html targets #recurring-calendar-list.
        # If we target the row, we can just remove it.
        return HttpResponse(success_html("Confirmed!"))

    return _render_rule_list(request)


@inject_service(RecurringService)
@general_rate
@require_http_methods(["POST"])
def recurring_confirm_all(
    request: AuthenticatedRequest, svc: RecurringService
) -> HttpResponse:
    """POST /recurring/confirm-all — confirm all due rules for a specific month."""
    year_str = request.POST.get("year", "")
    month_str = request.POST.get("month", "")

    year = int(year_str) if year_str.isdigit() else None
    month = int(month_str) if month_str.isdigit() else None

    count = svc.confirm_all(year=year, month=month)
    return HttpResponse(success_html(f"Confirmed {count} transactions!"))


@inject_service(RecurringService)
@general_rate
@require_http_methods(["POST"])
def recurring_skip(
    request: AuthenticatedRequest, svc: RecurringService, rule_id: UUID
) -> HttpResponse:
    """POST /recurring/{id}/skip — skip pending rule, advance due date."""
    try:
        svc.skip(str(rule_id))
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    return _render_rule_list(request)


@inject_service(RecurringService)
@general_rate
@require_http_methods(["DELETE"])
def recurring_delete(
    request: AuthenticatedRequest, svc: RecurringService, rule_id: UUID
) -> HttpResponse:
    """DELETE /recurring/{id} — delete recurring rule."""
    svc.delete(str(rule_id))
    return _render_rule_list(request)
