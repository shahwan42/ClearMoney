"""
Investment views — page handlers for /investments*.

Port of Go's PageHandler investment methods (pages.go:2296–2366).
Like Laravel's InvestmentController — handles list, add, update price, delete.

All forms use HTMX (hx-post, hx-delete) with htmx_redirect after mutations.
"""

import logging
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.htmx import htmx_redirect
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from investments.services import InvestmentService

logger = logging.getLogger(__name__)


def _svc(request: AuthenticatedRequest) -> InvestmentService:
    """Create an InvestmentService for the authenticated user."""
    return InvestmentService(request.user_id, request.tz)


def _parse_float(value: str) -> float:
    """Parse a form value to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


@general_rate
@require_http_methods(["GET"])
def investments_page(request: AuthenticatedRequest) -> HttpResponse:
    """GET /investments — render the investment portfolio page.

    Port of Go's PageHandler.Investments (pages.go:2296).
    """
    logger.info("page viewed: investments, user=%s", request.user_email)
    svc = _svc(request)
    investments = svc.get_all()
    total_valuation = svc.get_total_valuation()

    return render(
        request,
        "investments/investments.html",
        {
            "investments": investments,
            "total_valuation": total_valuation,
            "active_tab": "more",
        },
    )


@general_rate
@require_http_methods(["POST"])
def investment_add(request: AuthenticatedRequest) -> HttpResponse:
    """POST /investments/add — create a new investment holding.

    Port of Go's PageHandler.InvestmentAdd (pages.go:2316).
    """
    svc = _svc(request)
    try:
        svc.create(
            {
                "platform": request.POST.get("platform", ""),
                "fund_name": request.POST.get("fund_name", ""),
                "units": _parse_float(request.POST.get("units", "")),
                "unit_price": _parse_float(request.POST.get("unit_price", "")),
                "currency": request.POST.get("currency", ""),
            }
        )
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, "/investments")


@general_rate
@require_http_methods(["POST"])
def investment_update(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """POST /investments/<id>/update — update the unit price (NAV).

    Port of Go's PageHandler.InvestmentUpdateValuation (pages.go:2340).
    """
    svc = _svc(request)
    unit_price = _parse_float(request.POST.get("unit_price", ""))

    try:
        svc.update_valuation(str(id), unit_price)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    return htmx_redirect(request, "/investments")


@general_rate
@require_http_methods(["DELETE"])
def investment_delete(request: AuthenticatedRequest, id: UUID) -> HttpResponse:
    """DELETE /investments/<id>/delete — remove an investment holding.

    Port of Go's PageHandler.InvestmentDelete (pages.go:2356).
    """
    svc = _svc(request)
    try:
        svc.delete(str(id))
    except Exception:
        logger.exception("failed to delete investment id=%s", id)
        return HttpResponse("Failed to delete investment", status=500)

    return htmx_redirect(request, "/investments")
