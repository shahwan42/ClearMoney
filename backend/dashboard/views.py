"""
Dashboard views — home page and HTMX partials.

Uses DashboardService to aggregate all data, then renders templates.
Like Laravel's DashboardController or Django's TemplateView.
"""

import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest

from .services import DashboardService
from .services.accounts import get_net_worth_breakdown

logger = logging.getLogger(__name__)


@general_rate
def home(request: AuthenticatedRequest) -> HttpResponse:
    """Dashboard home page. GET /

    Delegates all data assembly to DashboardService.
    """
    logger.info("page viewed: dashboard, user=%s", request.user_email)
    svc = DashboardService(request.user_id, request.tz)
    data = svc.get_dashboard()
    return render(request, "dashboard/home.html", {"data": data})


@general_rate
def recent_transactions_partial(request: AuthenticatedRequest) -> HttpResponse:
    """HTMX partial: recent transactions. GET /partials/recent-transactions

    Returns HTML fragment for the transaction feed.
    """
    logger.info("partial loaded: recent-transactions, user=%s", request.user_email)
    svc = DashboardService(request.user_id, request.tz)
    transactions = svc.load_recent_transactions(limit=15)
    return render(
        request,
        "dashboard/_recent_transactions.html",
        {"transactions": transactions},
    )


@general_rate
def people_summary_partial(request: AuthenticatedRequest) -> HttpResponse:
    """HTMX partial: people summary. GET /partials/people-summary

    Returns HTML fragment for the people ledger.
    """
    logger.info("partial loaded: people-summary, user=%s", request.user_email)
    svc = DashboardService(request.user_id, request.tz)
    data = svc.get_dashboard()
    return render(request, "dashboard/_people_summary.html", {"data": data})


@general_rate
@require_http_methods(["GET"])
def net_worth_breakdown_partial(
    request: AuthenticatedRequest, card_type: str
) -> HttpResponse:
    """HTMX partial: net worth breakdown by card type.

    GET /dashboard/net-worth/<card_type> — returns account list HTML
    for the bottom sheet drill-down.
    """
    try:
        result = get_net_worth_breakdown(request.user_id, card_type)
    except ValueError:
        return HttpResponse("Invalid card type", status=400)

    return render(
        request,
        "dashboard/_net_worth_breakdown.html",
        {
            "title": result["title"],
            "accounts": result["accounts"],
            "card_type": card_type,
        },
    )


@general_rate
@require_http_methods(["GET"])
def net_worth_partial(request: AuthenticatedRequest) -> HttpResponse:
    """HTMX partial: net worth panel. GET /dashboard/partials/net-worth

    Returns HTML fragment for the dashboard net worth section.
    Used by quick-entry to refresh balance in-place after transaction.
    """
    logger.info("partial loaded: net-worth, user=%s", request.user_email)
    svc = DashboardService(request.user_id, request.tz)
    data = svc.get_dashboard()
    return render(request, "dashboard/_net_worth.html", {"data": data})


@general_rate
@require_http_methods(["GET"])
def accounts_partial(request: AuthenticatedRequest) -> HttpResponse:
    """HTMX partial: accounts panel. GET /dashboard/partials/accounts

    Returns HTML fragment for the dashboard accounts section.
    Used by quick-entry to refresh accounts in-place after transaction.
    """
    logger.info("partial loaded: accounts, user=%s", request.user_email)
    svc = DashboardService(request.user_id, request.tz)
    data = svc.get_dashboard()
    return render(request, "dashboard/_accounts.html", {"data": data})
