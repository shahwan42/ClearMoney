"""
Installment views — page handlers for /installments*.

Port of Go's PageHandler installment methods (pages.go:2368–2440).
Like Laravel's InstallmentController — handles list, add, pay, delete.

All forms use HTMX (hx-post, hx-delete) with htmx_redirect after mutations.
"""

import logging
from datetime import datetime
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.services import AccountService
from core.htmx import htmx_redirect
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_zero
from installments.services import InstallmentService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> InstallmentService:
    """Create an InstallmentService for the authenticated user."""
    return InstallmentService(request.user_id, request.tz)


def _parse_int(value: str) -> int:
    """Parse a form value to int, returning 0 on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


@general_rate
@require_http_methods(["GET"])
def installments_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /installments — render the installment plans page.

    Port of Go's PageHandler.Installments (pages.go:2381).
    Shows create form + list of all plans with progress tracking.
    """
    logger.info("page viewed: installments, user=%s", request.user_email)
    svc = _svc(request)
    plans = svc.get_all()
    accounts = AccountService(request.user_id, request.tz).get_all()
    today = datetime.now(tz=request.tz).date()

    return render(
        request,
        "installments/installments.html",
        {
            "plans": plans,
            "accounts": accounts,
            "today": today,
            "active_tab": "more",
        },
    )


@general_rate
@require_http_methods(["POST"])
def installment_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /installments/add — create a new installment plan.

    Port of Go's PageHandler.InstallmentAdd (pages.go:2393).
    """
    svc = _svc(request)
    try:
        svc.create(
            {
                "description": request.POST.get("description", ""),
                "total_amount": parse_float_or_zero(
                    request.POST.get("total_amount", "")
                ),
                "num_installments": _parse_int(
                    request.POST.get("num_installments", "")
                ),
                "account_id": request.POST.get("account_id", ""),
                "start_date": request.POST.get("start_date", ""),
            }
        )
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, "/installments")


@general_rate
@require_http_methods(["POST"])
def installment_pay(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /installments/<id>/pay — record a payment on an installment plan.

    Port of Go's PageHandler.InstallmentPay (pages.go:2418).
    Creates an expense transaction and decrements remaining installments.
    """
    svc = _svc(request)
    try:
        svc.record_payment(str(id))
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, "/installments")


@general_rate
@require_http_methods(["DELETE"])
def installment_delete(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """DELETE /installments/<id> — remove an installment plan.

    Port of Go's PageHandler.InstallmentDelete (pages.go:2431).
    """
    svc = _svc(request)
    try:
        svc.delete(str(id))
    except Exception:
        logger.exception("failed to delete installment id=%s", id)
        return HttpResponse("Failed to delete installment", status=500)

    return htmx_redirect(request, "/installments")
