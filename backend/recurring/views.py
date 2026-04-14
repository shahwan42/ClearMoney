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

from accounts.models import Account
from accounts.services import AccountService
from categories.models import Category
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from recurring.services import RecurringService
from transactions.models import Transaction

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> RecurringService:
    """Create a RecurringService for the authenticated user."""
    return RecurringService(request.user_id, request.tz)


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


def _render_rule_list(request: AuthenticatedRequest) -> HttpResponse:
    """Render the _rule_list.html partial for HTMX swap."""
    svc = _svc(request)
    rules = svc.get_all()
    rule_views = [svc.rule_to_view(r) for r in rules]
    return render(request, "recurring/_rule_list.html", {"rules": rule_views})


def _lookup_account_currency(user_id: str, account_id: str) -> str:
    """Look up an account's currency. Returns 'EGP' as fallback."""
    return (
        Account.objects.for_user(user_id)
        .filter(id=account_id)
        .values_list("currency", flat=True)
        .first()
        or "EGP"
    )


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["GET"])
def recurring_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /recurring — recurring rules page with pending, form, and active list."""
    logger.info("page viewed: recurring, user=%s", request.user_email)
    svc = _svc(request)

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


@general_rate
@require_http_methods(["POST"])
def recurring_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /recurring/add — create new recurring rule.

    Parses form, looks up account currency, builds template JSON,
    creates rule, returns updated rule list partial.
    """
    svc = _svc(request)

    # Parse form fields
    tx_type = request.POST.get("type", "expense")
    amount_str = request.POST.get("amount", "")
    account_id = request.POST.get("account_id", "")
    category_id = request.POST.get("category_id", "") or None
    note = request.POST.get("note", "") or None
    frequency = request.POST.get("frequency", "")
    next_due_str = request.POST.get("next_due_date", "")
    auto_confirm = request.POST.get("auto_confirm") == "true"

    # Parse amount
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        return HttpResponse(
            '<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">'
            "Amount is required</div>",
            status=400,
        )

    # Look up account currency (server-side override, never trust form)
    currency = _lookup_account_currency(request.user_id, account_id)

    # Build template_transaction JSONB
    if tx_type == "transfer":
        counter_account_id = request.POST.get("counter_account_id", "")
        if not counter_account_id:
            return HttpResponse(
                '<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">'
                "Destination account is required for transfers</div>",
                status=400,
            )
        if counter_account_id == account_id:
            return HttpResponse(
                '<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">'
                "Source and destination accounts must be different</div>",
                status=400,
            )

        template: dict[str, Any] = {
            "type": "transfer",
            "amount": amount,
            "currency": currency,
            "account_id": account_id,
            "counter_account_id": counter_account_id,
        }
        if note:
            template["note"] = note

        # Parse optional fee
        fee_str = request.POST.get("fee_amount", "")
        if fee_str:
            try:
                fee_amount = float(fee_str)
                if fee_amount > 0:
                    template["fee_amount"] = fee_amount
            except (ValueError, TypeError):
                pass
    else:
        template = {
            "type": tx_type,
            "amount": amount,
            "currency": currency,
            "account_id": account_id,
        }
        if category_id:
            template["category_id"] = category_id
        if note:
            template["note"] = note

    # Parse next_due_date
    next_due = None
    if next_due_str:
        try:
            next_due = datetime.strptime(next_due_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    try:
        svc.create(
            {
                "template_transaction": template,
                "frequency": frequency,
                "next_due_date": next_due,
                "auto_confirm": auto_confirm,
            }
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{e}</div>',
            status=400,
        )

    return _render_rule_list(request)


# ---------------------------------------------------------------------------
# Confirm / Skip / Delete
# ---------------------------------------------------------------------------


@general_rate
@require_http_methods(["POST"])
def recurring_confirm(request: AuthenticatedRequest, rule_id: UUID) -> HttpResponse:
    """POST /recurring/{id}/confirm — confirm pending rule, create transaction."""
    svc = _svc(request)
    try:
        svc.confirm(str(rule_id))
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    return _render_rule_list(request)


@general_rate
@require_http_methods(["POST"])
def recurring_skip(request: AuthenticatedRequest, rule_id: UUID) -> HttpResponse:
    """POST /recurring/{id}/skip — skip pending rule, advance due date."""
    svc = _svc(request)
    try:
        svc.skip(str(rule_id))
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    return _render_rule_list(request)


@general_rate
@require_http_methods(["DELETE"])
def recurring_delete(request: AuthenticatedRequest, rule_id: UUID) -> HttpResponse:
    """DELETE /recurring/{id} — delete recurring rule."""
    svc = _svc(request)
    svc.delete(str(rule_id))
    return _render_rule_list(request)
