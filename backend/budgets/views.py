"""
Budget views — page handlers for /budgets/*.

Like Laravel's BudgetController — handles the budget management page,
creation form, and deletion.

All three routes use standard POST forms (not HTMX), with 302 redirects
after mutations.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from budgets.services import BudgetService
from categories.models import Category
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from transactions.models import Transaction as TransactionModel

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> BudgetService:
    """Create a BudgetService for the authenticated user."""
    return BudgetService(request.user_id, request.tz)


@general_rate
@require_http_methods(["GET"])
def budgets_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /budgets — budget management page with creation form and active budget list."""
    logger.info("page viewed: budgets, user=%s", request.user_email)
    svc = _svc(request)
    budgets = svc.get_all_with_spending()
    usage_sq = Subquery(
        TransactionModel.objects.filter(category_id=OuterRef("id"))
        .values("category_id")
        .annotate(cnt=Count("id"))
        .values("cnt")[:1]
    )
    categories = (
        Category.objects.filter(
            user_id=request.user_id, type="expense", is_archived=False
        )
        .annotate(
            usage_count=Coalesce(usage_sq, Value(0)),
            name_en=KeyTextTransform("en", "name"),
        )
        .order_by("-usage_count", "name_en")
    )
    total_budget = svc.get_total_budget("EGP")

    return render(
        request,
        "budgets/budgets.html",
        {
            "budgets": budgets,
            "categories": categories,
            "total_budget": total_budget,
            "active_tab": "more",
        },
    )


@general_rate
@require_http_methods(["GET"])
def budget_detail(request: AuthenticatedRequest, budget_id: str) -> HttpResponse:
    """GET /budgets/<id>/ — budget detail with contributing transactions."""
    svc = _svc(request)
    try:
        budget = svc.get_budget_with_transactions(str(budget_id))
    except Exception:
        from django.http import Http404

        raise Http404

    return render(
        request,
        "budgets/budget_detail.html",
        {"budget": budget, "active_tab": "more"},
    )


@general_rate
@require_http_methods(["POST"])
def budget_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /budgets/add — create a new budget from form data.

    Validates input, creates budget, and redirects back to /budgets.
    """
    svc = _svc(request)
    category_id = request.POST.get("category_id", "")
    monthly_limit_str = request.POST.get("monthly_limit", "")
    currency = request.POST.get("currency", "EGP")

    try:
        monthly_limit = float(monthly_limit_str) if monthly_limit_str else 0.0
    except ValueError:
        return HttpResponse("Invalid monthly limit", status=400)

    try:
        with transaction.atomic():
            svc.create(category_id, monthly_limit, currency)
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    except IntegrityError:
        return HttpResponse(
            "A budget already exists for this category and currency", status=400
        )

    return redirect("budgets")


@general_rate
@require_http_methods(["POST"])
def budget_edit(request: AuthenticatedRequest, budget_id: str) -> HttpResponse:
    """POST /budgets/{id}/edit — update a budget's monthly limit."""
    svc = _svc(request)
    monthly_limit_str = request.POST.get("monthly_limit", "")

    try:
        monthly_limit = float(monthly_limit_str) if monthly_limit_str else 0.0
    except ValueError:
        return HttpResponse("Invalid monthly limit", status=400)

    try:
        with transaction.atomic():
            svc.update(str(budget_id), monthly_limit)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("budgets")


@general_rate
@require_http_methods(["POST"])
def total_budget_set(request: AuthenticatedRequest) -> HttpResponse:
    """POST /budgets/total/set — create or update the total monthly budget."""
    svc = _svc(request)
    monthly_limit_str = request.POST.get("monthly_limit", "")
    currency = request.POST.get("currency", "EGP")

    try:
        from decimal import Decimal, InvalidOperation

        monthly_limit = Decimal(monthly_limit_str) if monthly_limit_str else Decimal(0)
    except (ValueError, InvalidOperation):
        return HttpResponse("Invalid monthly limit", status=400)

    try:
        svc.set_total_budget(monthly_limit, currency)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return redirect("budgets")


@general_rate
@require_http_methods(["POST"])
def total_budget_delete(request: AuthenticatedRequest) -> HttpResponse:
    """POST /budgets/total/delete — delete the total monthly budget."""
    svc = _svc(request)
    currency = request.POST.get("currency", "EGP")
    svc.delete_total_budget(currency)
    return redirect("budgets")


@general_rate
@require_http_methods(["POST"])
def budget_delete(request: AuthenticatedRequest, budget_id: str) -> HttpResponse:
    """POST /budgets/{id}/delete — delete a budget.

    Deletes the budget and redirects back to /budgets.
    """
    svc = _svc(request)
    if not svc.delete(str(budget_id)):
        logger.warning(
            "budget delete failed: not found id=%s user=%s",
            budget_id,
            request.user_id,
        )
    return redirect("budgets")
