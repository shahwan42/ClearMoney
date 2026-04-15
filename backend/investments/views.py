"""
Investment views — page handlers for /investments*.

Like Laravel's InvestmentController — handles list, add, update price, delete.

All forms use HTMX (hx-post, hx-delete) with htmx_redirect after mutations.
"""

import logging
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.decorators import inject_service
from core.htmx import htmx_redirect, operational_error_response
from core.ratelimit import general_rate
from core.types import AuthenticatedRequest
from core.utils import parse_float_or_zero
from investments.services import InvestmentService

logger = logging.getLogger(__name__)


@inject_service(InvestmentService)
@general_rate
@require_http_methods(["GET"])
def investments_page(
    request: AuthenticatedRequest, svc: InvestmentService
) -> HttpResponse:
    """GET /investments — render the investment portfolio page."""
    logger.info("page viewed: investments, user=%s", request.user_email)
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


@inject_service(InvestmentService)
@general_rate
@require_http_methods(["POST"])
def investment_add(
    request: AuthenticatedRequest, svc: InvestmentService
) -> HttpResponse:
    """POST /investments/add — create a new investment holding."""
    try:
        svc.create(
            {
                "platform": request.POST.get("platform", ""),
                "fund_name": request.POST.get("fund_name", ""),
                "units": parse_float_or_zero(request.POST.get("units", "")),
                "unit_price": parse_float_or_zero(request.POST.get("unit_price", "")),
                "currency": request.POST.get("currency", ""),
            }
        )
    except ValueError as e:
        return operational_error_response(str(e))

    return htmx_redirect(request, "/investments")


@inject_service(InvestmentService)
@general_rate
@require_http_methods(["POST"])
def investment_update(
    request: AuthenticatedRequest, svc: InvestmentService, id: UUID
) -> HttpResponse:
    """POST /investments/<id>/update — update the unit price (NAV)."""
    unit_price = parse_float_or_zero(request.POST.get("unit_price", ""))

    try:
        svc.update_valuation(str(id), unit_price)
    except ValueError as e:
        return operational_error_response(str(e))

    return htmx_redirect(request, "/investments")


@inject_service(InvestmentService)
@general_rate
@require_http_methods(["DELETE"])
def investment_delete(
    request: AuthenticatedRequest, svc: InvestmentService, id: UUID
) -> HttpResponse:
    """DELETE /investments/<id>/delete — remove an investment holding."""
    try:
        svc.delete(str(id))
    except ValueError as e:
        return operational_error_response(str(e))

    return htmx_redirect(request, "/investments")
