"""
Budget views — page handlers for /budgets/*.

Like Laravel's BudgetController — handles the budget management page,
creation form, and deletion.

All three routes use standard POST forms (not HTMX), with 302 redirects
after mutations.
"""

import logging

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from budgets.services import BudgetService
from core.models import Category
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest

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
    categories = Category.objects.filter(
        user_id=request.user_id, type="expense"
    ).order_by("name")

    return render(
        request,
        "budgets/budgets.html",
        {
            "budgets": budgets,
            "categories": categories,
            "active_tab": "more",
        },
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
