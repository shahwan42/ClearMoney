"""
Dashboard views — home page and HTMX partials.

Uses DashboardService to aggregate all data, then renders templates.
Like Laravel's DashboardController or Django's TemplateView.
"""

import logging

from django.http import HttpResponse
from django.shortcuts import render

from core.ratelimit import general_rate
from core.types import AuthenticatedRequest

from .services import DashboardService

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
