"""
Budget views — page handlers for /budgets/*.

Like Laravel's BudgetController — handles the budget management page,
creation form, and deletion.

All three routes use standard POST forms (not HTMX), with 302 redirects
after mutations.
"""

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from budgets.services import BudgetService
from categories.models import Category
from core.decorators import inject_service
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from transactions.models import Transaction as TransactionModel

logger = logging.getLogger(__name__)


@inject_service(BudgetService)
@general_rate
@require_http_methods(["GET"])
def budgets_page(request: AuthenticatedRequest, svc: BudgetService) -> HttpResponse:
    """GET /budgets — budget management page with creation form and active budget list."""
    logger.info("page viewed: budgets, user=%s", request.user_email)
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


@inject_service(BudgetService)
@general_rate
@require_http_methods(["GET"])
def budget_detail(
    request: AuthenticatedRequest, svc: BudgetService, budget_id: str
) -> HttpResponse:
    """GET /budgets/<id>/ — budget detail with contributing transactions."""
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


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def budget_copy_last_month(
    request: AuthenticatedRequest, svc: BudgetService
) -> HttpResponse:
    """POST /budgets/copy-last-month — template new budgets from last month's spending."""
    created = svc.copy_last_month_budgets()
    logger.info(
        "budgets copied from last month: count=%d user=%s", created, request.user_id
    )
    return redirect("budgets")


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def budget_add(request: AuthenticatedRequest, svc: BudgetService) -> HttpResponse:
    """POST /budgets/add — create a new budget from form data.

    Validates input, creates budget, and redirects back to /budgets.
    """
    category_id = request.POST.get("category_id", "")
    monthly_limit_str = request.POST.get("monthly_limit", "")
    currency = request.POST.get("currency", "EGP")
    rollover_enabled = request.POST.get("rollover_enabled") == "on"
    max_rollover_str = request.POST.get("max_rollover", "")

    try:
        monthly_limit = float(monthly_limit_str) if monthly_limit_str else 0.0
        max_rollover = float(max_rollover_str) if max_rollover_str else None
    except ValueError:
        return HttpResponse("Invalid monthly limit or max rollover", status=400)

    try:
        with transaction.atomic():
            svc.create(
                category_id,
                monthly_limit,
                currency,
                rollover_enabled=rollover_enabled,
                max_rollover=max_rollover,
            )
    except ValueError as e:
        return HttpResponse(str(e), status=400)
    except IntegrityError:
        return HttpResponse(
            "A budget already exists for this category and currency", status=400
        )

    return redirect("budgets")


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def budget_edit(
    request: AuthenticatedRequest, svc: BudgetService, budget_id: str
) -> HttpResponse:
    """POST /budgets/{id}/edit — update a budget's monthly limit."""
    monthly_limit_str = request.POST.get("monthly_limit", "")
    rollover_enabled = request.POST.get("rollover_enabled") == "on"
    max_rollover_str = request.POST.get("max_rollover", "")

    try:
        monthly_limit = float(monthly_limit_str) if monthly_limit_str else None
        max_rollover = float(max_rollover_str) if max_rollover_str else None
    except ValueError:
        if request.htmx:
            # We need the budget to re-render the card with error
            budgets = svc.get_all_with_spending()
            budget = next((b for b in budgets if b.id == str(budget_id)), None)
            return render(request, "budgets/_budget_card.html", {"budget": budget, "error": "Invalid amount"})
        return HttpResponse("Invalid monthly limit or max rollover", status=400)

    try:
        with transaction.atomic():
            svc.update(
                str(budget_id),
                monthly_limit=monthly_limit,
                rollover_enabled=rollover_enabled,
                max_rollover=max_rollover,
            )
    except ValueError as e:
        if request.htmx:
            budgets = svc.get_all_with_spending()
            budget = next((b for b in budgets if b.id == str(budget_id)), None)
            return render(request, "budgets/_budget_card.html", {"budget": budget, "error": str(e)})
        return HttpResponse(str(e), status=400)
    except ObjectDoesNotExist:
        return HttpResponse("Budget not found", status=404)

    if request.htmx:
        budgets = svc.get_all_with_spending()
        budget = next((b for b in budgets if b.id == str(budget_id)), None)
        return render(request, "budgets/_budget_card.html", {"budget": budget, "saved": True})

    return redirect("budgets")


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def total_budget_set(request: AuthenticatedRequest, svc: BudgetService) -> HttpResponse:
    """POST /budgets/total/set — create or update the total monthly budget."""
    monthly_limit_str = request.POST.get("monthly_limit", "")
    currency = request.POST.get("currency", "EGP")

    try:
        from decimal import Decimal, InvalidOperation

        monthly_limit = Decimal(monthly_limit_str) if monthly_limit_str else Decimal(0)
    except (ValueError, InvalidOperation):
        if request.htmx:
            total_budget = svc.get_total_budget(currency)
            return render(request, "budgets/_total_budget_card.html", {"total_budget": total_budget, "error": "Invalid amount"})
        return HttpResponse("Invalid monthly limit", status=400)

    try:
        svc.set_total_budget(monthly_limit, currency)
    except ValueError as e:
        if request.htmx:
            total_budget = svc.get_total_budget(currency)
            return render(request, "budgets/_total_budget_card.html", {"total_budget": total_budget, "error": str(e)})
        return HttpResponse(str(e), status=400)

    if request.htmx:
        total_budget = svc.get_total_budget(currency)
        return render(request, "budgets/_total_budget_card.html", {"total_budget": total_budget, "saved": True})

    return redirect("budgets")


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def total_budget_delete(
    request: AuthenticatedRequest, svc: BudgetService
) -> HttpResponse:
    """POST /budgets/total/delete — delete the total monthly budget."""
    currency = request.POST.get("currency", "EGP")
    svc.delete_total_budget(currency)
    
    if request.htmx:
        return render(request, "budgets/_total_budget_card.html", {"total_budget": None})
        
    return redirect("budgets")


@inject_service(BudgetService)
@general_rate
@require_http_methods(["POST"])
def budget_delete(
    request: AuthenticatedRequest, svc: BudgetService, budget_id: str
) -> HttpResponse:
    """POST /budgets/{id}/delete — delete a budget.

    Deletes the budget and redirects back to /budgets.
    """
    if not svc.delete(str(budget_id)):
        logger.warning(
            "budget delete failed: not found id=%s user=%s",
            budget_id,
            request.user_id,
        )
    return redirect("budgets")
